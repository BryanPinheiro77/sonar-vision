"""#52 executable policy, model integrity and private capture correlation."""

import asyncio
import importlib.util
import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision.benchmark import SyntheticBackend
from sonar_vision.core import Frame, VisionService
from sonar_vision_api.config import Settings
from sonar_vision_api.diagnostics import PredictionJournal
from sonar_vision_api.runtime_options import (
    checked_weights,
    file_hash,
    load_audio_config,
)
from sonar_vision_api.service import InferenceService, header_only_decoder
from sonar_vision_api.validation import Metadata
from sonar_vision_integration.review import correlate, render

AUDIO = dict(
    confidence_min=0.5,
    track_cooldown_ms=2000,
    semantic_cooldown_ms=10000,
    memory_ttl_ms=30000,
    max_tracks=32,
    max_semantics=32,
    class_order=[
        "person",
        "car",
        "motorcycle",
        "bus",
        "bicycle",
        "chair",
        "dining_table",
        "dog",
        "stairs",
    ],
)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tokens = self.root / "tokens"
        self.tokens.write_text("device " + "a" * 64 + "\n")
        self.audio = self.root / "audio.json"
        self.audio.write_text(json.dumps(AUDIO))

    def test_audio_config_rejects_duplicates_nonfinite_missing_and_bool(self):
        self.assertEqual(
            load_audio_config(self.audio).class_order, tuple(AUDIO["class_order"])
        )
        for text in (
            '{"confidence_min":0.5,"confidence_min":0.6}',
            '{"confidence_min":NaN}',
            json.dumps({**AUDIO, "max_tracks": True}),
            json.dumps({**AUDIO, "unexpected": 1}),
            json.dumps({**AUDIO, "class_order": "person"}),
        ):
            self.audio.write_text(text)
            with self.assertRaises(ValueError):
                load_audio_config(self.audio)

    def test_hash_and_settings_fail_before_loading_models(self):
        weights = self.root / "model.pt"
        weights.write_bytes(b"trusted fixture, not a model")
        digest = checked_weights(weights, None)
        self.assertEqual(digest, file_hash(weights))
        with self.assertRaisesRegex(ValueError, "model_hash_mismatch"):
            checked_weights(weights, "0" * 64)
        common = dict(backend="ultralytics", tokens_file=self.tokens, weights=weights)
        for opts in (
            {"stair_direction_weights": self.root / "absent.pt"},
            {"weights_sha256": "bad"},
            {"diagnostics_dir": self.root / "absent"},
            {"stair_weights_sha256": "0" * 64},
        ):
            with self.assertRaises(ValueError):
                Settings(**common, **opts)
        env = dict(
            SONAR_API_BACKEND="ultralytics",
            SONAR_API_TOKENS_FILE=str(self.tokens),
            SONAR_API_WEIGHTS=str(weights),
            SONAR_API_WEIGHTS_SHA256=digest,
            SONAR_API_STAIR_WEIGHTS=str(weights),
            SONAR_API_STAIR_WEIGHTS_SHA256=digest,
            SONAR_API_AUDIO_CONFIG=str(self.audio),
            SONAR_API_DIAGNOSTICS_DIR=str(self.root),
        )
        settings = Settings.from_env(env)
        self.assertTrue(settings.public()["stairs_configured"])
        self.assertNotIn(str(self.root), json.dumps(settings.public()))

    def result(self):
        vision = VisionService(SyntheticBackend)
        vision.open("private-device", "private-session")
        result = vision.process(
            Frame("private-device", "private-session", "1", 1000, None)
        )
        vision.close("private-device", "private-session")
        return result

    def test_private_journal_correlates_exact_capture_without_changing_wire(self):
        result = self.result()
        path = self.root / "predictions.jsonl"
        journal = PredictionJournal(path, {"backend": "simulated"})
        journal.record(result, b"jpeg")
        journal.close()
        text = path.read_text()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertNotIn("private-session", text)
        self.assertNotIn("private-device", text)
        pred = json.loads(text.splitlines()[1])
        self.assertEqual(pred["detections"][0]["box"], [0.1, 0.2, 0.3, 0.8])
        self.assertNotIn("box", result.observation()["objects"][0])
        with self.assertRaises(FileExistsError):
            PredictionJournal(path, {})
        receipts = self.root / "client.jsonl"
        row = dict(
            outcome="accepted",
            observation_id=result.message_id,
            audio="no_suggestion",
            objects=result.observation()["objects"],
            **{
                k: pred[k]
                for k in ("frame_id", "captured_at_ms", "tracker_epoch", "jpeg_sha256")
            },
        )
        receipts.write_text(
            json.dumps({"kind": "private_client_receipts"})
            + "\n"
            + json.dumps(row)
            + "\n"
        )
        report = correlate(receipts, [path])
        self.assertEqual(report["accepted_without_diagnostic"], 0)
        self.assertIn("person", render(report))
        row["jpeg_sha256"] = "wrong"
        receipts.write_text(
            json.dumps({"kind": "private_client_receipts"})
            + "\n"
            + json.dumps(row)
            + "\n"
        )
        with self.assertRaisesRegex(ValueError, "capture_correlation_mismatch"):
            correlate(receipts, [path])

    def test_file_limit_drops_diagnostics_and_error_does_not_lose_observation(self):
        journal = PredictionJournal(self.root / "small.jsonl", {}, max_bytes=512)
        journal.record(self.result(), b"jpeg")
        journal.close()
        self.assertEqual(journal.dropped, 1)
        service = InferenceService(
            VisionService(SyntheticBackend),
            header_only_decoder,
            timeout_ms=1500,
            diagnostics=type(
                "Broken",
                (),
                {
                    "record": lambda *a, **k: (_ for _ in ()).throw(OSError()),
                    "close": lambda s: None,
                },
            )(),
        )
        self.addCleanup(service.close)
        body = asyncio.run(
            service.infer(
                "device",
                Metadata("boot", "1", 1000),
                b"jpeg",
                (480, 640),
                service.clock(),
                {},
            )
        )
        self.assertEqual(json.loads(body)["observation"]["frame_id"], "1")

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "install .[api]")
    def test_executable_policy_is_opt_in_and_each_restart_has_new_journal(self):
        from sonar_vision_api.__main__ import build

        for enabled in (False, True, True):
            settings = Settings(
                "simulated",
                self.tokens,
                audio_config=self.audio if enabled else None,
                diagnostics_dir=self.root if enabled else None,
            )
            _, service = build(settings)
            try:

                def call(frame):
                    return json.loads(
                        asyncio.run(
                            service.infer(
                                "device",
                                Metadata("boot", str(frame), 1000 + frame),
                                b"jpeg",
                                (480, 640),
                                service.clock(),
                                {},
                            )
                        )
                    )

                first, second = call(1), call(2)
                self.assertEqual(first["audio"] is not None, enabled)
                self.assertIsNone(second["audio"])
                if enabled:
                    self.assertEqual(first["audio"]["text"], "Pessoa")
                    other = json.loads(
                        asyncio.run(
                            service.infer(
                                "other-device",
                                Metadata("boot", "1", 1001),
                                b"jpeg",
                                (480, 640),
                                service.clock(),
                                {},
                            )
                        )
                    )
                    self.assertEqual(other["audio"]["text"], "Pessoa")
            finally:
                service.close()
        self.assertEqual(len(list(self.root.glob("predictions-*.jsonl"))), 2)

    @unittest.skipUnless(importlib.util.find_spec("fastapi"), "install .[api]")
    def test_hash_mismatch_prevents_factory_construction(self):
        from sonar_vision_api.__main__ import build

        weights = self.root / "model.pt"
        weights.write_bytes(b"fixture")
        with patch("sonar_vision.ultralytics_backend.UltralyticsFactory") as factory:
            with self.assertRaisesRegex(ValueError, "model_hash_mismatch"):
                build(
                    Settings(
                        "ultralytics",
                        self.tokens,
                        weights=weights,
                        weights_sha256="0" * 64,
                    )
                )
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
