from importlib.util import find_spec
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from sonar_vision.preview import parse_args, selected_frame, video_timestamp_ms


class PreviewTests(unittest.TestCase):
    def test_sampling_preserves_original_timeline(self):
        indices = [i for i in range(10) if selected_frame(i, stride=2, drop_every=3)]
        self.assertEqual(indices, [0, 4, 6])
        self.assertEqual([video_timestamp_ms(i, 30) for i in indices], [0, 133, 200])
        for fps in (0, -1, float("nan")):
            with self.assertRaises(ValueError):
                video_timestamp_ms(1, fps)

    def test_cli_does_not_assume_fixed_camera(self):
        args = parse_args(["--weights", "model.pt", "--video", "clip.mp4"])
        self.assertFalse(args.assume_fixed_camera)
        self.assertFalse(args.headless)
        self.assertEqual(args.stride, 1)

    @unittest.skipUnless(find_spec("cv2") and find_spec("numpy"), "vision extras required")
    def test_draws_boxes_and_ids_without_modifying_image(self):
        import numpy as np
        from sonar_vision.core import Detection, Frame, VisionService
        from sonar_vision.preview import draw_overlay

        class Backend:
            def infer(self, image):
                return [Detection("person", .9, (.1, .1, .6, .9), "7")]
            def close(self):
                pass

        service = VisionService(Backend)
        service.open("a", "s")
        source = np.zeros((480, 640, 3), dtype=np.uint8)
        result = service.process(Frame("a", "s", "0", 0, source))
        output = draw_overlay(source, result, camera_motion="unknown")
        self.assertFalse(source.any())
        self.assertTrue(output.any())
        self.assertEqual(output.shape[1], 640)
        self.assertGreater(output.shape[0], source.shape[0])
        service.close("a", "s")

    @unittest.skipUnless(all(find_spec(n) for n in ("cv2", "numpy", "ultralytics", "lap")),
                         "vision extras required")
    def test_headless_loop_releases_source_and_preserves_capture_times(self):
        import numpy as np
        from sonar_vision.preview import main
        from sonar_vision.core import Detection

        class Capture:
            released = False
            index = 0
            def isOpened(self):
                return True
            def get(self, key):
                return 30.0
            def read(self):
                self.index += 1
                return (True, np.zeros((100, 100, 3), dtype=np.uint8)) if self.index <= 6 else (False, None)
            def release(self):
                self.released = True

        class Backend:
            def infer(self, image):
                return [Detection("person", .9, (.1, .1, .5, .9), "1")]
            def close(self):
                pass

        class Factory:
            metadata = {"model": "fixture"}
            def __call__(self):
                return Backend()

        capture = Capture()
        stdout = io.StringIO()
        with patch("sonar_vision.ultralytics_backend.UltralyticsFactory", return_value=Factory()), \
             patch("sonar_vision.preview.Path.is_file", return_value=True), \
             patch("cv2.VideoCapture", return_value=capture), \
             patch("cv2.imshow") as show, contextlib.redirect_stdout(stdout):
            main(["--weights", "fixture.pt", "--video", "fixture.mp4", "--stride", "2",
                  "--drop-every", "3", "--headless"])
        report = json.loads(stdout.getvalue())
        self.assertTrue(capture.released)
        show.assert_not_called()
        self.assertEqual(report["processed_frames"], 2)
        self.assertEqual(report["skipped_frames"], 4)
        self.assertEqual(report["camera_motion_assumption"], "unknown")
        self.assertEqual(report["stop_reason"], "end_or_decode_failure")


if __name__ == "__main__":
    unittest.main()
