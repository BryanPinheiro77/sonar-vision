import json
import threading
import unittest

from sonar_vision.core import Busy, Detection, Frame, SessionMissing, VisionService, normalize_class
from sonar_vision.benchmark import summarize


def detection(track="1", box=(0.1, 0.2, 0.3, 0.8), cls="person", confidence=0.9):
    return Detection(cls, confidence, box, track)


class FakeBackend:
    def __init__(self):
        self.closed = False

    def infer(self, image):
        if isinstance(image, Exception):
            raise image
        return image

    def close(self):
        self.closed = True


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.backends = []
        self.now = 0.0

        def factory():
            backend = FakeBackend()
            self.backends.append(backend)
            return backend

        self.service = VisionService(factory, history_size=2, missing_frames=2,
                                     max_sessions=2, max_tracks=20, clock=lambda: self.now)
        self.epoch = self.service.open("a", "s")

    def run_frame(self, n, detections=None, device="a", session="s", timestamp=None):
        return self.service.process(Frame(device, session, str(n),
                                         n * 33 if timestamp is None else timestamp,
                                         [detection()] if detections is None else detections))

    def test_stable_history_is_bounded_and_results_detached(self):
        first = self.run_frame(0)
        second = self.run_frame(1)
        last = self.run_frame(2)
        self.assertEqual(first.events, (("appeared", "1"),))
        self.assertEqual(second.events, ())
        self.assertEqual([s.frame_id for s in last.history["1"]], ["1", "2"])
        self.assertEqual(len(first.history["1"]), 1)
        self.assertEqual(last.tracker_epoch, first.tracker_epoch)
        self.assertNotEqual(first.message_id, last.message_id)

    def test_occlusion_lost_recovered_without_bridging_gap(self):
        self.run_frame(0)
        self.assertEqual(self.run_frame(1, []).events, (("lost", "1"),))
        returned = self.run_frame(2)
        self.assertEqual(returned.events, (("recovered", "1"),))
        self.assertEqual(len(returned.history["1"]), 1)

    def test_expiration_and_reentry_can_receive_new_id(self):
        self.run_frame(0)
        self.run_frame(1, [])
        self.run_frame(2, [])
        expired = self.run_frame(3, [])
        self.assertIn(("expired", "1"), expired.events)
        self.assertEqual(expired.history, {})
        self.assertEqual(self.run_frame(4, [detection("2")]).events, (("appeared", "2"),))

    def test_no_tracking_is_null_not_zero(self):
        result = self.run_frame(0, [detection(None)])
        self.assertIsNone(result.observation()["objects"][0]["track_id"])
        self.assertEqual(result.history, {})

    def test_two_devices_same_session_same_id_are_isolated(self):
        other_epoch = self.service.open("b", "s")
        a = self.run_frame(0)
        b = self.run_frame(0, [detection(box=(0.6, 0.1, 0.9, 0.8))], device="b")
        self.assertNotEqual(self.epoch, other_epoch)
        self.assertNotEqual(a.history["1"][0].box, b.history["1"][0].box)
        self.service.close("b", "s")
        self.assertEqual(self.run_frame(1).events, ())
        self.assertFalse(self.backends[0].closed)
        self.assertTrue(self.backends[1].closed)

    def test_two_sessions_same_device_are_isolated(self):
        self.service.open("a", "new")
        self.run_frame(1)
        self.assertEqual(self.run_frame(0, session="new").events, (("appeared", "1"),))

    def test_reset_changes_epoch_clears_history_preserves_frame_watermark(self):
        self.run_frame(1)
        new_epoch = self.service.reset("a", "s")
        self.assertNotEqual(new_epoch, self.epoch)
        self.assertTrue(self.backends[0].closed)
        with self.assertRaises(ValueError):
            self.run_frame(1)
        result = self.run_frame(2)
        self.assertEqual(result.events, (("appeared", "1"),))
        self.assertEqual(len(result.history["1"]), 1)

    def test_closed_session_rejects_until_explicit_open(self):
        self.service.close("a", "s")
        self.service.close("a", "s")
        with self.assertRaises(SessionMissing):
            self.run_frame(0)
        self.assertNotEqual(self.service.open("a", "s"), self.epoch)

    def test_idle_boundary_expires_session(self):
        self.now = 60
        with self.assertRaises(SessionMissing):
            self.run_frame(0)
        self.assertTrue(self.backends[0].closed)
        self.assertNotEqual(self.service.open("a", "s"), self.epoch)

    def test_session_capacity_and_reaping(self):
        self.service.open("b", "s")
        with self.assertRaises(Busy):
            self.service.open("c", "s")
        self.now = 60
        self.service.open("c", "s")
        self.assertTrue(all(b.closed for b in self.backends[:2]))

    def test_open_existing_session_does_not_reset_backend(self):
        self.run_frame(0)
        self.assertEqual(self.service.open("a", "s"), self.epoch)
        self.assertEqual(len(self.backends), 1)
        self.assertEqual(self.run_frame(1).events, ())

    def test_history_capacity_evicts_oldest(self):
        self.run_frame(0, [detection(str(i)) for i in range(20)])
        result = self.run_frame(1, [detection("new")])
        self.assertEqual(len(result.history), 20)
        self.assertIn(("evicted", "0"), result.events)
        self.assertIn("new", result.history)

    def test_frame_order_and_capture_regression_rejected_before_inference(self):
        self.run_frame(2)
        for n, timestamp in ((2, 66), (1, 67), (3, 65)):
            with self.assertRaises(ValueError):
                self.run_frame(n, timestamp=timestamp)
        self.assertEqual(self.run_frame(3).events, ())

    def test_failure_invalidates_tracker(self):
        with self.assertRaises(RuntimeError):
            self.run_frame(0, RuntimeError("failed"))
        with self.assertRaises(SessionMissing):
            self.run_frame(1)
        self.assertTrue(self.backends[0].closed)
        self.assertNotEqual(self.service.open("a", "s"), self.epoch)

    def test_duplicate_ids_fail_closed(self):
        with self.assertRaises(ValueError):
            self.run_frame(0, [detection(), detection()])
        with self.assertRaises(SessionMissing):
            self.run_frame(1)

    def test_object_limit_sorted_by_confidence(self):
        result = self.run_frame(0, [detection(str(i), confidence=i / 30) for i in range(30)])
        self.assertEqual(len(result.detections), 20)
        self.assertEqual(result.detections[0].track_id, "29")
        self.assertEqual(result.detections[-1].track_id, "10")
        self.assertLess(len(json.dumps({"observation": result.observation(), "audio": None}).encode()), 16384)

    def test_wire_contract_no_boxes_or_risk_or_fabricated_motion(self):
        result = self.run_frame(0, [detection(cls="stairs"), detection("2", cls="chair")])
        observation = result.observation()
        self.assertEqual(set(observation), {"version", "type", "session_id", "message_id", "frame_id",
                                          "captured_at_ms", "valid_for_ms", "tracker_epoch", "objects"})
        self.assertEqual(set(observation["objects"][0]), {"track_id", "class_name", "confidence",
                                                         "direction", "movement", "stair_direction"})
        self.assertEqual(observation["objects"][0]["stair_direction"], "unknown")
        self.assertIsNone(observation["objects"][1]["stair_direction"])
        self.assertTrue(all(o["movement"] == o["direction"] == "unknown" for o in observation["objects"]))
        self.assertEqual(observation["valid_for_ms"], 1000)

    def test_concurrent_calls_return_busy_instead_of_queue(self):
        entered, release = threading.Event(), threading.Event()
        errors = []
        original = self.backends[0].infer

        def slow(image):
            entered.set()
            release.wait(3)
            return original(image)

        self.backends[0].infer = slow

        def worker():
            try:
                self.run_frame(0)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            with self.assertRaises(Busy):
                self.run_frame(1)
            with self.assertRaises(Busy):
                self.service.close("a", "s")
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])


class ValidationTests(unittest.TestCase):
    def test_invalid_metadata(self):
        for frame_id in ("", "-1", "1.2", "01", "1" * 129):
            with self.assertRaises(ValueError):
                Frame("d", "s", frame_id, 0, None)
        for timestamp in (-1, True, 1.2, 2**53):
            with self.assertRaises(ValueError):
                Frame("d", "s", "0", timestamp, None)

    def test_invalid_detections(self):
        for score in (float("nan"), float("inf"), -0.1, 1.1, True, "0.8"):
            with self.assertRaises(ValueError):
                detection(confidence=score)
        for box in ((0, 0, 0, 1), (-0.1, 0, 1, 1), (0, 0, float("nan"), 1)):
            with self.assertRaises(ValueError):
                detection(box=box)

    def test_class_normalization_is_not_person_only(self):
        self.assertEqual(normalize_class("dining table"), "dining_table")
        self.assertEqual(normalize_class("traffic light"), "traffic_light")
        for name in ("person", "car", "dog", "chair", "bus", "bicycle", "motorcycle"):
            self.assertEqual(normalize_class(name), name)
        self.assertEqual(normalize_class("cat"), "unknown")

    def test_latency_metrics(self):
        stats = summarize([10, 30, 20, 40])
        self.assertEqual(stats["mean_ms"], 25)
        self.assertEqual(stats["p50_ms"], 20)
        self.assertEqual(stats["p95_ms"], 40)
        self.assertEqual(stats["p99_ms"], 40)
        self.assertEqual(summarize(range(1, 101))["p99_ms"], 99)
        for values in ([], [-1], [float("nan")]):
            with self.assertRaises(ValueError):
                summarize(values)


if __name__ == "__main__":
    unittest.main()
