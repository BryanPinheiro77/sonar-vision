"""Offered-load invariants through real HTTPS; no weights or external services."""

from importlib.util import find_spec
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

AVAILABLE = all(find_spec(n) for n in ("fastapi", "uvicorn", "httpx2", "trustme"))


class LoadConfigurationTests(unittest.TestCase):
    def test_invalid_load_is_rejected_without_optional_api_imports(self):
        from sonar_vision_integration.load_bench import run

        with patch.dict(sys.modules, {"sonar_vision_integration.server": None}):
            for options in ({"devices": 0}, {"devices": 9}, {"fps": float("nan")},
                            {"duration_s": 0}, {"phase": "invalid"},
                            {"stair_weights": Path("stairs.pt")},
                            {"cpu_threads": 1},
                            {"weights": Path("trusted.pt"), "cpu_threads": 0},
                            {"weights": Path("trusted.pt"), "cpu_threads": True},
                            {"weights": Path("trusted.pt"), "delay_ms": 100}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    run(**options)

    def test_resources_unavailable_are_reported_as_unknown(self):
        from sonar_vision_integration.load import ResourceSampler

        with patch("sonar_vision_integration.load.resource", None), \
                patch("sonar_vision_integration.load.current_rss_bytes", return_value=None):
            with ResourceSampler() as sampler:
                pass
            report = sampler.report()
        self.assertIsNone(report["peak_rss_bytes_since_process_start"])
        self.assertGreater(report["measured_wall_s"], 0)


@unittest.skipUnless(AVAILABLE, "requires .[api,api-dev]")
class OfferedLoadTests(unittest.TestCase):
    def test_two_devices_report_rejections_instead_of_an_old_frame_queue(self):
        from sonar_vision_integration.load_bench import run

        report = run(devices=2, fps=10, duration_s=.6, delay_ms=150)
        self.assertEqual(report["offered_opportunities"], 12)
        self.assertEqual(sum(report["opportunity_counts"].values()), 12)
        self.assertGreater(report["attempt_outcomes"].get("admitted", 0), 0)
        self.assertLess(report["admitted_fraction_of_offered"], 1)
        self.assertFalse(report["acceptance_evaluated"])
        for device in report["devices"]:
            self.assertEqual(sum(device["opportunity_counts"].values()), 6)
            self.assertEqual(device["unexpected_exception_types"], [])
            self.assertEqual(device["opportunity_counts"]["attempted"], len(device["rows"]))

    def test_busy_opportunities_drop_without_old_frame_queue(self):
        from sonar_vision_integration.bench import synthetic_jpeg
        from sonar_vision_integration.client import DeviceClient
        from sonar_vision_integration.load import run_load
        from sonar_vision_integration.server import Control, Harness

        with TemporaryDirectory() as temporary, Harness(Path(temporary), control=Control(delay_s=.15)) as server:
            client = DeviceClient(server.url, server.tokens["glasses-01"], server.tls["ca"])
            try:
                frames = [{"clip_id": "synthetic", "jpeg": synthetic_jpeg(real=False), "source_timestamp_ms": 0}]
                result = run_load(client, frames, fps=20, duration_s=.5)
                self.assertEqual(result["offered_opportunities"], 10)
                self.assertGreater(result["opportunity_counts"].get("busy_before_capture", 0), 0)
                self.assertEqual(result["attempt_outcomes"], {"admitted": len(result["rows"])})
                self.assertEqual(server.control.calls, len(result["rows"]))
                self.assertEqual(sum(result["opportunity_counts"].values()), 10)
                self.assertEqual(len(client.records), len(result["rows"]))
                self.assertFalse(client.busy)
            finally:
                client.close()

    def test_invalid_load_fails_before_sending(self):
        from sonar_vision_integration.load import run_load
        for rate, duration in ((0, 1), (float("nan"), 1), (1, float("inf"))):
            with self.subTest(rate=rate, duration=duration), self.assertRaises(ValueError):
                run_load(None, [{"clip_id": "none"}], fps=rate, duration_s=duration)


if __name__ == "__main__":
    unittest.main()
