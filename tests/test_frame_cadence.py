"""#23 timing replay keeps one active capture and the offered-rate ceiling."""

import importlib.util
from pathlib import Path
import unittest


class CadenceReplayTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "cadence",
            Path(__file__).resolve().parents[1] / "scripts/analyze_frame_cadence.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_slow_request_waits_for_completion_without_skipping_extra_grid_time(self):
        result = self.module.replay([150, 150, 150], 10)["results"]
        self.assertAlmostEqual(result["periodic"]["modeled_cohort_duration_s"], 0.55)
        self.assertAlmostEqual(
            result["when_available"]["modeled_cohort_duration_s"], 0.45
        )
        for value in result.values():
            self.assertGreaterEqual(value["minimum_start_interval_ms"], 100 - 1e-6)

    def test_fast_requests_do_not_exceed_start_rate(self):
        result = self.module.replay([20] * 10, 10)["results"]
        for value in result.values():
            self.assertAlmostEqual(value["modeled_cohort_duration_s"], 0.92)
            self.assertAlmostEqual(value["minimum_start_interval_ms"], 100)

    def test_invalid_durations_or_failure_trace_cannot_silently_be_ignored(self):
        for values in ([], [0], [float("nan")], [float("inf")], [-1], [True]):
            with self.assertRaises(ValueError):
                self.module.replay(values)
        with self.assertRaises(ValueError):
            self.module.analyze({"devices": [{"rows": [{"outcome": "timeout"}]}]})

    def test_public_projection_does_not_export_future_private_input_fields(self):
        import json

        report = {
            "devices": [
                {
                    "rows": [
                        {
                            "outcome": "admitted",
                            "synthetic_capture_to_admission_ms": 150,
                        }
                    ],
                    "offered_fps": 10,
                    "admitted_fps_within_offering_window": 7,
                    "opportunity_counts": {
                        "attempted": 1,
                        "endpoint": "https://private.invalid",
                        "session_id": "private-session",
                    },
                }
            ]
        }
        result = self.module.analyze(report)
        self.assertEqual(result["observed_opportunities"], {"attempted": 1})
        self.assertNotIn("private.invalid", json.dumps(result))
        self.assertNotIn("private-session", json.dumps(result))
