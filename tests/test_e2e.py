"""#27 deterministic end-to-end checks over real HTTPS (requires .[api,api-dev]).

Simulated backend only; no camera, weights, network outside loopback or cost.
Real-detector checks live in test_e2e_real.py and are opt-in.
"""

from importlib.util import find_spec
from pathlib import Path
import socket
import ssl
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest

from api_helpers import jpeg, metadata, multipart

AVAILABLE = all(find_spec(n) for n in ("fastapi", "uvicorn", "httpx2", "trustme", "python_multipart"))


class SpeakPolicy:
    """Server-side stand-in for the #5/#31 policy: always suggests 'Pessoa'."""

    def __init__(self, session_id):
        pass

    def select(self, observation, *, capture_age_lower_bound_ms):
        return {"version": "0.1", "type": "audio_suggestion",
                "session_id": observation["session_id"], "message_id": "a-" + observation["message_id"],
                "frame_id": observation["frame_id"], "captured_at_ms": observation["captured_at_ms"],
                "valid_for_ms": observation["valid_for_ms"], "observation_id": observation["message_id"],
                "text": "Pessoa", "directional": False}


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to run end-to-end checks")
class EndToEndTests(unittest.TestCase):
    def harness(self, **options):
        from sonar_vision_integration.server import Harness

        directory = self.enterContext(TemporaryDirectory())
        return self.enterContext(Harness(Path(directory), **options))

    def client(self, harness, device="glasses-01", token=None, ca=None, **options):
        from sonar_vision_integration.client import DeviceClient

        client = DeviceClient(harness.url, harness.tokens[device] if token is None else token,
                              ca or harness.tls["ca"], **options)
        self.addCleanup(client.close)
        return client

    def discarded(self, call, reason, status=None):
        from sonar_vision_integration.client import Discarded

        with self.assertRaises(Discarded) as caught:
            call()
        self.assertEqual(caught.exception.reason, reason)
        if status is not None:
            self.assertEqual(caught.exception.status, status)

    def raw_post(self, harness, body, content_type, token):
        import httpx2

        context = ssl.create_default_context(cafile=str(harness.tls["ca"]))
        with httpx2.Client(verify=context, timeout=2.0) as http:
            return http.post(f"{harness.url}/v1/inference", content=body,
                             headers={"Authorization": f"Bearer {token}", "Content-Type": content_type})

    def wait_idle(self, harness, seconds=5):
        deadline = time.monotonic() + seconds
        while harness.service._busy and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(harness.service._busy)

    # ----- flow ----------------------------------------------------------
    def test_capture_api_tracker_response(self):
        harness = self.harness()
        client = self.client(harness)
        capture = client.capture(jpeg())
        data = client.send(capture)
        observation = data["observation"]
        self.assertIsNone(data["audio"])
        self.assertEqual((observation["session_id"], observation["frame_id"],
                          observation["captured_at_ms"]),
                         (capture.session_id, capture.frame_id, capture.captured_at_ms))
        self.assertEqual(observation["objects"][0]["track_id"], "1")
        request = harness.log.of("inference_request")[-1]
        self.assertEqual((request["status"], request["device_id"]), (200, "glasses-01"))
        for key in ("read_ms", "inference_ms", "total_ms"):
            self.assertIn(key, request)

    def test_audio_suggestion_reaches_local_arbitration(self):
        from sonar_vision_local_audio.arbiter import Arbiter, Suggestion
        from sonar_vision_local_audio.catalog import CANDIDATE_PROFILE, check_catalog
        from sonar_vision_local_audio.examples import build, load

        examples = Path(__file__).resolve().parents[1] / "docs" / "protocol" / "exemplos-audio-local.json"
        catalog = check_catalog(*build(load(examples)), CANDIDATE_PROFILE)
        harness = self.harness(policy_factory=SpeakPolicy)
        client = self.client(harness)

        def arbitrate(urgent):
            capture = client.capture(jpeg())
            audio = client.send(capture)["audio"]
            arbiter = Arbiter(catalog, client.session_id, dict(client.records), lambda c: 0.0)
            if urgent:
                arbiter.urgency(client.clock(), True)
            fields = {k: audio[k] for k in ("message_id", "session_id", "frame_id", "captured_at_ms",
                                            "valid_for_ms", "text", "directional")}
            arbiter.suggestion(client.clock(), Suggestion(**fields))
            return arbiter.log

        self.assertEqual(arbitrate(False)[-1], ("start", "visual.person.unknown.unknown.none"))
        self.assertEqual(arbitrate(True)[-1][2], "urgent_active")

    # ----- credentials and certificates ----------------------------------
    def test_missing_and_invalid_credentials(self):
        harness = self.harness()
        for token in ("", "not-a-device-token"):
            client = self.client(harness, token=token)
            self.discarded(lambda: client.send(client.capture(jpeg())), "unauthorized", 401)
        self.assertEqual(harness.control.calls, 0)

    def test_untrusted_ca_and_wrong_hostname_fail_closed(self):
        from sonar_vision_api.dev_tls import create

        harness = self.harness()
        other = create(Path(self.enterContext(TemporaryDirectory())), ("localhost",))
        client = self.client(harness, ca=other["ca"])
        self.discarded(lambda: client.send(client.capture(jpeg())), "tls")
        wrong_name = self.harness(cert_names=("vm.example.test",))
        client = self.client(wrong_name)
        self.discarded(lambda: client.send(client.capture(jpeg())), "tls")
        self.assertEqual(harness.control.calls + wrong_name.control.calls, 0)

    # ----- payload and fields --------------------------------------------
    def test_payload_limits_and_incorrect_fields(self):
        harness = self.harness(max_body_bytes=8192, max_pixels=640 * 480)
        client = self.client(harness)
        self.discarded(lambda: client.send(client.capture(jpeg() + b"\x00" * 9000)),
                       "payload_too_large", 413)
        self.discarded(lambda: client.send(client.capture(jpeg(481, 640))), "payload_too_large", 413)
        token = harness.tokens["glasses-01"]
        for meta in (metadata(extra=1), metadata(frame_id="01"), metadata(captured_at_ms=-1)):
            body, ctype = multipart(meta, jpeg())
            response = self.raw_post(harness, body, ctype, token)
            self.assertEqual((response.status_code, response.json()["error"]["code"]),
                             (400, "invalid_request"))
        body, ctype = multipart(metadata(), jpeg(), image_type="image/png")
        self.assertEqual(self.raw_post(harness, body, ctype, token).status_code, 415)
        self.assertEqual(harness.control.calls, 0)

    # ----- sessions ------------------------------------------------------
    def test_expired_session_reopens_with_new_epoch(self):
        harness = self.harness(idle_seconds=0.2)
        client = self.client(harness)
        first = client.send(client.capture(jpeg()))["observation"]["tracker_epoch"]
        time.sleep(0.3)
        second = client.send(client.capture(jpeg()))["observation"]["tracker_epoch"]
        self.assertNotEqual(first, second)

    def test_mixed_sessions_and_devices_stay_isolated(self):
        harness = self.harness()
        a, b = self.client(harness, "glasses-01"), self.client(harness, "glasses-02")
        b.session_id = a.session_id  # same session id on two devices
        reply_a = a.send(a.capture(jpeg()))
        reply_b = b.send(b.capture(jpeg()))
        self.assertNotEqual(reply_a["observation"]["tracker_epoch"],
                            reply_b["observation"]["tracker_epoch"])
        old = a.capture(jpeg())
        old_body = self.raw_post(harness, *multipart(metadata(old.session_id, old.frame_id,
                                                              old.captured_at_ms), jpeg()),
                                 harness.tokens["glasses-01"]).content
        a.restart()  # reboot: replies for the previous session are rejected
        self.discarded(lambda: a.admit(old_body), "session_mismatch")
        self.discarded(lambda: b.admit(old_body), "capture_mismatch")

    # ----- timeout, busy, disconnection, cancellation --------------------
    def test_timeout_then_busy_without_accumulating_frames(self):
        harness = self.harness()
        harness.control.gate = Event()
        slow = self.client(harness, "glasses-01", timeout_s=0.5)
        other = self.client(harness, "glasses-02")
        self.discarded(lambda: slow.send(slow.capture(jpeg())), "timeout")
        # Inference still running on the server: a new device gets busy, nothing is queued.
        self.discarded(lambda: other.send(other.capture(jpeg())), "busy", 429)
        self.assertEqual(harness.control.calls, 1)
        time.sleep(1.2)  # server-side 1500 ms budget expires: wait abandoned
        harness.control.gate.set()
        self.wait_idle(harness)
        self.assertEqual(harness.service.counters["abandoned"], 1)
        self.assertTrue(harness.log.of("abandoned_work_finished"))
        harness.control.gate = None
        other.send(other.capture(jpeg()))
        self.assertEqual(harness.control.calls, 2)

    def test_one_active_request_per_device_on_client(self):
        from sonar_vision_integration.client import ClientBusy

        harness = self.harness()
        harness.control.gate = Event()
        client = self.client(harness)
        worker = Thread(target=lambda: self._swallow(client))
        worker.start()
        time.sleep(0.2)
        with self.assertRaises(ClientBusy):
            client.send(client.capture(jpeg()))
        harness.control.gate.set()
        worker.join(5)
        self.assertEqual(len(harness.log.of("inference_request")), 1)

    @staticmethod
    def _swallow(client):
        try:
            client.send(client.capture(jpeg()))
        except Exception:
            pass

    def test_disconnection_is_reported_without_retry(self):
        harness = self.harness()
        client = self.client(harness)
        client.send(client.capture(jpeg()))
        harness.stop()
        from sonar_vision_integration.client import Discarded

        with self.assertRaises(Discarded) as caught:
            client.send(client.capture(jpeg()))
        # Refused connections surface as "connect" on Linux; Windows retries the
        # SYN to a closed loopback port until the 2 s client timeout instead.
        self.assertIn(caught.exception.reason, ("connect", "timeout", "disconnected"))
        self.assertEqual(harness.control.calls, 1)  # the lost capture is never resent

    def test_client_cancellation_does_not_free_the_slot_early(self):
        harness = self.harness()
        harness.control.gate = Event()
        body, ctype = multipart(metadata("boot", "0", 0), jpeg())
        request = (f"POST /v1/inference HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                   f"Authorization: Bearer {harness.tokens['glasses-01']}\r\n"
                   f"Content-Type: {ctype}\r\nContent-Length: {len(body)}\r\n\r\n").encode() + body
        context = ssl.create_default_context(cafile=str(harness.tls["ca"]))
        with socket.create_connection(("127.0.0.1", harness.port)) as raw:
            with context.wrap_socket(raw, server_hostname="127.0.0.1") as tls:
                tls.sendall(request)
                time.sleep(0.2)  # inference started; now the client goes away
        other = self.client(harness, "glasses-02")
        self.discarded(lambda: other.send(other.capture(jpeg())), "busy", 429)
        harness.control.gate.set()
        self.wait_idle(harness)
        harness.control.gate = None
        other.send(other.capture(jpeg()))

    # ----- duplicate, expired and out-of-order responses -----------------
    def test_duplicate_expired_and_out_of_order_responses(self):
        harness = self.harness()
        now = [10_000]
        client = self.client(harness, clock=lambda: now[0])
        token = harness.tokens["glasses-01"]

        def reply(capture):
            meta = metadata(capture.session_id, capture.frame_id, capture.captured_at_ms)
            return self.raw_post(harness, *multipart(meta, jpeg()), token).content

        first, second = client.capture(jpeg()), client.capture(jpeg())
        body_first, body_second = reply(first), reply(second)
        client.admit(body_second)
        self.discarded(lambda: client.admit(body_second), "duplicate")
        self.discarded(lambda: client.admit(body_first), "out_of_order")
        late = client.capture(jpeg())
        body_late = reply(late)
        now[0] += 1000  # age == 1000 ms since capture: expired
        self.discarded(lambda: client.admit(body_late), "expired")
        # Server side: resending an already processed frame is rejected.
        self.assertEqual(self.raw_post(harness, *multipart(
            metadata(late.session_id, late.frame_id, late.captured_at_ms), jpeg()), token).status_code, 400)

    # ----- tactile independence ------------------------------------------
    def test_api_lockup_does_not_block_simulated_tactile_path(self):
        from sonar_vision_integration.tactile import run_independence

        harness = self.harness()
        harness.control.gate = Event()
        client = self.client(harness)
        report = run_independence(lambda: client.send(client.capture(jpeg())))
        harness.control.gate.set()
        self.assertIsNotNone(report["obstacle_to_vibration_ms"])
        self.assertTrue(report["network_still_blocked_at_vibration"])
        self.assertLess(report["obstacle_to_vibration_ms"], 250)  # generous: desktop scheduler

    # ----- benchmark report ----------------------------------------------
    def test_benchmark_report_separates_environment_numbers(self):
        from sonar_vision_integration.bench import run

        report = run(3)
        self.assertEqual(report["kind"], "environment_dependent_benchmark")
        self.assertEqual(report["backend"], "simulated")
        self.assertEqual(report["outcomes"], {"admitted": 3})
        self.assertEqual(report["client_round_trip"]["samples"], 3)
        self.assertEqual(report["server_statuses"], {"200": 3})
        self.assertIn("fastapi", report["environment"]["packages"])


class TactileWithoutApiTests(unittest.TestCase):
    """Standard library only: runs in every CI job."""

    def test_loop_does_not_shadow_thread_internals(self):
        # Python 3.11 Thread.join() calls self._stop(); an Event there breaks join().
        from sonar_vision_integration.tactile import TactileLoop

        loop = TactileLoop(lambda: 3.0, period_s=0.005)
        self.assertNotIn("_stop", vars(loop))
        loop.start()
        loop.stop()
        self.assertFalse(loop.is_alive())

    def test_network_lockup_does_not_block_simulated_tactile_path(self):
        from sonar_vision_integration.tactile import blocking_socket_call, hung_endpoint, run_independence

        with hung_endpoint() as address:
            report = run_independence(blocking_socket_call(address, timeout_s=1.0))
        self.assertEqual(report["kind"], "independent_simulation_not_hardware")
        self.assertIsNotNone(report["obstacle_to_vibration_ms"])
        self.assertTrue(report["network_still_blocked_at_vibration"])
        self.assertGreaterEqual(report["network_blocked_ms"], 900)
        self.assertLess(report["obstacle_to_vibration_ms"], 250)


if __name__ == "__main__":
    unittest.main()
