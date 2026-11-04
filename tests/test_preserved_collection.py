"""Synthetic policies; no Docker, AWS or participant data."""

import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "preserved_collection",
    Path(__file__).resolve().parents[1] / "scripts/prepare_preserved_collection.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PolicyTests(unittest.TestCase):
    def policy(self):
        return {
            "enabled": True,
            "source_id": "synthetic-test",
            "permission_ref": "owned-synthetic",
            **module.LIMITS,
        }

    def test_explicit_policy_and_disabled_history_mode(self):
        self.assertTrue(module.validate_policy(self.policy())["enabled"])
        self.assertFalse(
            module.validate_policy({**self.policy(), "enabled": False})["enabled"]
        )

    def test_missing_origin_permission_or_bounds_cannot_enable_recording(self):
        for key in self.policy():
            policy = self.policy()
            del policy[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_policy(policy)
        for patch in (
            {"source_id": "../private"},
            {"permission_ref": ""},
            {"enabled": "yes"},
            {"max_frames": True},
            {"max_duration_seconds": 601},
            {"retention_seconds": 86401},
            {"max_bytes": 0},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                module.validate_policy({**self.policy(), **patch})

    def test_env_update_preserves_literal_verifier_and_replaces_only_target(self):
        text = "SONAR_DEMO_VIEWER_PASSWORD_VERIFIER='hash$literal$parts'\nOTHER=unchanged\n"
        first = module.set_environment(
            text, "SONAR_COLLECTION_CONFIG_IN_CONTAINER", "/run/one.json"
        )
        second = module.set_environment(
            first, "SONAR_COLLECTION_CONFIG_IN_CONTAINER", "/run/two.json"
        )
        self.assertIn(text, second)
        self.assertNotIn("/run/one.json", second)
        self.assertEqual(second.count("SONAR_COLLECTION_CONFIG_IN_CONTAINER="), 1)
        with self.assertRaises(ValueError):
            module.set_environment("K=1\nK=2\n", "K", "3")


if __name__ == "__main__":
    unittest.main()
