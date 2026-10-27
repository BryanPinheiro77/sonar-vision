"""#73 persisted evidence with synthetic bytes, private temp dirs and controlled clocks."""

from dataclasses import replace
from hashlib import sha256
from importlib.util import find_spec
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
from types import SimpleNamespace
import unittest
from uuid import uuid4

from api_helpers import jpeg, metadata, multipart
from sonar_vision_api.collection import CollectionConfig, RoundArchive, QUEUE_SIZE
from sonar_vision_api.diagnostics import prediction_record

SOURCE = {"device_id": "demo-sim", "session_id": "boot-1", "kind": "simulated"}


def config(**updates):
    base = CollectionConfig(uuid4().hex, "synthetic-73", "owned-synthetic", 600, 3000,
                            100 * 1024 * 1024, 86400)
    return replace(base, **updates)


def frame(index=1, image=None):
    image = image or jpeg() + str(index).encode()
    row = {"frame_id": str(index), "session_id": "boot-1", "captured_at_ms": index * 1000,
           "received_at_ms": 1000000, "jpeg_sha256": sha256(image).hexdigest(),
           "shape": [480, 640], "prediction_status": "unavailable", "predictions": None}
    row["sample_id"] = RoundArchive.sample_id(SOURCE, row)
    return row, image


def wait_for(predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        time.sleep(.01)
    if not predicate():
        raise AssertionError("collection worker did not reach expected state")


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "private"
        self.now = 1000.0
        self.archive = RoundArchive(self.root, clock=lambda: self.now, wall_clock=lambda: self.now)
        self.addCleanup(self.archive.close)
        self.cfg = config()

    def start(self, **changes):
        self.cfg = replace(self.cfg, **changes)
        self.recording = self.archive.start(self.cfg, SOURCE, {"backend": "simulated"})
        return self.recording

    def save(self, index=1):
        row, image = frame(index)
        self.recording.offer("frame", row, image)
        wait_for(lambda: len(self.archive.timeline(self.cfg.round_id)["frames"]) >= index)
        return row, image

    def test_retention_rescan_and_recording_preserve_aggregate_byte_count(self):
        self.start(retention_seconds=1)
        self.save()
        self.archive.close()
        self.now += 2
        self.archive = RoundArchive(self.root, clock=lambda: self.now,
                                    wall_clock=lambda: self.now, automatic_cleanup=False)
        self.addCleanup(self.archive.close)
        # Keep the expired round until a new collection is already writing.
        cleanup = self.archive.cleanup
        self.archive.cleanup = lambda **kwargs: None
        self.cfg = config()
        self.start()
        self.archive.cleanup = cleanup
        scanned, release, entered, written = Event(), Event(), Event(), Event()
        disk_bytes, record = self.archive._disk_bytes, self.archive._record

        def delayed_scan():
            size = disk_bytes()
            scanned.set()
            if not release.wait(3):
                raise AssertionError("retention scan was not released")
            return size

        def observed_record(*args):
            entered.set()
            record(*args)
            written.set()

        self.archive._disk_bytes = delayed_scan
        self.archive._record = observed_record
        worker = Thread(target=lambda: cleanup(dry_run=False))
        worker.start()
        try:
            self.assertTrue(scanned.wait(3))
            row, image = frame()
            self.recording.offer("frame", row, image)
            self.assertTrue(entered.wait(3))
            # A racing writer used to invalidate the pending retention total.
            written.wait(.2)
        finally:
            release.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertTrue(written.wait(3))
        self.archive._disk_bytes = disk_bytes
        self.assertEqual(self.archive.total_bytes, disk_bytes())

    def test_explicit_limits_and_provenance_required(self):
        for change in ({"permission_ref": ""}, {"source_id": ""}, {"max_frames": 0},
                       {"max_frames": 3001}, {"max_bytes": True}, {"retention_seconds": 86401},
                       {"round_id": "../other"}, {"max_duration_seconds": 601}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                config(**change)

    def test_no_opt_in_does_not_record(self):
        self.assertIsNone(self.archive.recording)
        self.assertEqual(self.archive.summaries(), [])
        self.assertFalse(any(self.root.rglob("*.jpg")))

    def test_oversized_images_do_not_enter_the_bounded_queue(self):
        self.start()
        row, image = frame(1, b"x" * (512 * 1024 + 1))
        self.recording.offer("frame", row, image)
        self.assertTrue(self.recording.queue.empty())
        self.assertEqual(self.recording.drops["image_exceeds_collection_limit"], 1)

    def test_two_images_exact_bytes_and_correlated_predictions(self):
        self.start()
        first, image1 = self.save(1)
        second, image2 = self.save(2)
        result = SimpleNamespace(message_id="m", frame_id="2", session_id="boot-1",
            captured_at_ms=2000, tracker_epoch="epoch", processing_ms=10, detections=[])
        self.recording.offer("prediction", {"sample_id": second["sample_id"], "status": "available",
                                           "predictions": prediction_record(result, image2)})
        wait_for(lambda: self.archive.timeline(self.cfg.round_id)["frames"][-1]["prediction_status"] == "available")
        self.assertEqual(self.archive.frame(self.cfg.round_id, first["sample_id"]), image1)
        self.assertEqual(self.archive.frame(self.cfg.round_id, second["sample_id"]), image2)
        self.assertNotEqual(first["jpeg_sha256"], second["jpeg_sha256"])
        self.assertEqual(self.archive.timeline(self.cfg.round_id)["frames"][0]["prediction_status"], "unavailable")

    def test_wrong_hash_prediction_is_never_attached(self):
        self.start()
        row, _ = self.save()
        self.recording.offer("prediction", {"sample_id": row["sample_id"], "status": "available",
            "predictions": {"frame_id": "other", "captured_at_ms": 0, "jpeg_sha256": "wrong"}})
        wait_for(lambda: not self.recording.thread.is_alive())
        self.assertEqual(self.archive.timeline(self.cfg.round_id)["frames"][0]["prediction_status"], "unavailable")
        self.assertEqual(self.recording.reason, "write_error")
        self.archive.close()
        reopened = RoundArchive(self.root, wall_clock=lambda: self.now)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.timeline(self.cfg.round_id)["frames"][0]["prediction_status"], "unavailable")

    def test_invalid_tof_and_separate_timestamps_preserved(self):
        self.start()
        self.save()
        data = {"sequence": "4", "captured_at_ms": 1250, "distance_mm": None,
                "valid": False, "quality": "invalid", "received_at_ms": 1000500}
        self.recording.offer("tof", data)
        wait_for(lambda: len(self.archive.timeline(self.cfg.round_id)["tof"]) == 1)
        self.assertEqual(self.archive.timeline(self.cfg.round_id)["tof"][0], data)

    def test_count_duration_and_byte_limits(self):
        self.start(max_frames=1)
        self.save()
        row, image = frame(2)
        self.recording.offer("frame", row, image)
        wait_for(lambda: not self.recording.thread.is_alive())
        self.assertEqual(self.recording.reason, "frame_limit")
        self.assertEqual(len(self.archive.timeline(self.cfg.round_id)["frames"]), 1)
        self.assertLessEqual(self.archive._disk_bytes(), self.cfg.max_bytes)

    def test_duration_stops_without_more_uploads(self):
        self.start(max_duration_seconds=1)
        self.now += 2
        wait_for(lambda: not self.recording.thread.is_alive())
        self.assertEqual(self.recording.reason, "duration_limit")

    def test_byte_budget_stops_before_writing_large_image(self):
        self.start(max_bytes=8192)
        row, image = frame(1, jpeg() + b"x" * 8192)
        self.recording.offer("frame", row, image)
        wait_for(lambda: not self.recording.thread.is_alive())
        self.assertEqual(self.recording.reason, "byte_limit")
        self.assertFalse(any(self.root.rglob("*.jpg")))

    def test_queue_is_bounded_and_slow_disk_does_not_block_offer(self):
        self.start()
        entered, release = Event(), Event()
        original = self.archive._record
        def slow(*args):
            entered.set()
            release.wait(3)
            return original(*args)
        self.archive._record = slow
        row, image = frame()
        self.recording.offer("frame", row, image)
        self.assertTrue(entered.wait(2))
        start = time.monotonic()
        for i in range(2, 30):
            row, image = frame(i)
            self.recording.offer("frame", row, image)
        self.assertLess(time.monotonic() - start, .5)
        self.assertLessEqual(self.recording.queue.qsize(), QUEUE_SIZE)
        self.assertGreater(self.recording.drops["queue_full"], 0)
        release.set()

    def test_disk_failure_disables_recording_and_releases_queued_bytes(self):
        self.start()
        def fail(*args):
            raise OSError("disk full")
        self.archive._record = fail
        self.recording.offer("frame", *frame())
        wait_for(lambda: not self.recording.thread.is_alive())
        self.assertEqual(self.recording.reason, "write_error")
        self.assertTrue(self.recording.queue.empty())

    def test_restart_keeps_closed_round_and_refuses_overwrite(self):
        self.start()
        row, image = self.save()
        self.archive.close()
        reopened = RoundArchive(self.root, wall_clock=lambda: self.now)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.frame(self.cfg.round_id, row["sample_id"]), image)
        self.assertEqual(reopened.summaries()[0]["state"], "completed")
        with self.assertRaises(ValueError):
            reopened.start(self.cfg, SOURCE, {})

    def test_interrupted_journal_tail_is_recovered_without_reopening_round(self):
        self.start()
        self.save()
        self.archive.close()
        directory = self.root / self.cfg.round_id
        manifest = json.loads((directory / "manifest.json").read_text())
        manifest["state"] = "recording"
        (directory / "manifest.json").write_text(json.dumps(manifest))
        with (directory / "events.jsonl").open("ab") as stream:
            stream.write(b'{"incomplete":')
        reopened = RoundArchive(self.root, wall_clock=lambda: self.now)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.summaries()[0]["state"], "interrupted")
        self.assertEqual(reopened.summaries()[0]["recovery"], "incomplete_tail_ignored")

    def test_cleanup_is_scoped_dry_run_then_execute_and_does_not_touch_export(self):
        self.start(retention_seconds=1)
        self.save()
        self.archive.close()
        export = Path(self.temp.name) / "human-export.zip"
        export.write_bytes(b"preserve")
        self.now += 2
        self.assertEqual(self.archive.summaries(), [])
        with self.assertRaises(KeyError):
            self.archive.timeline(self.cfg.round_id)
        report = self.archive.cleanup()
        self.assertEqual(report["eligible"], [self.cfg.round_id])
        self.assertTrue((self.root / self.cfg.round_id).exists())
        self.archive.cleanup(dry_run=False)
        self.assertFalse((self.root / self.cfg.round_id).exists())
        self.assertEqual(export.read_bytes(), b"preserve")

    def test_symlinks_unknown_files_and_path_traversal_are_refused(self):
        self.start(retention_seconds=1)
        self.save()
        self.archive.close()
        outside = Path(self.temp.name) / "outside"
        outside.write_bytes(b"preserve")
        (self.root / self.cfg.round_id / "frames" / ("a"*64 + ".jpg")).symlink_to(outside)
        self.now += 2
        self.assertEqual(self.archive.cleanup(dry_run=False)["refused"], [self.cfg.round_id])
        self.assertEqual(outside.read_bytes(), b"preserve")
        with self.assertRaises(ValueError):
            self.archive.timeline("../outside")

    def test_archive_cannot_be_opened_twice_while_api_owns_it(self):
        with self.assertRaises(ValueError):
            RoundArchive(self.root)

    def test_offline_dry_run_has_no_background_deletion(self):
        self.start(retention_seconds=1)
        self.save()
        self.archive.close()
        self.now += 2
        offline = RoundArchive(self.root, wall_clock=lambda: self.now, automatic_cleanup=False)
        self.addCleanup(offline.close)
        self.assertIsNone(offline._house)
        self.assertEqual(offline.cleanup()["eligible"], [self.cfg.round_id])
        self.assertTrue((self.root / self.cfg.round_id).exists())


AVAILABLE = all(find_spec(n) for n in ("fastapi", "httpx2", "python_multipart"))


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] for collection adapter tests")
class CollectionIntegrationTests(unittest.TestCase):
    def test_recording_failure_never_invalidates_inference_or_tof(self):
        from fastapi.testclient import TestClient
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.demo import DemoSettings, DemoStore
        from sonar_vision_api.service import InferenceService, header_only_decoder
        with TemporaryDirectory() as temp:
            archive = RoundArchive(Path(temp) / "private")
            archive.start(config(), SOURCE, {})
            def fail(*args):
                raise OSError("simulated disk full")
            archive._record = fail
            demo = DemoStore(DemoSettings("demo-sim", "boot-1", "simulated"), archive=archive)
            service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                       timeout_ms=1500, demo=demo)
            try:
                client = TestClient(create_app(service, TokenStore({"demo-sim": token_hash("test-token")}),
                    backend="simulated", max_body_bytes=4096, max_pixels=640*480), client=("127.0.0.1", 1))
                auth = {"Authorization": "Bearer test-token"}
                for i in (1, 2):
                    body, ctype = multipart(metadata(frame_id=str(i), captured_at_ms=i*1000), jpeg())
                    response = client.post("/v1/inference", content=body, headers={**auth,"Content-Type":ctype})
                    self.assertEqual(response.status_code, 200)
                wait_for(lambda: not archive.recording.thread.is_alive())
                self.assertEqual(archive.recording.reason, "write_error")
                self.assertEqual(client.get("/healthz").status_code, 200)
                response = client.post("/v1/demo/tof", headers=auth, json={"version": "demo-tof-1",
                    "session_id": "boot-1", "sequence": "1", "captured_at_ms": 2100,
                    "distance_mm": None, "valid": False, "quality": "invalid", "sector": "all",
                    "zone": None, "aggregation": "min_valid_8x8"})
                self.assertEqual(response.status_code, 204)
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
