"""#23 preflight blocks mutable artifacts and unsafe private inputs before Docker."""

import hashlib
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sonar_vision_api.auth import token_hash


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "aws_release",
            Path(__file__).resolve().parents[1] / "scripts/check_aws_release.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.models = self.root / "models"
        self.models.mkdir()
        self.tokens = self.root / "tokens"
        self.tokens.write_text(
            "glasses-01 " + token_hash("synthetic-test-secret") + "\n"
        )
        self.tokens.chmod(0o600)
        self.env = {
            "SONAR_AWS_IMAGE_ID": "sha256:" + "a" * 64,
            "SONAR_HOST_TLS_DIR": str(self.root),
            "SONAR_HOST_MODELS_DIR": str(self.models),
            "SONAR_HOST_TOKENS_FILE": str(self.tokens),
        }

    def test_wrong_platform_or_image_identity_is_rejected(self):
        image = {"Id": "sha256:" + "a" * 64, "Os": "linux", "Architecture": "arm64"}
        with self.assertRaisesRegex(ValueError, "platform"):
            self.module.validate_image(image, image["Id"], "linux/amd64")
        with self.assertRaisesRegex(ValueError, "identity"):
            self.module.validate_image(image, "sha256:" + "b" * 64, "linux/arm64")
        self.assertEqual(
            self.module.validate_image(image, image["Id"], "linux/arm64"), "linux/arm64"
        )

    def test_mutable_image_fails_before_private_inputs(self):
        for image in ("latest", "sonar:main", "sha256:abc", "sha256:" + "G" * 64):
            with (
                self.subTest(image=image),
                self.assertRaisesRegex(ValueError, "immutable"),
            ):
                self.module.inspect_inputs({**self.env, "SONAR_AWS_IMAGE_ID": image})

    @unittest.skipIf(os.name == "nt", "POSIX private permissions")
    def test_group_readable_credential_and_symlink_fail_closed(self):
        self.tokens.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "private"):
            self.module.inspect_inputs(self.env)
        self.tokens.chmod(0o600)
        link = self.root / "linked"
        link.symlink_to(self.tokens)
        with self.assertRaisesRegex(ValueError, "private"):
            self.module.inspect_inputs(
                {**self.env, "SONAR_HOST_TOKENS_FILE": str(link)}
            )

    def test_model_mismatch_and_traversal_rejected(self):
        from unittest.mock import patch

        with (
            patch.object(self.module.ssl, "SSLContext"),
            patch.object(self.module.ssl, "create_default_context"),
            patch.object(
                self.module, "private_file", wraps=self.module.private_file
            ) as private,
        ):
            # TLS loading is outside this test; preserve token validation.
            private.side_effect = lambda path: Path(path)
            weights = self.models / "general.pt"
            weights.write_bytes(b"not-a-real-model-for-file-hash-test")
            env = {
                **self.env,
                "SONAR_API_BACKEND": "ultralytics",
                "SONAR_API_WEIGHTS_IN_CONTAINER": "/models/general.pt",
                "SONAR_API_WEIGHTS_SHA256": "b" * 64,
            }
            with self.assertRaisesRegex(ValueError, "mismatch"):
                self.module.inspect_inputs(env)
            env["SONAR_API_WEIGHTS_SHA256"] = hashlib.sha256(
                weights.read_bytes()
            ).hexdigest()
            self.assertTrue(self.module.inspect_inputs(env)["credentials_validated"])
            env["SONAR_API_WEIGHTS_IN_CONTAINER"] = "/models/../general.pt"
            with self.assertRaisesRegex(ValueError, "immediate"):
                self.module.inspect_inputs(env)

    def test_optional_audio_requires_matching_hash_and_valid_policy(self):
        import json
        from unittest.mock import patch

        policy = self.root / "audio.json"
        data = {
            "confidence_min": 0.5,
            "track_cooldown_ms": 2000,
            "semantic_cooldown_ms": 10000,
            "memory_ttl_ms": 30000,
            "max_tracks": 32,
            "max_semantics": 32,
            "class_order": [
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
        }
        policy.write_text(json.dumps(data))
        env = {
            **self.env,
            "SONAR_HOST_AUDIO_CONFIG": str(policy),
            "SONAR_AUDIO_CONFIG_SHA256": "b" * 64,
        }
        with (
            patch.object(self.module.ssl, "SSLContext"),
            patch.object(self.module.ssl, "create_default_context"),
            patch.object(
                self.module, "private_file", side_effect=lambda path: Path(path)
            ),
        ):
            with self.assertRaisesRegex(ValueError, "audio configuration hash"):
                self.module.inspect_inputs(env, audio=True)
            env["SONAR_AUDIO_CONFIG_SHA256"] = hashlib.sha256(
                policy.read_bytes()
            ).hexdigest()
            result = self.module.inspect_inputs(env, audio=True)
            self.assertEqual(
                result["model_hashes"]["audio_config_sha256"],
                env["SONAR_AUDIO_CONFIG_SHA256"],
            )
            policy.write_text(json.dumps({"unexpected": "field"}))
            env["SONAR_AUDIO_CONFIG_SHA256"] = hashlib.sha256(
                policy.read_bytes()
            ).hexdigest()
            with self.assertRaises(ValueError):
                self.module.inspect_inputs(env, audio=True)
