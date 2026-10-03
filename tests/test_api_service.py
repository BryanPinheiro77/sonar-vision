"""#24 admission, sessions, timeout and policy seam without HTTP."""

import asyncio
import json
import logging
from threading import Event
import time
import unittest

from sonar_vision.benchmark import SyntheticBackend
from sonar_vision.core import Detection, VisionService
from sonar_vision_api.errors import ApiError
from sonar_vision_api.service import InferenceService, header_only_decoder
from sonar_vision_api.validation import Metadata

logging.getLogger("sonar_vision_api").setLevel(logging.CRITICAL)


class BlockingBackend:
    """Holds the worker until released, to exercise busy/timeout paths."""

    def __init__(self, gate):
        self.gate = gate

    def infer(self, image):
        self.gate.wait(5)
        return [Detection("person", 0.9, (0.1, 0.2, 0.3, 0.8), "1")]

    def close(self):
        pass


class FailingBackend:
    def infer(self, image):
        raise RuntimeError("detector exploded")

    def close(self):
        pass


class RecordingPolicy:
    calls = []

    def __init__(self, session_id):
        self.session_id = session_id

    def select(self, observation, *, capture_age_lower_bound_ms):
        RecordingPolicy.calls.append((self.session_id, capture_age_lower_bound_ms))
        return {"version": "0.1", "type": "audio_suggestion",
                "session_id": observation["session_id"], "message_id": "a-" + observation["frame_id"],
                "frame_id": observation["frame_id"], "captured_at_ms": observation["captured_at_ms"],
                "valid_for_ms": observation["valid_for_ms"],
                "observation_id": observation["message_id"], "text": "Pessoa",
                "directional": False}


class BrokenPolicy:
    def __init__(self, session_id):
        pass

    def select(self, observation, *, capture_age_lower_bound_ms):
        return {"text": "não é uma sugestão válida"}


def run(coro):
    return asyncio.run(coro)


class ServiceTests(unittest.TestCase):
    def make(self, factory=SyntheticBackend, timeout_ms=1500, policy=None):
        vision = VisionService(factory)
        kwargs = {"policy_factory": policy} if policy else {}
        service = InferenceService(vision, header_only_decoder, timeout_ms=timeout_ms, **kwargs)
        self.addCleanup(service.close)
        return service, vision

    def call(self, service, device="glasses-01", session="boot-1", frame="1",
             captured=1000, shape=(480, 640), timings=None):
        return run(service.infer(device, Metadata(session, frame, captured), b"jpeg", shape,
                                 service.clock(), {} if timings is None else timings))

    def status(self, *args, **kwargs):
        with self.assertRaises(ApiError) as caught:
            self.call(*args, **kwargs)
        return caught.exception.status

    def test_success_returns_contract_body_with_null_audio(self):
        service, _ = self.make()
        timings = {}
        body = json.loads(self.call(service, timings=timings))
        self.assertIsNone(body["audio"])
        self.assertEqual(body["observation"]["session_id"], "boot-1")
        self.assertEqual(body["observation"]["frame_id"], "1")
        self.assertEqual(body["observation"]["captured_at_ms"], 1000)
        for key in ("decode_ms", "inference_ms", "policy_ms", "encode_ms", "work_ms"):
            self.assertIn(key, timings)

    def test_replay_and_clock_regression_are_rejected(self):
        service, _ = self.make()
        self.call(service, frame="5", captured=1000)
        self.assertEqual(self.status(service, frame="5", captured=1000), 400)
        self.assertEqual(self.status(service, frame="4", captured=2000), 400)
        self.assertEqual(self.status(service, frame="6", captured=999), 400)
        self.call(service, frame="6", captured=1000)

    def test_devices_and_sessions_are_isolated(self):
        service, vision = self.make()
        a = json.loads(self.call(service, device="a", session="same"))["observation"]
        b = json.loads(self.call(service, device="b", session="same"))["observation"]
        self.assertNotEqual(a["tracker_epoch"], b["tracker_epoch"])
        # Same frame number is fine for another device: watermarks are per device session.
        self.assertEqual(len(vision._sessions), 2)

    def test_new_session_from_same_device_replaces_previous(self):
        service, vision = self.make()
        first = json.loads(self.call(service, session="boot-1", frame="9"))["observation"]
        second = json.loads(self.call(service, session="boot-2", frame="0"))["observation"]
        self.assertNotEqual(first["tracker_epoch"], second["tracker_epoch"])
        self.assertEqual(list(vision._sessions), [("glasses-01", "boot-2")])
        self.assertEqual(service.counters["session_replaced"], 1)

    def test_resolution_change_resets_tracker_instead_of_failing(self):
        service, _ = self.make()
        first = json.loads(self.call(service, frame="1", shape=(480, 640)))["observation"]
        second = json.loads(self.call(service, frame="2", shape=(240, 320)))["observation"]
        self.assertNotEqual(first["tracker_epoch"], second["tracker_epoch"])
        self.assertEqual(service.counters["resolution_reset"], 1)

    def test_backend_failure_is_internal_and_keeps_replay_watermark(self):
        service, _ = self.make(factory=FailingBackend)
        self.assertEqual(self.status(service, frame="3"), 500)
        # The failed frame was consumed; replaying it is still rejected.
        self.assertEqual(self.status(service, frame="3"), 400)
        self.assertEqual(self.status(service, frame="4"), 500)

    def test_idle_expiry_reopens_with_new_epoch(self):
        service, vision = self.make()
        first = json.loads(self.call(service, frame="1"))["observation"]
        vision.close("glasses-01", "boot-1")  # same effect as idle expiry
        second = json.loads(self.call(service, frame="2"))["observation"]
        self.assertNotEqual(first["tracker_epoch"], second["tracker_epoch"])
        self.assertEqual(service.counters["session_reopened"], 1)

    def test_concurrent_request_gets_busy_without_queue(self):
        gate = Event()
        service, _ = self.make(factory=lambda: BlockingBackend(gate))

        async def scenario():
            first = asyncio.create_task(service.infer(
                "a", Metadata("s", "1", 1), b"", (1, 1), service.clock(), {}))
            await asyncio.sleep(0.05)
            with self.assertRaises(ApiError) as caught:
                await service.infer("b", Metadata("s", "1", 1), b"", (1, 1), service.clock(), {})
            self.assertEqual(caught.exception.status, 429)
            gate.set()
            await first

        run(scenario())
        self.assertEqual(service.counters["busy"], 1)

    def test_timeout_abandons_wait_but_keeps_slot_until_work_ends(self):
        gate = Event()
        service, _ = self.make(factory=lambda: BlockingBackend(gate), timeout_ms=50)
        timings = {}
        with self.assertRaises(ApiError) as caught:
            self.call(service, timings=timings)
        self.assertEqual(caught.exception.status, 503)
        self.assertTrue(timings["abandoned"])
        # Inference is still running: the server reports busy instead of queueing.
        self.assertEqual(self.status(service, device="other"), 429)
        gate.set()
        deadline = time.monotonic() + 2
        while service._busy and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(service._busy)
        self.assertEqual(service.counters["abandoned"], 1)

    def test_expired_deadline_is_rejected_before_admission(self):
        service, _ = self.make()
        with self.assertRaises(ApiError) as caught:
            run(service.infer("a", Metadata("s", "1", 1), b"", (1, 1),
                              service.clock() - 10, {}))
        self.assertEqual(caught.exception.status, 503)
        self.assertFalse(service._busy)

    def test_policy_suggestion_is_validated_and_sent(self):
        RecordingPolicy.calls.clear()
        service, _ = self.make(policy=RecordingPolicy)
        body = json.loads(self.call(service))
        self.assertEqual(body["audio"]["observation_id"], body["observation"]["message_id"])
        session_id, age = RecordingPolicy.calls[0]
        self.assertEqual(session_id, "boot-1")
        self.assertGreaterEqual(age, 0)

    def test_invalid_policy_output_keeps_observation(self):
        service, _ = self.make(policy=BrokenPolicy)
        body = json.loads(self.call(service))
        self.assertIsNone(body["audio"])
        self.assertEqual(service.counters["audio_rejected"], 1)


if __name__ == "__main__":
    unittest.main()
