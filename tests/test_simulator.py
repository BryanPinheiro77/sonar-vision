"""Issue #30: synthetic client tests, not physical safety or real API evidence."""
from copy import deepcopy
import contextlib
import io
import json
import ssl
from threading import Event, Thread
import unittest
from unittest.mock import patch

from sonar_vision.simulator import (
    Capture, FixtureSource, FixtureTransport, HTTPS, LocalState, MAX_BODY,
    Orientation, Profile, Rejected, SCENARIOS, Simulator, VirtualClock,
    main, multipart, parse_response,
)


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.clock = VirtualClock()
        self.client = Simulator(clock=self.clock)
        self.source = FixtureSource()
        self.state = LocalState(Orientation.yaw(0))
        self.capture = Capture(self.client.session_id, "0", 0, b"jpeg", self.state.orientation)

    def body(self):
        return FixtureTransport(self.clock).send(self.capture)

    def run_fixture(self, scenario="success", current=None):
        states = iter((self.state, current or self.state))
        return self.client.exchange(self.source, FixtureTransport(self.clock, scenario),
                                    lambda: next(states))

    def test_success_metadata_image_and_no_risk_or_audio_execution(self):
        result = self.run_fixture()
        self.assertEqual(result["outcome"], "accepted")
        self.assertEqual(result["audio"], "accepted")
        self.assertEqual(result["latency_ms"], 100)
        self.assertNotIn("risk", result)
        self.assertNotIn("text", result)
        body, kind = multipart(self.capture)
        self.assertIn(b'name="metadata"', body)
        self.assertIn(b'name="image"; filename="capture.jpg"', body)
        self.assertIn(json.dumps(self.capture.metadata(), separators=(",", ":")).encode(), body)
        self.assertIn(b"\r\njpeg\r\n", body)
        self.assertIn("boundary=sonar-", kind)

    def test_deterministic_failure_scenarios(self):
        expected = {"expired": "expired", "timeout": "timeout",
                    "old_session": "session_mismatch", "wrong_capture": "capture_mismatch",
                    "malformed": "invalid_message", "oversized": "response_too_large",
                    "unauthorized": "http_401", "disconnect": "network_error"}
        for scenario, reason in expected.items():
            with self.subTest(scenario=scenario):
                result = self.run_fixture(scenario)
                self.assertEqual(result["outcome"], "discarded")
                self.assertEqual(result["reason"], reason)

    def test_validity_boundaries_and_server_cannot_extend(self):
        body = self.body()
        for age, accepted in ((999, True), (1000, False)):
            self.client._seen.clear()
            self.clock.now = age
            if accepted:
                self.assertEqual(self.client.admit(body, self.capture, self.state)["audio"], "accepted")
            else:
                with self.assertRaisesRegex(Rejected, "expired"):
                    self.client.admit(body, self.capture, self.state)
        value = json.loads(body)
        value["observation"]["valid_for_ms"] = 9000
        with self.assertRaisesRegex(Rejected, "expired"):
            self.client.admit(json.dumps(value).encode(), self.capture, self.state)

    def test_audio_validity_never_extends_observation_and_short_audio_expires(self):
        value = json.loads(self.body())
        value["audio"]["valid_for_ms"] = 100
        self.assertEqual(self.client.admit(json.dumps(value).encode(), self.capture, self.state)["audio"], "expired")
        value["observation"]["valid_for_ms"] = 100
        value["audio"]["valid_for_ms"] = 9000
        with self.assertRaisesRegex(Rejected, "expired"):
            self.client.admit(json.dumps(value).encode(), self.capture, self.state)

    def test_orientation_boundaries_quaternion_sign_wrap_and_reference(self):
        for degrees, reason in ((15, "accepted"), (15.01, "orientation_changed"), (360, "accepted")):
            self.client._seen.clear()
            result = self.client.admit(self.body(), self.capture, LocalState(Orientation.yaw(degrees)))
            self.assertEqual(result["audio"], reason)
        for orientation in (Orientation.yaw(0, valid=False), Orientation.yaw(0, reference="reset")):
            self.client._seen.clear()
            result = self.client.admit(self.body(), self.capture, LocalState(orientation))
            self.assertEqual(result["audio"], "orientation_invalid")
        self.assertAlmostEqual(Orientation.yaw(179).separation(Orientation.yaw(-179)), 2)
        self.assertAlmostEqual(Orientation((1, 0, 0, 0)).separation(Orientation((-1, 0, 0, 0))), 0)
        self.assertAlmostEqual(Orientation((1, 0, 0, 0)).separation(Orientation((0, 1, 0, 0))), 180)

    def test_non_directional_audio_does_not_require_orientation(self):
        value = json.loads(self.body())
        value["audio"]["directional"] = False
        result = self.client.admit(json.dumps(value).encode(), self.capture,
                                   LocalState(Orientation.yaw(0, valid=False)))
        self.assertEqual(result["audio"], "accepted")

    def test_urgent_state_suppresses_audio_without_changing_observation(self):
        result = self.run_fixture(current=LocalState(Orientation.yaw(0), True))
        self.assertEqual(result["observation"], "accepted")
        self.assertEqual(result["audio"], "local_urgent")
        self.client.update_local(self.state)
        result = self.run_fixture()
        self.assertEqual(result["audio"], "before_urgent_release")
        self.clock.now += 1
        self.assertEqual(self.run_fixture()["audio"], "accepted")

    def test_duplicate_conflict_restart_clock_regression_and_capacity(self):
        body = self.body()
        self.client.admit(body, self.capture, self.state)
        with self.assertRaisesRegex(Rejected, "duplicate"):
            self.client.admit(body, self.capture, self.state)
        changed = json.loads(body)
        changed["audio"]["text"] = "Pessoa"
        # Same observation is already consumed regardless of modified audio.
        changed["observation"]["tracker_epoch"] = "new"
        with self.assertRaisesRegex(Rejected, "id_conflict"):
            self.client.admit(json.dumps(changed).encode(), self.capture, self.state)
        self.client.restart()
        with self.assertRaisesRegex(Rejected, "session_mismatch"):
            self.client.admit(body, self.capture, self.state)
        self.client.session_id = self.capture.session_id
        self.clock.now = -1
        with self.assertRaisesRegex(Rejected, "clock_regression"):
            self.client.admit(body, self.capture, self.state)
        self.clock.now = 100
        self.client._seen = {str(i): (1000, {}) for i in range(64)}
        with self.assertRaisesRegex(Rejected, "capacity"):
            self.client.admit(body, self.capture, self.state)

    def test_busy_never_reads_or_queues_new_capture(self):
        entered, release = Event(), Event()
        outer = self

        class Blocking:
            def ready(self):
                return True

            def send(self, capture):
                entered.set()
                release.wait(2)
                return FixtureTransport(outer.clock).send(capture)

        first = []
        thread = Thread(target=lambda: first.append(self.client.exchange(self.source, Blocking(), lambda: self.state)))
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            class ForbiddenSource:
                def read(self, clock):
                    raise AssertionError("busy must not capture")
            self.assertEqual(self.client.exchange(ForbiddenSource(), Blocking(), lambda: self.state)["reason"], "busy")
        finally:
            release.set()
            thread.join(2)
        self.assertEqual(first[0]["outcome"], "accepted")
        self.assertEqual(self.client.counter, 1)

    def test_late_response_after_restart_is_rejected(self):
        outer = self

        class RestartTransport(FixtureTransport):
            def send(self, capture):
                body = super().send(capture)
                outer.client.restart()
                return body

        result = self.client.exchange(self.source, RestartTransport(self.clock), lambda: self.state)
        self.assertEqual(result["reason"], "session_mismatch")

    def test_complete_envelope_validation_before_effects(self):
        original = json.loads(self.body())
        invalid = []
        for key in original["observation"]:
            value = deepcopy(original)
            del value["observation"][key]
            invalid.append(value)
        for location, key, bad in (
                ("observation", "objects", [{}] * 21), ("observation", "valid_for_ms", True),
                ("observation", "captured_at_ms", 2**53), ("observation", "tracker_epoch", "x" * 129),
                ("audio", "text", "é" * 121), ("audio", "directional", 1),
                ("audio", "observation_id", "wrong"), ("audio", "session_id", "wrong")):
            value = deepcopy(original)
            value[location][key] = bad
            invalid.append(value)
        for bad in (True, float("nan"), 1.1, [], None):
            value = deepcopy(original)
            value["observation"]["objects"][0]["confidence"] = bad
            invalid.append(value)
        value = deepcopy(original)
        value["observation"]["vibration"] = True
        invalid.append(value)
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises(Rejected):
                    self.client.admit(json.dumps(value).encode(), self.capture, self.state)
                self.assertFalse(self.client._seen)
        for body in (b'{"observation":null,"observation":null,"audio":null}', b"\xff", b"NaN"):
            with self.assertRaises(Rejected):
                parse_response(body)

    def test_exact_response_size_and_unicode_text_limits(self):
        value = json.loads(self.body())
        value["audio"]["text"] = "é" * 120
        body = json.dumps(value, ensure_ascii=False).encode()
        padded = body + b" " * (MAX_BODY - len(body))
        self.assertEqual(parse_response(padded)["audio"]["text"], "é" * 120)
        with self.assertRaisesRegex(Rejected, "response_too_large"):
            parse_response(padded + b" ")

    def test_duplicate_fixture_reuses_ids_and_is_rejected(self):
        transport = FixtureTransport(self.clock, "duplicate")
        self.assertEqual(self.client.exchange(self.source, transport, lambda: self.state)["audio"], "accepted")
        self.assertEqual(self.client.exchange(self.source, transport, lambda: self.state)["reason"], "id_conflict")

    def test_cli_fixtures_and_orientation_are_reproducible(self):
        for scenario in SCENARIOS:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--fixture", scenario, "--frames", "2"])
            self.assertEqual(code, 0)
            lines = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual(lines[0]["local_inputs"], "simulated")
            self.assertEqual(len(lines), 3)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            main(["--fixture", "success", "--current-yaw", "16"])
        self.assertIn("orientation_changed", output.getvalue())

    def test_invalid_profile_and_orientation(self):
        for kwargs in ({"validity_ms": 0}, {"timeout_ms": True}, {"angle_deg": float("nan")}):
            with self.assertRaises(ValueError):
                Profile(**kwargs)
        for quaternion in ((0, 0, 0, 0), (1, 2), (1, 0, float("nan"), 0)):
            with self.assertRaises(ValueError):
                Orientation(quaternion)


class HTTPSTests(unittest.TestCase):
    def setUp(self):
        self.capture = Capture("s", "1", 0, b"private-image", Orientation.yaw(0))

    def test_configuration_rejects_plain_http_redirect_targets_and_header_injection(self):
        for endpoint in ("http://example.com", "https://user:pass@example.com",
                         "https://example.com/wrong", "https://example.com?token=x"):
            with self.assertRaises(ValueError):
                HTTPS(endpoint, "secret")
        for token in ("", "bad\r\nHeader:x", "bad token", "não-ascii"):
            with self.assertRaises(ValueError):
                HTTPS("https://example.com", token)
        transport = HTTPS("https://example.com", "secret")
        self.assertEqual(transport.context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(transport.context.check_hostname)

    def fake_connection(self, *, status=200, body=b"{}", content_type="application/json", length=None, error=None):
        outer = self

        class Sock:
            def settimeout(self, value):
                outer.assertGreater(value, 0)

        class Response:
            def __init__(self):
                self.status, self.data = status, body

            def getheader(self, name, default=None):
                return {"Content-Type": content_type, "Content-Length": length}.get(name, default)

            def read1(self, amount):
                chunk, self.data = self.data[:amount], self.data[amount:]
                return chunk

        class Connection:
            sock = Sock()

            def __init__(self, host, port, context, timeout):
                outer.assertTrue(context.check_hostname)

            def connect(self):
                if error:
                    raise error

            def request(self, method, path, data, headers):
                outer.assertEqual(method, "POST")
                outer.assertEqual(path, "/v1/inference")
                outer.assertEqual(headers["Authorization"], "Bearer secret")
                outer.assertIn(b"private-image", data)
                outer.assertIn(b'"session_id":"s"', data)

            def getresponse(self):
                return Response()

            def close(self):
                pass
        return Connection

    def test_verified_transport_constructs_request_and_bounds_body(self):
        transport = HTTPS("https://example.com", "secret")
        with patch("sonar_vision.simulator.http.client.HTTPSConnection", self.fake_connection()):
            self.assertEqual(transport.send(self.capture), b"{}")
        for kwargs, reason in (
                ({"status": 302}, "http_302"), ({"status": 401}, "http_401"),
                ({"status": 503}, "http_503"), ({"body": b"x" * (MAX_BODY + 1)}, "response_too_large"),
                ({"length": str(MAX_BODY + 1)}, "response_too_large"),
                ({"content_type": "text/html"}, "invalid_content_type"),
                ({"error": ssl.SSLCertVerificationError("private secret")}, "tls_error"),
                ({"error": OSError("private secret")}, "network_error")):
            with self.subTest(kwargs=kwargs):
                with patch("sonar_vision.simulator.http.client.HTTPSConnection", self.fake_connection(**kwargs)):
                    with self.assertRaisesRegex(Rejected, reason) as raised:
                        transport.send(self.capture)
                    self.assertNotIn("private", str(raised.exception))
                    self.assertTrue(transport.ready())

    def test_deadline_returns_and_never_starts_another_worker_while_dns_is_blocked(self):
        release, entered, sent = Event(), Event(), Event()
        base = self.fake_connection()

        class SlowConnection(base):
            sock = None

            def connect(self):
                entered.set()
                release.wait(2)

            def request(self, *args):
                sent.set()
                super().request(*args)

        transport = HTTPS("https://example.com", "secret", profile=Profile(timeout_ms=20))
        with patch("sonar_vision.simulator.http.client.HTTPSConnection", SlowConnection):
            try:
                with self.assertRaisesRegex(Rejected, "timeout"):
                    transport.send(self.capture)
                self.assertTrue(entered.is_set())
                self.assertFalse(transport.ready())
                with self.assertRaisesRegex(Rejected, "busy"):
                    transport.send(self.capture)
            finally:
                release.set()
            # Acquire blocks only for cleanup, proving abandoned worker releases its guard.
            self.assertTrue(transport._active.acquire(timeout=1))
            transport._active.release()
            self.assertFalse(sent.is_set())

class CaptureSourceTests(unittest.TestCase):
    def test_video_skips_old_frames_and_timestamp_precedes_encoding(self):
        import sys
        from types import SimpleNamespace
        from sonar_vision.simulator import OpenCVSource

        clock = VirtualClock()
        positions = []

        class JPEG:
            def tobytes(self):
                return b"encoded-corresponding-frame"

        class Camera:
            def isOpened(self):
                return True
            def get(self, prop):
                return 30
            def set(self, prop, position):
                positions.append(position)
                return True
            def read(self):
                clock.now += 2
                return True, object()
            def release(self):
                pass

        def encode(extension, image):
            clock.now += 5
            return True, JPEG()

        cv2 = SimpleNamespace(VideoCapture=lambda source: Camera(), CAP_PROP_FPS=1,
                              CAP_PROP_POS_FRAMES=2, imencode=encode)
        with patch.dict(sys.modules, {"cv2": cv2}):
            source = OpenCVSource("authorized-video")
            try:
                jpeg, timestamp = source.read(clock)
                self.assertEqual(jpeg, b"encoded-corresponding-frame")
                self.assertEqual(timestamp, 2)
                self.assertEqual(clock.now, 7)
                clock.now = 1000
                _, timestamp = source.read(clock)
                self.assertEqual(positions, [30])
                self.assertEqual(timestamp, 1002)
            finally:
                source.close()

    def test_webcam_reader_keeps_only_latest_sample_and_reports_failure(self):
        from sonar_vision.simulator import OpenCVSource
        from threading import Lock
        source = OpenCVSource.__new__(OpenCVSource)
        source._lock, source._stop, source._available = Lock(), Event(), Event()
        source._latest, source._error = None, False
        source._thread = None

        class Camera:
            count = 0
            def read(self):
                self.count += 1
                if self.count == 3:
                    source._stop.set()
                return True, self.count
            def release(self):
                pass

        source.cap = Camera()
        with patch("sonar_vision.simulator.monotonic", side_effect=(1, 2, 3)):
            source._reader()
        self.assertEqual(source._latest, (3, 3000))
        self.assertTrue(source._available.is_set())
        source.close()

    def test_capture_errors_are_explicit_and_do_not_send(self):
        clock = VirtualClock()
        client = Simulator(clock=clock)

        class BadSource:
            def read(self, clock):
                raise Rejected("source_ended_or_decode_failed")

        class ForbiddenTransport:
            def ready(self):
                return True
            def send(self, capture):
                raise AssertionError("failed capture must never be sent")

        result = client.exchange(BadSource(), ForbiddenTransport(),
                                 lambda: LocalState(Orientation.yaw(0)))
        self.assertEqual(result["reason"], "source_ended_or_decode_failed")


if __name__ == "__main__":
    unittest.main()
