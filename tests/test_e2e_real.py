"""#27 OPT-IN integration with the real detector (YOLO + ByteTrack).

Runs only when SONAR_E2E_WEIGHTS points to a trusted local .pt file and the
`vision`, `api` and `api-dev` extras are installed. Never downloads weights,
uses a camera or reaches external services. Not run by CI.
"""

from importlib.util import find_spec
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

WEIGHTS = os.environ.get("SONAR_E2E_WEIGHTS")
AVAILABLE = (WEIGHTS is not None and Path(WEIGHTS).is_file()
             and all(find_spec(n) for n in ("ultralytics", "cv2", "fastapi", "uvicorn", "httpx2", "trustme")))


@unittest.skipUnless(AVAILABLE, "opt-in: set SONAR_E2E_WEIGHTS and install .[vision,api,api-dev]")
class RealDetectorTests(unittest.TestCase):
    def test_synthetic_frames_through_real_detector(self):
        from sonar_vision_integration.bench import synthetic_jpeg
        from sonar_vision_integration.client import DeviceClient
        from sonar_vision_integration.server import Harness

        with TemporaryDirectory() as directory, Harness(Path(directory), weights=Path(WEIGHTS)) as harness:
            client = DeviceClient(harness.url, harness.tokens["glasses-01"], harness.tls["ca"])
            try:
                for _ in range(3):
                    observation = client.send(client.capture(synthetic_jpeg(real=True)))["observation"]
                    # Black frames: the contract allows an empty list; empty is not a free path.
                    self.assertLessEqual(len(observation["objects"]), 20)
            finally:
                client.close()
            self.assertEqual(harness.backend, "ultralytics")
            self.assertEqual({e["status"] for e in harness.log.of("inference_request")}, {200})

    def test_identified_video_through_simulator_and_real_detector(self):
        import cv2
        import numpy as np

        from sonar_vision_integration.bench import run

        with TemporaryDirectory() as directory:
            video = Path(directory) / "generated.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 15, (480, 360))
            self.assertTrue(writer.isOpened())
            for index in range(30):
                frame = np.zeros((360, 480, 3), dtype=np.uint8)
                cv2.rectangle(frame, (30 + index, 80), (120 + index, 220), (255, 255, 255), -1)
                writer.write(frame)
            writer.release()
            report = run(3, Path(WEIGHTS), video=video, source_id="generated-test-video")

        self.assertEqual(report["backend"], "ultralytics")
        self.assertEqual(report["outcomes"], {"admitted": 3})
        self.assertEqual(report["server_statuses"], {"200": 3})
        self.assertEqual(report["configuration"]["source_id"], "generated-test-video")
        self.assertEqual(report["configuration"]["frames_observed"], 3)
        self.assertIsNone(report["configuration"]["source_stop_reason"])
        self.assertEqual(len(report["configuration"]["video_sha256"]), 64)
        self.assertEqual(len(report["model"]["weights_sha256"]), 64)
        self.assertEqual(report["capture_to_decision"]["samples"], 3)
        self.assertNotIn(str(video), str(report))


if __name__ == "__main__":
    unittest.main()
