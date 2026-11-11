"""Reject misleading benchmark configurations before starting TLS or a model."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from sonar_vision_integration.bench import run


class IntegrationBenchmarkConfigurationTests(unittest.TestCase):
    def test_invalid_and_ignored_options_never_start_a_server(self):
        configurations = (
            {"frames": 0}, {"frames": True}, {"frames": 1, "delay_ms": -1},
            {"frames": 1, "weights": Path("trusted.pt"), "delay_ms": 10},
            {"frames": 1, "video": Path("video.mp4"), "source_id": "scene"},
            {"frames": 1, "video": Path("video.mp4"), "weights": Path("trusted.pt")},
            {"frames": 1, "source_id": "scene"},
        )
        # A missing optional API must not hide invalid benchmark configuration.
        with patch.dict(sys.modules, {"sonar_vision_integration.server": None}):
            for options in configurations:
                with self.subTest(options=options), self.assertRaises(ValueError):
                    run(**options)
