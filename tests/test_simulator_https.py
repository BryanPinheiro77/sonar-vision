"""#30 client against #24 HTTPS, reusing #27; scripted backend, no camera."""
from copy import deepcopy
from importlib.util import find_spec
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest

from sonar_vision.audio import AudioConfig, NAMES
from sonar_vision.simulator import (
    Capture, FixtureSource, HTTPS, LocalState, Orientation, Rejected, Simulator,
)
from sonar_vision_api.policy import audio_policy_factory

AVAILABLE = all(find_spec(n) for n in ("fastapi", "uvicorn", "trustme", "python_multipart"))


def experimental_config():
    # Existing unit-test profile, NOT approved operational or risk thresholds.
    return AudioConfig(0.5, 2000, 10000, 30000, 32, 32, tuple(NAMES))


class PolicyFactoryTests(unittest.TestCase):
    def test_explicit_configuration_and_independent_state(self):
        from test_audio import observation, obj

        with self.assertRaises(TypeError):
            audio_policy_factory(None)
        factory = audio_policy_factory(experimental_config(), clock=lambda: 0)
        first, second = factory("s"), factory("s")
        value = observation(1, [obj(direction="unknown")])
        suggestion = first.select(value, capture_age_lower_bound_ms=0)
        self.assertEqual(suggestion["observation_id"], value["message_id"])
        self.assertEqual(suggestion["text"], "Pessoa")
        self.assertIsNotNone(second.select(value, capture_age_lower_bound_ms=0))
        self.assertIsNone(first.select(observation(2, [obj(direction="unknown")]),
                                       capture_age_lower_bound_ms=0))
        self.assertIsNone(factory("s").select(value, capture_age_lower_bound_ms=1000))


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to exercise simulator HTTPS")
class SimulatorHttpsTests(unittest.TestCase):
    def setUp(self):
        from sonar_vision_integration.server import Harness

        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.server = self.enterContext(Harness(
            Path(self.directory.name),
            policy_factory=audio_policy_factory(experimental_config()),
        ))
        self.client = Simulator()
        self.state = LocalState(Orientation.yaw(0))  # explicitly synthetic
        self.source = FixtureSource()  # original black 8x8 JPEG, no video
        self.transport = self.make_transport()

    def make_transport(self, device="glasses-01", *, ca=None, token=None):
        return HTTPS(self.server.url + "/v1/inference",
                     token if token is not None else self.server.tokens[device],
                     ca_file=str(ca or self.server.tls["ca"]))

    def exchange(self, *, client=None, transport=None, state=None):
        return (client or self.client).exchange(
            self.source, transport or self.transport, lambda: state or self.state)

    def test_suggestion_then_suppression_and_device_isolation(self):
        self.assertEqual(self.server.backend, "simulated")
        first = self.exchange()
        self.assertEqual((first["outcome"], first["audio"]), ("accepted", "accepted"))
        self.assertEqual(first["objects"][0]["direction"], "unknown")
        self.assertEqual(self.exchange()["audio"], "no_suggestion")
        other = Simulator()
        other.session_id = self.client.session_id
        self.assertEqual(self.exchange(client=other,
                                      transport=self.make_transport("glasses-02"))["audio"],
                         "accepted")
        devices = {e["device_id"] for e in self.server.log.of("inference_request")}
        self.assertEqual(devices, {"glasses-01", "glasses-02"})

    def test_real_response_references_duplicates_expiration_and_old_session(self):
        jpeg, timestamp = self.source.read(self.client.clock)
        capture = Capture(self.client.session_id, "0", timestamp, jpeg, self.state.orientation)
        body = self.transport.send(capture)
        value = json.loads(body)
        self.assertEqual(value["audio"]["observation_id"], value["observation"]["message_id"])
        bad = deepcopy(value)
        bad["observation"]["frame_id"] = "999"
        bad["audio"]["frame_id"] = "999"
        with self.assertRaisesRegex(Rejected, "capture_mismatch"):
            self.client.admit(json.dumps(bad).encode(), capture, self.state)
        bad = deepcopy(value)
        bad["audio"]["observation_id"] = "wrong"
        with self.assertRaises(Rejected):
            self.client.admit(json.dumps(bad).encode(), capture, self.state)
        self.assertEqual(self.client.admit(body, capture, self.state)["audio"], "accepted")
        with self.assertRaisesRegex(Rejected, "duplicate"):
            self.client.admit(body, capture, self.state)
        self.client.clock = lambda: timestamp + 1000  # synthetic age, real API body
        with self.assertRaisesRegex(Rejected, "expired"):
            self.client.admit(body, capture, self.state)
        self.client.restart()
        with self.assertRaisesRegex(Rejected, "session_mismatch"):
            self.client.admit(body, capture, self.state)

    def test_untrusted_ca_and_invalid_device_credential(self):
        from sonar_vision_api.dev_tls import create

        other = create(Path(self.directory.name) / "other")
        self.assertEqual(self.exchange(transport=self.make_transport(ca=other["ca"]))["reason"],
                         "tls_error")
        self.assertEqual(self.exchange(transport=self.make_transport(token="invalid"))["reason"],
                         "http_401")
        self.assertEqual(self.server.control.calls, 0)

    def test_default_policy_keeps_audio_null(self):
        from sonar_vision_api.policy import NullPolicy

        self.server.service.policy_factory = NullPolicy
        result = self.exchange()
        self.assertEqual(result["observation"], "accepted")
        self.assertEqual(result["audio"], "no_suggestion")

    def test_local_urgency_discards_audio_but_keeps_observation(self):
        result = self.exchange(state=LocalState(Orientation.yaw(0), True))
        self.assertEqual(result["observation"], "accepted")
        self.assertEqual(result["audio"], "local_urgent")

    def test_active_request_does_not_capture_or_queue_second_frame(self):
        gate = Event()
        self.server.control.gate = gate
        result = []
        worker = Thread(target=lambda: result.append(self.exchange()))
        worker.start()
        try:
            deadline = time.monotonic() + 1
            while not self.server.control.calls and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertEqual(self.server.control.calls, 1)
            counter = self.client.counter
            self.assertEqual(self.exchange()["reason"], "busy")
            self.assertEqual(self.client.counter, counter)
            other = Simulator()
            self.assertEqual(self.exchange(client=other)["reason"], "busy")
            self.assertEqual(other.counter, 0)
            self.assertEqual(self.server.control.calls, 1)
        finally:
            gate.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result[0]["outcome"], "accepted")

    def test_api_failure_keeps_tactile_simulation_independent(self):
        from sonar_vision_integration.tactile import run_independence

        self.server.control.fail = True
        self.server.control.delay_s = 0.7
        results = []
        report = run_independence(lambda: results.append(self.exchange()))
        self.assertEqual(results[0]["reason"], "http_500")
        self.assertTrue(report["network_still_blocked_at_vibration"])
        self.assertLess(report["obstacle_to_vibration_ms"], 250)


if __name__ == "__main__":
    unittest.main()
