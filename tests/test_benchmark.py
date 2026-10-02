"""The scripted benchmark checks report structure without weights or media."""

from contextlib import redirect_stdout
from io import StringIO
import json
import math
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision.benchmark import main


class BenchmarkReportTests(unittest.TestCase):
    def test_scripted_report_includes_bounded_performance_fields(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            with patch.object(sys, "argv", ["benchmark", "--frames", "10",
                                             "--warmup", "2", "--output", str(output)]):
                with redirect_stdout(StringIO()):
                    main()
            report = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["input"], "synthetic_no_accuracy_evidence")
        self.assertEqual(report["processing_latency"]["samples"], 10)
        self.assertEqual(report["processing_latency"]["p99_ms"],
                         report["processing_latency"]["max_ms"])
        self.assertIsNone(report["video_decode_latency"])
        self.assertGreater(report["measured_wall_seconds"], 0)
        self.assertTrue(math.isfinite(report["process_cpu_percent_one_core"]))
        self.assertGreaterEqual(report["process_cpu_percent_one_core"], 0)
        if report["process_peak_rss_bytes"] is not None:
            self.assertGreater(report["process_peak_rss_bytes"], 0)
        self.assertNotIn(str(output), json.dumps(report))


if __name__ == "__main__":
    unittest.main()
