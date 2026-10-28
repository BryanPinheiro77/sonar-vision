"""Real ByteTrack tests with fabricated boxes: no weights, downloads or people."""

from importlib.util import find_spec
from types import SimpleNamespace
import unittest

AVAILABLE = all(find_spec(name) for name in ("ultralytics", "numpy", "lap"))


@unittest.skipUnless(AVAILABLE, "install .[vision] to exercise real ByteTrack")
class ByteTrackTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from ultralytics.engine.results import Boxes
        from sonar_vision.ultralytics_backend import UltralyticsBackend, VisionConfig
        self.np = np
        self.image = np.zeros((200, 300, 3), dtype=np.uint8)
        self.rows = [[10, 10, 60, 150, 0.9, 0]]

        def predict(image):
            return SimpleNamespace(boxes=Boxes(np.array(self.rows, dtype=np.float32).reshape(-1, 6),
                                               image.shape[:2]), names={0: "person", 1: "dining table"})

        self.make = lambda: UltralyticsBackend(predict, VisionConfig())
        self.a = self.make()

    def test_stable_then_lost_and_recovered(self):
        first = self.a.infer(self.image)
        self.assertEqual(first[0].track_id, "1")
        self.assertAlmostEqual(first[0].box[2], 0.2)
        self.rows = []
        self.assertEqual(self.a.infer(self.image), [])
        self.rows = [[10, 10, 60, 150, 0.9, 0]]
        self.assertEqual(self.a.infer(self.image)[0].track_id, "1")

    def test_interleaved_trackers_have_independent_id_counters(self):
        self.assertEqual(self.a.infer(self.image)[0].track_id, "1")
        b = self.make()  # must not reset the counter in a
        self.assertEqual(b.infer(self.image)[0].track_id, "1")
        self.rows.append([180, 10, 250, 150, 0.9, 1])
        unconfirmed = self.a.infer(self.image)
        self.assertIsNone(unconfirmed[1].track_id)
        self.assertEqual([d.track_id for d in self.a.infer(self.image)], ["1", "2"])
        self.assertEqual(self.a.infer(self.image)[1].class_name, "dining_table")
        self.rows = [[10, 10, 60, 150, 0.9, 0]]
        self.assertEqual(b.infer(self.image)[0].track_id, "1")
        b.close()
        self.assertEqual(self.a.infer(self.image)[0].track_id, "1")

    def test_shape_change_requires_explicit_reset(self):
        self.a.infer(self.image)
        with self.assertRaises(ValueError):
            self.a.infer(self.np.zeros((100, 100, 3), dtype=self.np.uint8))

    def test_bad_images_and_closed_backend(self):
        with self.assertRaises(ValueError):
            self.a.infer(None)
        self.a.close()
        with self.assertRaises(RuntimeError):
            self.a.infer(self.image)

    def test_weak_detections_maintain_id_without_becoming_output(self):
        self.assertEqual(self.a.infer(self.image)[0].track_id, "1")
        self.rows[0][4] = 0.3
        for _ in range(65):  # longer than the lost-track retention buffer
            self.assertEqual(self.a.infer(self.image), [])
        self.rows[0][4] = 0.9
        self.assertEqual(self.a.infer(self.image)[0].track_id, "1")

    def test_weak_detections_cannot_create_new_ids(self):
        self.rows[0][4] = 0.3
        for _ in range(3):
            self.assertEqual(self.a.infer(self.image), [])
        self.rows[0][4] = 0.9
        self.assertIsNone(self.a.infer(self.image)[0].track_id)
        self.assertEqual(self.a.infer(self.image)[0].track_id, "1")

    def test_raising_output_cutoff_also_raises_new_track_cutoff(self):
        from sonar_vision.ultralytics_backend import UltralyticsBackend, VisionConfig
        backend = UltralyticsBackend(self.a._predict, VisionConfig(confidence=0.6))
        self.rows[0][4] = 0.5
        for _ in range(3):
            self.assertEqual(backend.infer(self.image), [])
        self.rows[0][4] = 0.9
        self.assertIsNone(backend.infer(self.image)[0].track_id)
        self.assertEqual(backend.infer(self.image)[0].track_id, "1")

    def test_ambiguous_lost_track_does_not_beat_active_track(self):
        from sonar_vision.ultralytics_backend import _guard_reactivation_costs
        tracks = [SimpleNamespace(state=2, cls=0), SimpleNamespace(state=1, cls=0)]
        costs = self.np.array([[0.6646], [0.6660]], dtype=self.np.float32)
        guarded = _guard_reactivation_costs(
            costs, tracks, [SimpleNamespace(cls=0)], 0.8, 0.02)
        self.assertGreater(guarded[0, 0], 0.8)
        self.assertEqual(guarded[1, 0], costs[1, 0])
        self.assertLess(costs[0, 0], 0.8)  # input is never mutated

    def test_two_ambiguous_lost_tracks_both_abstain(self):
        from sonar_vision.ultralytics_backend import _guard_reactivation_costs
        tracks = [SimpleNamespace(state=2, cls=0), SimpleNamespace(state=2, cls=0)]
        guarded = _guard_reactivation_costs(
            self.np.array([[0.7373], [0.7387]]), tracks,
            [SimpleNamespace(cls=0)], 0.8, 0.02)
        self.assertTrue((guarded > 0.8).all())

    def test_decisive_recovery_and_different_class_rival_are_preserved(self):
        from sonar_vision.ultralytics_backend import _guard_reactivation_costs
        for costs, classes in [([[0.5], [0.7]], [0, 0]),
                               ([[0.6646], [0.6660]], [0, 1])]:
            costs = self.np.array(costs)
            tracks = [SimpleNamespace(state=state, cls=cls)
                      for state, cls in zip([2, 1], classes)]
            guarded = _guard_reactivation_costs(
                costs, tracks, [SimpleNamespace(cls=0)], 0.8, 0.02)
            self.np.testing.assert_array_equal(guarded, costs)

    def test_zero_margin_and_empty_matrices_preserve_original_costs(self):
        from sonar_vision.ultralytics_backend import _guard_reactivation_costs
        tracks = [SimpleNamespace(state=2, cls=0), SimpleNamespace(state=1, cls=0)]
        costs = self.np.array([[0.5], [0.5]])
        self.assertIs(_guard_reactivation_costs(
            costs, tracks, [SimpleNamespace(cls=0)], 0.8, 0), costs)
        empty = self.np.empty((2, 0))
        self.assertIs(_guard_reactivation_costs(empty, tracks, [], 0.8, 0.02), empty)


class VisionConfigTests(unittest.TestCase):
    def test_existing_positional_arguments_keep_their_meaning(self):
        from sonar_vision.ultralytics_backend import VisionConfig
        config = VisionConfig(0.35, 640, "cpu", 0.25, 0.1, 0.25, 60, 0.8, True, 300)
        self.assertEqual((config.track_high_thresh, config.track_low_thresh,
                          config.new_track_thresh, config.track_buffer,
                          config.match_thresh, config.fuse_score,
                          config.max_detections), (0.25, 0.1, 0.25, 60, 0.8, True, 300))

    def test_invalid_association_parameters_are_rejected(self):
        from sonar_vision.ultralytics_backend import VisionConfig
        for field in ("association_confidence", "reactivation_margin"):
            for value in (-0.1, 1.1, float("nan"), float("inf")):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    VisionConfig(**{field: value})

    def test_general_detector_uses_weak_cutoff_but_stair_specialist_does_not(self):
        from threading import Lock
        from sonar_vision.ultralytics_backend import UltralyticsFactory, VisionConfig
        calls = []
        model = SimpleNamespace(predict=lambda image, **kwargs: calls.append(kwargs) or [None])
        factory = object.__new__(UltralyticsFactory)
        factory.config = VisionConfig()
        factory._lock = Lock()
        factory._model = factory._direction_model = model
        factory._predict(None)
        factory._predict_stairs(None)
        self.assertEqual([call["conf"] for call in calls], [0.25, 0.35])


if __name__ == "__main__":
    unittest.main()
