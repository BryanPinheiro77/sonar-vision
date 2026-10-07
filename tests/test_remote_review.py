"""Private #52 receipt admission, capture reconstruction and disk failures."""

from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision.simulator import main, OpenCVSource
from sonar_vision_api.diagnostics import PredictionJournal
from sonar_vision_integration.review import add_overlays
import test_runtime_options as runtime_tests


class RemoteReviewTests(unittest.TestCase):
    def test_fixture_receipts_only_expose_admitted_audio(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "client.jsonl"
            with redirect_stdout(StringIO()):
                self.assertEqual(
                    main(
                        [
                            "--fixture",
                            "success",
                            "--frames",
                            "1",
                            "--urgent",
                            "--report",
                            str(path),
                        ]
                    ),
                    0,
                )
            header, row = map(json.loads, path.read_text().splitlines())
            self.assertEqual(header["local_inputs"], "simulated")
            self.assertEqual(row["outcome"], "accepted")
            self.assertEqual(row["audio"], "local_urgent")
            self.assertIsNone(row["audio_text"])
            self.assertIn("confidence", row["objects"][0])
            self.assertIn("observation_id", row)

    def test_diagnostic_queue_never_waits_and_disk_failure_drops_records(self):
        with TemporaryDirectory() as temp:
            result = runtime_tests.RuntimeTests.result(self)
            with patch("sonar_vision_api.diagnostics.Thread"):
                journal = PredictionJournal(Path(temp) / "full.jsonl", {}, capacity=1)
                journal.record(result, b"jpeg")
                journal.record(result, b"jpeg")
                self.assertEqual(journal._queue.qsize(), 1)
                self.assertEqual(journal.dropped, 1)
                journal._stream.close()
            journal = PredictionJournal(Path(temp) / "broken.jsonl", {})
            original = journal._stream

            class Broken:
                def write(self, line):
                    raise OSError("synthetic disk failure")

                def close(self):
                    original.close()

            journal._stream = Broken()
            journal.record(result, b"jpeg")
            journal.close()
            self.assertTrue(journal.failed)
            journal.record(result, b"jpeg")
            self.assertEqual(journal.dropped, 1)

    @unittest.skipUnless(importlib.util.find_spec("cv2"), "install .[vision]")
    def test_overlay_reconstructs_exact_upload_and_rejects_wrong_original(self):
        import cv2
        import numpy as np

        with TemporaryDirectory() as temp:
            root = Path(temp)
            video = root / "source.avi"
            writer = cv2.VideoWriter(
                str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (80, 40)
            )
            self.assertTrue(writer.isOpened())
            writer.write(np.zeros((40, 80, 3), dtype=np.uint8))
            writer.release()
            source = OpenCVSource(str(video), max_edge=40)
            try:
                jpeg, _ = source.read(lambda: 1000)
            finally:
                source.close()
            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(image.shape[:2], (20, 40))
            report = {
                "source": {
                    "video_sha256": sha256(video.read_bytes()).hexdigest(),
                    "upload_max_edge": 40,
                },
                "frames": [
                    {
                        "source_frame_index": 0,
                        "jpeg_sha256": sha256(jpeg).hexdigest(),
                        "diagnostic": {
                            "detections": [
                                {
                                    "box": [0.1, 0.1, 0.9, 0.9],
                                    "class_name": "person",
                                    "track_id": "1",
                                    "confidence": 0.9,
                                    "stair_direction": None,
                                }
                            ]
                        },
                    }
                ],
            }
            add_overlays(report, video, root / "images")
            self.assertTrue((root / report["frames"][0]["overlay"]).is_file())
            high_source = OpenCVSource(str(video), max_edge=40, jpeg_quality=100)
            try:
                high_jpeg, _ = high_source.read(lambda: 1000)
            finally:
                high_source.close()
            self.assertNotEqual(sha256(jpeg).hexdigest(), sha256(high_jpeg).hexdigest())
            report["frames"][0]["jpeg_sha256"] = sha256(high_jpeg).hexdigest()
            report["source"]["upload_jpeg_quality"] = 100
            add_overlays(report, video, root / "high-images")
            report["source"]["upload_jpeg_quality"] = 95
            with self.assertRaisesRegex(
                ValueError, "reconstructed_capture_hash_mismatch"
            ):
                add_overlays(report, video, root / "wrong-quality-images")
            report["source"]["video_sha256"] = "wrong"
            with self.assertRaisesRegex(ValueError, "video_hash_mismatch"):
                add_overlays(report, video, root / "other-images")


if __name__ == "__main__":
    unittest.main()
