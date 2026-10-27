"""#73 synthetic transport/state evidence. No ESP, model weights or AWS."""

from hashlib import sha256
from importlib.util import find_spec
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest

from api_helpers import jpeg, metadata, multipart
from sonar_vision_api.demo import DemoSettings, DemoStore, parse_tof
from sonar_vision_api.errors import ApiError
from sonar_vision_api.validation import Metadata


def tof(**updates):
    return {"version": "demo-tof-1", "session_id": "boot-1", "sequence": "1",
            "captured_at_ms": 1010, "distance_mm": 1250, "valid": True,
            "quality": "good", "sector": "all", "zone": None,
            "aggregation": "min_valid_8x8", **updates}


class DemoStateTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.store = DemoStore(DemoSettings("glasses-01", "boot-1", "simulated"),
                               clock=lambda: self.now, wall_clock=lambda: 1000)
        self.meta = Metadata("boot-1", "1", 1000)

    def accept(self, meta=None, image=None):
        self.store.accepted("glasses-01", meta or self.meta, image or jpeg(), (480, 640), self.now)

    def test_tof_strict_schema(self):
        self.assertEqual(parse_tof(json.dumps(tof())), tof())
        for change in ({"distance_mm": None}, {"distance_mm": True}, {"distance_mm": -1},
                       {"valid": 1}, {"captured_at_ms": 1.5}, {"captured_at_ms": True},
                       {"sequence": "01"}, {"quality": "invalid"}, {"zone": 0},
                       {"sector": "center"}, {"extra": 1}, {"distance_mm": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ApiError):
                parse_tof(json.dumps(tof(**change)))
        for raw in ('[]', '{}', '{"version":"demo-tof-1","version":"other"}', b'\xff'):
            with self.assertRaises(ApiError):
                parse_tof(raw)
        zone = tof(aggregation="zone", zone=63, sector="center")
        self.assertEqual(parse_tof(json.dumps(zone)), zone)
        with self.assertRaises(ApiError):
            parse_tof(json.dumps(tof(aggregation="zone", zone=True)))

    def test_invalid_reading_does_not_become_zero(self):
        self.store.ingest_tof("glasses-01", parse_tof(json.dumps(
            tof(valid=False, quality="invalid", distance_mm=None))))
        snapshot = self.store.snapshot("simulated")
        self.assertEqual(snapshot["tof"]["state"], "invalid")
        self.assertIsNone(snapshot["tof"]["data"]["distance_mm"])
        self.assertEqual(snapshot["image"]["state"], "waiting")

    def test_out_of_order_or_other_source_cannot_replace_valid_data(self):
        self.store.ingest_tof("glasses-01", tof())
        for device, data in (("glasses-01", tof()), ("other", tof(sequence="2")),
                             ("glasses-01", tof(sequence="2", captured_at_ms=1009)),
                             ("glasses-01", tof(sequence="2", session_id="old"))):
            with self.assertRaises(ApiError):
                self.store.ingest_tof(device, data)
        self.assertEqual(self.store.snapshot("simulated")["tof"]["data"]["sequence"], "1")

    def test_independent_staleness_and_payload_expiry_keep_replay_watermarks(self):
        self.accept()
        self.now += 5
        self.store.ingest_tof("glasses-01", tof())
        data = self.store.snapshot("simulated")
        self.assertEqual(data["image"]["state"], "stale")
        self.assertEqual(data["tof"]["state"], "receiving")
        self.now += 25
        self.store.expire()
        self.assertIsNone(self.store.jpeg)
        self.assertIsNone(self.store.frame)
        self.assertIsNotNone(self.store.tof)
        self.now += 5
        self.store.expire()
        self.assertIsNone(self.store.tof)
        with self.assertRaises(ApiError):
            self.store.ingest_tof("glasses-01", tof())

    def test_latest_frame_and_exact_hash_only(self):
        self.accept()
        first_hash = sha256(jpeg()).hexdigest()
        self.assertEqual(self.store.image("1", first_hash), jpeg())
        second = jpeg() + b"second"
        self.accept(Metadata("boot-1", "2", 2000), second)
        with self.assertRaises(ApiError):
            self.store.image("1", first_hash)
        self.assertEqual(self.store.image("2", sha256(second).hexdigest()), second)

    def test_predictions_must_match_frame_capture_session_and_hash(self):
        self.accept()
        result = SimpleNamespace(message_id="m", frame_id="1", session_id="boot-1",
                                 captured_at_ms=1000, tracker_epoch="e", processing_ms=10,
                                 detections=[])
        self.store.record("other", result, jpeg())
        self.store.record("glasses-01", result, b"wrong")
        self.assertEqual(self.store.frame["inference"], "pending")
        self.store.record("glasses-01", result, jpeg())
        self.assertEqual(self.store.frame["inference"], "pending")
        self.assertNotIn("_pending", self.store.snapshot("simulated")["image"]["data"])
        self.store.complete("glasses-01", self.meta)
        self.assertEqual(self.store.frame["inference"], "available")
        self.store.record("glasses-01", result, jpeg(), abandoned=True)
        self.assertEqual(self.store.frame["inference"], "unavailable")
        self.assertIsNone(self.store.frame["predictions"])

    def test_completion_cannot_resurrect_timeout_in_either_record_order(self):
        result = SimpleNamespace(message_id="m", frame_id="1", session_id="boot-1",
                                 captured_at_ms=1000, tracker_epoch="e", processing_ms=10,
                                 detections=[])
        for late_record_first in (False, True):
            self.accept()
            if late_record_first:
                self.store.record("glasses-01", result, jpeg())
            self.store.unavailable("glasses-01", self.meta)
            self.store.record("glasses-01", result, jpeg(), abandoned=False)
            self.store.complete("glasses-01", self.meta)
            self.assertEqual(self.store.frame["inference"], "unavailable")
            self.assertIsNone(self.store.frame["predictions"])
            self.assertNotIn("_pending", self.store.frame)

    def test_end_or_new_boot_clears_both_channels_and_cannot_resurrect(self):
        self.accept()
        self.store.ingest_tof("glasses-01", tof())
        self.accept(Metadata("boot-2", "1", 1))
        self.assertTrue(self.store.ended)
        self.assertIsNone(self.store.jpeg)
        self.assertIsNone(self.store.tof)
        self.accept()
        self.assertIsNone(self.store.jpeg)

    def test_panel_lock_never_blocks_inference_hook(self):
        with self.store._lock:
            self.accept()
        self.assertIsNone(self.store.jpeg)

    def test_allowlist_and_rate_state_are_bounded(self):
        self.assertTrue(self.store.allowed("127.0.0.1"))
        self.assertFalse(self.store.allowed("203.0.113.1"))
        self.assertFalse(self.store.allowed("testclient"))
        with self.assertRaises(ValueError):
            DemoSettings("glasses-01", "boot-1", "esp32", ("0.0.0.0/0",))
        for _ in range(3):
            self.store.rate_limit("snapshot", 3)
        with self.assertRaises(ApiError):
            self.store.rate_limit("snapshot", 3)
        self.now += 1
        self.store.rate_limit("snapshot", 3)

    def test_settings_require_explicit_source_boot_and_restricted_network(self):
        self.assertIsNone(DemoSettings.from_env({}))
        env = {"SONAR_DEMO_ENABLED": "1", "SONAR_DEMO_DEVICE_ID": "glasses-01",
               "SONAR_DEMO_SESSION_ID": "boot-1", "SONAR_DEMO_SOURCE_KIND": "simulated"}
        self.assertEqual(DemoSettings.from_env(env).session_id, "boot-1")
        for update in ({"SONAR_DEMO_SOURCE_KIND": "unknown"},
                       {"SONAR_DEMO_ALLOWED_CIDRS": "0.0.0.0/0"},
                       {"SONAR_DEMO_ALLOWED_CIDRS": "::/0"},
                       {"SONAR_DEMO_SESSION_ID": ""}):
            with self.assertRaises(ValueError):
                DemoSettings.from_env({**env, **update})

    @unittest.skipUnless(find_spec("fastapi"), "install .[api] for startup")
    def test_startup_checks_selected_credential(self):
        from sonar_vision_api.__main__ import build
        from sonar_vision_api.config import Settings
        with TemporaryDirectory() as directory:
            path = Path(directory) / "tokens"
            path.write_text("other " + "a" * 64 + "\n")
            with self.assertRaises(ValueError):
                build(Settings(backend="simulated", tokens_file=path, demo=self.store.settings))

    @unittest.skipUnless(shutil.which("node"), "Node is optional for frontend regression checks")
    def test_frontend_failure_independence_and_pause_race(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([shutil.which("node"), "tests/demo_panel_regression.cjs"],
                                cwd=root, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


AVAILABLE = all(find_spec(n) for n in ("fastapi", "httpx2", "python_multipart"))


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] for demo HTTP tests")
class DemoHttpTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.service import InferenceService, header_only_decoder
        self.TestClient = TestClient
        self.store = DemoStore(DemoSettings("glasses-01", "boot-1", "simulated"))
        self.service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                        timeout_ms=1500, demo=self.store)
        self.addCleanup(self.service.close)
        self.app = create_app(self.service, TokenStore({"glasses-01": token_hash("test-token"),
                             "other": token_hash("other-token")}), backend="simulated",
                              max_body_bytes=4096, max_pixels=640 * 480)
        self.client = TestClient(self.app, client=("127.0.0.1", 40000), raise_server_exceptions=False)
        self.auth = {"Authorization": "Bearer test-token"}

    def upload(self, frame="1", image=None):
        body, ctype = multipart(metadata(frame_id=frame, captured_at_ms=int(frame) * 1000), image or jpeg())
        return self.client.post("/v1/inference", content=body,
                                headers={**self.auth, "Content-Type": ctype})

    def test_no_login_no_token_in_browser_and_restricted_network(self):
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Sonar Vision", response.text)
        self.assertNotIn("test-token", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])
        outside = self.TestClient(self.app, client=("203.0.113.10", 40000))
        for path in ("/demo", "/demo/assets/logo.jpeg", "/v1/demo/snapshot", "/v1/demo/image"):
            self.assertEqual(outside.get(path, headers={"X-Forwarded-For": "127.0.0.1"}).status_code, 403)

    def test_two_frames_and_shared_diagnostic_projection(self):
        for frame, image in (("1", jpeg()), ("2", jpeg() + b"second")):
            response = self.upload(frame, image)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(set(response.json()), {"observation", "audio"})
            snapshot = self.client.get("/v1/demo/snapshot").json()
            f = snapshot["image"]["data"]
            self.assertEqual(f["frame_id"], frame)
            self.assertEqual(f["inference"], "available")
            self.assertEqual(f["predictions"]["jpeg_sha256"], sha256(image).hexdigest())
            r = self.client.get("/v1/demo/image", params={"frame_id": frame, "sha256": f["jpeg_sha256"]})
            self.assertEqual(r.content, image)
        self.assertEqual(self.client.get("/v1/demo/image", params={"frame_id": "1", "sha256": "wrong"}).status_code, 409)

    def test_ingest_authorization_limits_and_order(self):
        url = "/v1/demo/tof"
        self.assertEqual(self.client.post(url, content=b"x" * 3000).status_code, 401)
        self.assertEqual(self.client.post(url, headers={"Authorization": "Bearer other-token"}, json=tof()).status_code, 403)
        self.assertEqual(self.client.post(url, headers=self.auth, content=b"x" * 3000).status_code, 415)
        self.assertEqual(self.client.post(url, headers={**self.auth, "Content-Type": "application/json"}, content=b"x" * 3000).status_code, 413)
        self.assertEqual(self.client.post(url, headers=self.auth, json=tof()).status_code, 204)
        self.assertEqual(self.client.post(url, headers=self.auth, json=tof()).status_code, 409)
        self.assertEqual(self.client.post(url, headers=self.auth, json=tof(sequence="2", valid=False, distance_mm=None, quality="invalid")).status_code, 204)
        self.assertEqual(self.client.get("/v1/demo/snapshot").json()["tof"]["state"], "invalid")
        self.assertEqual(self.client.delete("/v1/demo/session").status_code, 401)
        self.assertEqual(self.client.delete("/v1/demo/session", headers=self.auth).status_code, 204)
        self.assertIsNone(self.store.tof)
        self.assertIsNone(self.store.jpeg)

    def test_spectator_limit_does_not_block_api(self):
        original_clock = self.store.clock
        self.store.clock = lambda: 100.0  # don't straddle the fixed rate window
        try:
            for _ in range(6):
                self.client.get("/v1/demo/snapshot")
            self.assertEqual(self.client.get("/v1/demo/snapshot").status_code, 429)
        finally:
            self.store.clock = original_clock
        self.assertEqual(self.upload().status_code, 200)

    def test_chunked_tof_body_limit(self):
        response = self.client.post("/v1/demo/tof", content=iter([b"x" * 1100, b"x" * 1100]),
                                    headers={**self.auth, "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        self.assertIsNone(self.store.tof)

    def test_expiry_without_spectator_and_shutdown_cleanup(self):
        import time
        now = [100.0]
        self.store.clock = lambda: now[0]
        with self.client:
            self.store.accepted("glasses-01", Metadata("boot-1", "1", 1000), jpeg(), (480,640), 100)
            self.store.ingest_tof("glasses-01", tof())
            now[0] = 131.0
            time.sleep(1.1)
            self.assertIsNone(self.store.jpeg)
            self.assertIsNone(self.store.tof)
        self.assertTrue(self.store.ended)

    def test_rejected_replay_preserves_current_predictions(self):
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(self.store.frame["inference"], "available")

    def test_panel_failure_does_not_invalidate_inference(self):
        self.store.accepted = lambda *a: (_ for _ in ()).throw(RuntimeError("panel failed"))
        self.store.record = self.store.accepted
        self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertGreaterEqual(self.service.counters["demo_error"], 2)

    def test_pending_timeout_and_late_predictions(self):
        import time
        original = self.service.decoder
        def slow(data, shape):
            time.sleep(.02)
            return original(data, shape)
        self.service.decoder = slow
        self.service.timeout = .005
        self.assertEqual(self.upload().status_code, 503)
        time.sleep(.04)
        self.assertEqual(self.store.frame["inference"], "unavailable")
        self.assertIsNone(self.store.frame["predictions"])

    def test_disabled_surface_not_exposed(self):
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        self.service.demo = None
        app = create_app(self.service, TokenStore({"glasses-01": token_hash("test-token")}),
                         backend="simulated", max_body_bytes=4096, max_pixels=640*480)
        self.assertEqual(self.TestClient(app).get("/demo").status_code, 404)


if __name__ == "__main__":
    unittest.main()
