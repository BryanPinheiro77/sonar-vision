"""Read-only history, exact-byte exports and bounded streaming (#73)."""

from hashlib import sha256
from importlib.util import find_spec
from io import BytesIO
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import shutil
import subprocess
from threading import Event
import unittest
from zipfile import ZipFile

from api_helpers import jpeg, metadata, multipart
from test_collection import config, frame, SOURCE, wait_for
from sonar_vision_api.collection import RoundArchive
from sonar_vision_api.errors import ApiError
from sonar_vision_api.history import HistoryReader


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000.0
        self.archive = RoundArchive(Path(self.temp.name) / "rounds", wall_clock=lambda: self.now)
        self.addCleanup(self.archive.close)
        self.cfg = config(retention_seconds=60)
        self.recording = self.archive.start(self.cfg, SOURCE, {"backend": "simulated"})
        self.row, self.image = frame(1)
        self.recording.offer("frame", self.row, self.image)
        self.recording.offer("tof", {"sequence": "1", "captured_at_ms": 900,
            "valid": False, "distance_mm": None, "quality": "invalid"})
        wait_for(lambda: self.archive.timeline(self.cfg.round_id)["tof"])
        self.reader = HistoryReader(self.archive)

    def test_zip_contains_exact_originals_manifest_tof_and_checksums(self):
        download = self.reader.download(self.cfg.round_id)
        data = b"".join(download.chunks())
        download.thread.join(2)
        with ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 4)
            self.assertTrue(all(not name.startswith("/") and ".." not in name for name in names))
            row = json.loads(archive.read("round.json"))
            self.assertIsNone(row["tof"][0]["distance_mm"])
            member = "frames/" + self.row["sample_id"] + ".jpg"
            self.assertEqual(archive.read(member), self.image)
            self.assertEqual(json.loads(archive.read("sha256.json"))[member], sha256(self.image).hexdigest())
            self.assertIn("permission_ref", row["round"])
            self.assertNotIn("test-token", data.decode("latin1"))
        self.assertFalse(any(self.archive.root.rglob("*.zip")))

    def blocked_download(self):
        row, image = frame(2, jpeg() + b"x" * (300 * 1024))
        self.recording.offer("frame", row, image)
        wait_for(lambda: len(self.archive.timeline(self.cfg.round_id)["frames"]) == 2)
        download = self.reader.download(self.cfg.round_id)
        wait_for(lambda: download.queue.full())
        return download

    def test_single_download_two_chunk_queue_and_cancellation(self):
        download = self.blocked_download()
        self.assertLessEqual(download.queue.qsize(), 2)
        self.assertLessEqual(max(map(len, list(download.queue.queue))), 65536)
        with self.assertRaises(ApiError) as error:
            self.reader.download(self.cfg.round_id)
        self.assertEqual(error.exception.status, 429)
        download.close()
        download.thread.join(3)
        self.assertFalse(download.thread.is_alive())
        self.assertEqual(self.archive._leases[self.cfg.round_id], 0)

    def test_retention_refuses_new_reads_but_preserves_export_files_until_release(self):
        download = self.blocked_download()
        self.recording.stop("test_stop")
        self.recording.thread.join(2)
        self.now += 61
        self.assertEqual(self.archive.cleanup(dry_run=False)["removed"], [])
        with self.assertRaises(KeyError):
            self.archive.timeline(self.cfg.round_id)
        download.close()
        download.thread.join(3)
        self.assertEqual(self.archive.cleanup(dry_run=False)["removed"], [self.cfg.round_id])

    def test_corrupt_jpeg_cannot_be_served_or_exported_as_valid(self):
        path = self.archive.root / self.cfg.round_id / "frames" / (self.row["sample_id"] + ".jpg")
        path.write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            self.archive.frame(self.cfg.round_id, self.row["sample_id"])
        download = self.reader.download(self.cfg.round_id)
        with self.assertRaises(OSError):
            b"".join(download.chunks())
        download.thread.join(2)

    def test_public_timeline_omits_permission_reference_and_never_mutates_manifest(self):
        data = json.loads(self.reader.timeline(self.cfg.round_id))
        self.assertNotIn("permission_ref", data["round"])
        self.assertNotIn("permission_ref", data["round"]["limits"])
        self.assertIn("permission_ref", self.archive.timeline(self.cfg.round_id)["round"])

    def test_download_has_bounded_deadline(self):
        download = self.blocked_download()
        download.deadline = time.monotonic() - 1
        self.assertEqual(list(download.chunks()), [])
        download.thread.join(2)
        self.assertFalse(download.thread.is_alive())

    def test_canceled_reads_keep_their_slots_until_disk_work_finishes(self):
        release = Event()
        def blocked():
            release.wait(3)
            return True
        async def exercise():
            first = asyncio.create_task(self.reader.read(blocked))
            second = asyncio.create_task(self.reader.read(blocked))
            await asyncio.sleep(.02)
            with self.assertRaises(ApiError):
                await self.reader.read(lambda: True)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            with self.assertRaises(ApiError):
                await self.reader.read(lambda: True)
            release.set()
            self.assertTrue(await second)
        try:
            asyncio.run(exercise())
        finally:
            release.set()

    @unittest.skipUnless(shutil.which("node"), "Node is optional for player-core regressions")
    def test_temporal_player_regressions(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), "tests/player_core_regression.cjs"],
                                cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node is optional for history UI regressions")
    def test_expired_or_failed_selection_clears_old_identity_and_download(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), "tests/history_panel_regression.cjs"],
                                cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


AVAILABLE = all(find_spec(n) for n in ("fastapi", "httpx2", "python_multipart"))


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] for history HTTP tests")
class HistoryHttpTests(HistoryTests):
    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.demo import DemoSettings, DemoStore
        from sonar_vision_api.service import InferenceService, header_only_decoder
        self.demo = DemoStore(DemoSettings("demo-sim", "boot-1", "simulated"), archive=self.archive)
        self.service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                        timeout_ms=1500, demo=self.demo)
        self.addCleanup(self.service.close)
        self.app = create_app(self.service, TokenStore({"demo-sim": token_hash("test-token")}),
            backend="simulated", max_body_bytes=4096, max_pixels=640*480)
        self.client = TestClient(self.app, client=("127.0.0.1", 1), raise_server_exceptions=False)

    def test_network_restriction_and_header_spoofing_cover_history_and_exports(self):
        from fastapi.testclient import TestClient
        outsider = TestClient(self.app, client=("203.0.113.1", 1))
        base = "/v1/demo/history/" + self.cfg.round_id
        for path in ("/v1/demo/history", base, base + "/download", base + "/frames/" + self.row["sample_id"]):
            self.assertEqual(outsider.get(path, headers={"X-Forwarded-For": "127.0.0.1"}).status_code, 403)

    def test_list_timeline_image_and_download_are_read_only_and_no_store(self):
        summary = self.client.get("/v1/demo/history").json()["rounds"][0]
        self.assertEqual(summary["round_id"], self.cfg.round_id)
        self.assertNotIn("permission_ref", summary["limits"])
        base = "/v1/demo/history/" + self.cfg.round_id
        self.assertEqual(self.client.get(base).json()["frames"][0]["jpeg_sha256"], self.row["jpeg_sha256"])
        image = self.client.get(base + "/frames/" + self.row["sample_id"])
        self.assertEqual(image.content, self.image)
        self.assertIn("no-store", image.headers["cache-control"])
        response = self.client.get(base + "/download")
        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertIn("round.json", archive.namelist())
        self.assertEqual(self.client.delete(base).status_code, 405)

    def test_expired_history_and_tampered_identifiers_never_leak_paths(self):
        self.now += 61
        response = self.client.get("/v1/demo/history/" + self.cfg.round_id)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(str(self.archive.root), response.text)
        self.assertEqual(self.client.get("/v1/demo/history/not-an-id").status_code, 400)

    def test_busy_download_does_not_stop_inference(self):
        download = self.blocked_download()
        try:
            base = "/v1/demo/history/" + self.cfg.round_id
            self.assertEqual(self.client.get(base + "/download").status_code, 429)
            body, ctype = multipart(metadata(), jpeg())
            response = self.client.post("/v1/inference", content=body, headers={
                "Authorization": "Bearer test-token", "Content-Type": ctype})
            self.assertEqual(response.status_code, 200)
        finally:
            download.close()
            download.thread.join(3)


if __name__ == "__main__":
    unittest.main()
