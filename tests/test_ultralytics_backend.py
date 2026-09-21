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


if __name__ == "__main__":
    unittest.main()
