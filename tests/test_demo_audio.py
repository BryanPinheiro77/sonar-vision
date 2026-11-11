"""Private panel projection of the exact validated audio response; no real TTS."""
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import Event
import time
import unittest
from uuid import uuid4

from api_helpers import jpeg
from sonar_vision import VisionService
from sonar_vision.benchmark import SyntheticBackend
from sonar_vision_api.collection import CollectionConfig, RoundArchive
from sonar_vision_api.demo import DemoSettings, DemoStore
from sonar_vision_api.errors import ApiError
from sonar_vision_api.service import InferenceService, header_only_decoder
from sonar_vision_api.validation import Metadata


class SpokenPolicy:
    def __init__(self, session_id):
        pass

    def select(self, observation, **kwargs):
        return {k: observation[k] for k in ("version", "session_id", "frame_id", "captured_at_ms", "valid_for_ms")} | {
            "type": "audio_suggestion", "message_id": "audio-1",
            "observation_id": observation["message_id"], "text": "Pessoa", "directional": False}


class InvalidPolicy(SpokenPolicy):
    def select(self, observation, **kwargs):
        return super().select(observation, **kwargs) | {"frame_id": "999"}


class DemoAudioTests(unittest.TestCase):
    def make(self, policy=SpokenPolicy, archive=None, factory=SyntheticBackend, timeout=1500):
        store = DemoStore(DemoSettings("device", "boot-1", "simulated"), archive=archive)
        service = InferenceService(VisionService(factory), header_only_decoder,
            timeout_ms=timeout, policy_factory=policy, demo=store)
        self.addCleanup(service.close)
        return service, store

    def infer(self, service):
        return json.loads(asyncio.run(service.infer("device", Metadata("boot-1", "1", 1000),
            jpeg(), (480, 640), time.monotonic(), {})))

    def test_exact_validated_audio_and_rejected_output_fallback(self):
        for policy in (SpokenPolicy, InvalidPolicy):
            with self.subTest(policy=policy.__name__):
                service, store = self.make(policy)
                response = self.infer(service)
                prediction = store.snapshot("simulated")["image"]["data"]["predictions"]
                self.assertEqual(prediction["audio"], response["audio"])
                self.assertEqual(prediction["message_id"], response["observation"]["message_id"])
                if policy is InvalidPolicy:
                    self.assertIsNone(prediction["audio"])
                else:
                    self.assertEqual(prediction["audio"]["text"], "Pessoa")
                # A newer capture must not retain the previous phrase.
                store.accepted("device", Metadata("boot-1", "2", 2000), jpeg(), (480, 640), time.monotonic())
                self.assertIsNone(store.snapshot("simulated")["image"]["data"]["predictions"])

    def test_timeout_cannot_publish_late_suggestion(self):
        gate = Event()
        class Blocked(SyntheticBackend):
            def infer(self, image):
                gate.wait(2)
                return super().infer(image)
        service, store = self.make(factory=Blocked, timeout=20)
        try:
            with self.assertRaises(ApiError):
                self.infer(service)
        finally:
            gate.set()
            service._executor.shutdown(wait=True)
        frame = store.snapshot("simulated")["image"]["data"]
        self.assertEqual(frame["inference"], "unavailable")
        self.assertIsNone(frame["predictions"])
        self.assertNotIn("_pending", frame)

    def test_audio_survives_archive_restart_and_rejects_wrong_reference(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "rounds"
            archive = RoundArchive(root)
            self.addCleanup(archive.close)
            cfg = CollectionConfig(uuid4().hex, "synthetic-audio", "owned-synthetic", 600, 3000, 100*1024*1024, 86400)
            archive.start(cfg, {"device_id": "device", "session_id": "boot-1", "kind": "simulated"}, {"backend": "simulated"})
            service, store = self.make(archive=archive)
            response = self.infer(service)
            archive.close()  # drains the bounded writer queue
            reopened = RoundArchive(root)
            self.addCleanup(reopened.close)
            frame = reopened.timeline(cfg.round_id)["frames"][0]
            self.assertEqual(frame["predictions"]["audio"], response["audio"])
            prediction = json.loads(json.dumps(frame["predictions"]))
            for key, value in (("frame_id", "2"), ("session_id", "wrong-boot"), ("observation_id", "wrong-observation")):
                bad = json.loads(json.dumps(prediction))
                bad["audio"][key] = value
                with self.subTest(key=key), self.assertRaises(ValueError):
                    RoundArchive._check_prediction(frame, {"status": "available", "predictions": bad})
            # Older archives and explicit null remain distinct and readable.
            for legacy in ({k: v for k, v in prediction.items() if k != "audio"}, prediction | {"audio": None}):
                RoundArchive._check_prediction(frame, {"status": "available", "predictions": legacy})

    @unittest.skipUnless(shutil.which("node"), "Node optional for browser presentation checks")
    def test_audio_view_javascript(self):
        result = subprocess.run([shutil.which("node"), "tests/audio_panel_regression.cjs"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
