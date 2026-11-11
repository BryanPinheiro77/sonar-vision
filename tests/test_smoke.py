"""Issue #34: real offline CLI checks and controlled runner failures."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision.smoke import Case, check_case, main, matches, run_checks


ROOT = Path(__file__).resolve().parents[1]


class SmokeTests(unittest.TestCase):
    def test_offline_demo_executes_existing_commands(self):
        report = run_checks(ROOT)
        self.assertTrue(report["passed"], report["checks"])
        self.assertEqual(len(report["checks"]), 16)
        self.assertEqual(report["evidence"], "synthetic_only")
        self.assertFalse(report["hardware_validated"])
        self.assertFalse(report["network_validated"])
        self.assertEqual(report["human_checkout_review"], "pending")

    def test_nested_values_missing_fields_and_types(self):
        self.assertTrue(matches({"a": {"b": 2}}, {"a.b": 2}))
        for document in ({}, {"a": None}, {"a": []}, {"a": {"b": True}}, {"a": {"b": 2.0}}):
            with self.subTest(document=document):
                self.assertFalse(matches(document, {"a.b": 2}))

    def test_timeout_limits_and_invalid_root(self):
        for value in (0, 0.99, 60.01, float("inf"), float("nan"), True, "30"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                run_checks(ROOT, timeout=value)
        with TemporaryDirectory() as directory, self.assertRaises(ValueError):
            run_checks(directory)

    def check_mock(self, result, *, case=None):
        case = case or Case("example", "simulator", (), {"ok": True})
        with patch("sonar_vision.smoke.subprocess.run", return_value=result) as runner:
            report = check_case(case, ROOT, {}, 1)
        self.assertFalse(runner.call_args.kwargs.get("shell", False))
        self.assertEqual(runner.call_args.kwargs["timeout"], 1)
        return report

    def test_failure_exit_and_expected_rejection(self):
        result = subprocess.CompletedProcess([], 2, "", "PRIVATE SECRET")
        self.assertEqual(self.check_mock(result)["reason"], "exit_code")
        case = Case("blocked", "audio_catalog", (), None, exit_code=2)
        report = self.check_mock(result, case=case)
        self.assertTrue(report["passed"])
        self.assertNotIn("SECRET", json.dumps(report))

    def test_wrong_answer_and_invalid_json_fail(self):
        for stdout, reason in (("{\"ok\": false}", "result_mismatch"), ("PRIVATE TOKEN", "unreadable_result")):
            report = self.check_mock(subprocess.CompletedProcess([], 0, stdout, ""))
            self.assertEqual(report["reason"], reason)
            self.assertNotIn("TOKEN", json.dumps(report))

    def test_timeout_and_launch_error_are_sanitized(self):
        for error, reason in ((subprocess.TimeoutExpired("SECRET", 1, output="PRIVATE"), "process_timeout"),
                              (OSError("SECRET"), "unreadable_result")):
            with patch("sonar_vision.smoke.subprocess.run", side_effect=error):
                report = check_case(Case("demo", "simulator", (), {}), ROOT, {}, 1)
            self.assertEqual(report["reason"], reason)
            self.assertNotIn("SECRET", json.dumps(report))

    def test_simulator_header_and_record_count(self):
        case = Case("example", "simulator", (), {"outcome": "accepted"}, line=1)
        header = {"mode": "in_process_fixture", "local_inputs": "simulated"}
        valid = json.dumps(header) + '\n{"outcome": "accepted"}\n'
        self.assertTrue(self.check_mock(subprocess.CompletedProcess([], 0, valid, ""), case=case)["passed"])
        for stdout in (valid + '{}\n', '{}\n{"outcome": "accepted"}', '{}'):
            self.assertFalse(self.check_mock(subprocess.CompletedProcess([], 0, stdout, ""), case=case)["passed"])

    def test_artifact_is_checked_instead_of_only_exit_code(self):
        case = Case("example", "evaluation", (), {"tp": 5}, artifact="report.json")
        with TemporaryDirectory() as directory:
            workspace = Path(directory)
            with patch("sonar_vision.smoke.subprocess.run", return_value=subprocess.CompletedProcess([], 0, '{}', '')):
                self.assertEqual(check_case(case, workspace, {}, 1)["reason"], "unreadable_result")
                (workspace / "report.json").write_text('{"tp": 4}', encoding="utf-8")
                self.assertEqual(check_case(case, workspace, {}, 1)["reason"], "result_mismatch")
                (workspace / "report.json").write_text('{"tp": 5}', encoding="utf-8")
                self.assertTrue(check_case(case, workspace, {}, 1)["passed"])

    def test_environment_token_removed_and_timeout_boundaries(self):
        seen = []
        def inspect(case, workspace, environment, timeout):
            seen.append((workspace, environment, timeout))
            return {"case": case.name, "passed": True, "reason": None}
        with patch.dict(os.environ, {"SONAR_VISION_TOKEN": "SECRET", "PYTHONPATH": "UNRELATED"}), \
                patch("sonar_vision.smoke.check_case", side_effect=inspect):
            for timeout in (1, 60):
                self.assertTrue(run_checks(ROOT, timeout=timeout)["passed"])
        for workspace, environment, timeout in seen:
            self.assertNotIn("SONAR_VISION_TOKEN", environment)
            self.assertEqual(environment["PYTHONPATH"], str(ROOT / "src"))
            self.assertFalse(workspace.exists())

    def test_cli_private_output_no_overwrite_and_failure_status(self):
        with TemporaryDirectory() as directory, patch("sonar_vision.smoke.Path.cwd", return_value=Path(directory)):
            target = Path(directory) / "results" / "smoke.json"
            report = {"passed": True, "evidence": "synthetic_only"}
            with patch("sonar_vision.smoke.run_checks", return_value=report), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--output", str(target)]), 0)
                original = target.read_bytes()
                with self.assertRaises(SystemExit) as caught:
                    main(["--output", str(target)])
                self.assertEqual(caught.exception.code, 2)
                self.assertEqual(target.read_bytes(), original)
                for path in (Path(directory) / "public.json", Path(directory) / "results" / ".." / "outside.json"):
                    with self.assertRaises(SystemExit):
                        main(["--output", str(path)])
            with patch("sonar_vision.smoke.run_checks", return_value={"passed": False}), redirect_stdout(io.StringIO()):
                self.assertEqual(main([]), 1)


if __name__ == "__main__":
    unittest.main()
