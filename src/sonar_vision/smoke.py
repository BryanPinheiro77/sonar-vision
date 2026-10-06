"""Offline checks of the documented software demo (#34), using synthetic data only."""

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class Case:
    name: str
    module: str
    arguments: tuple
    expected: dict | None
    exit_code: int = 0
    line: int | None = None
    artifact: str | None = None


def matches(document, expected):
    """Compare selected nested values; absent fields and bool/int confusion fail."""
    for path, value in expected.items():
        current = document
        try:
            for key in path.split("."):
                current = current[key]
        except (KeyError, TypeError):
            return False
        if type(current) is not type(value) or current != value:
            return False
    return True


def cases(root):
    catalog = str(root / "docs" / "catalog")
    manifest = str(root / "docs" / "experiments" / "manifest-example.json")
    evaluation = str(root / "docs" / "experiments" / "issue-33-fixture.json")
    checks = []
    for name, options, expected in (
        ("success", (), {"outcome": "accepted", "audio": "accepted", "latency_ms": 100}),
        ("expired", (), {"outcome": "discarded", "reason": "expired", "latency_ms": 1000}),
        ("timeout", (), {"outcome": "discarded", "reason": "timeout", "latency_ms": 2000}),
        ("disconnect", (), {"outcome": "discarded", "reason": "network_error"}),
        ("old_session", (), {"outcome": "discarded", "reason": "session_mismatch"}),
        ("orientation", ("--current-yaw", "16"), {"observation": "accepted", "audio": "orientation_changed"}),
        ("urgent", ("--urgent",), {"observation": "accepted", "audio": "local_urgent"}),
    ):
        scenario = "success" if name in ("orientation", "urgent") else name
        checks.append(Case(name, "simulator", ("--fixture", scenario, "--frames", "1") + options,
                           expected, line=1))
    checks.extend([
        Case("invalid_frame_limit", "simulator", ("--fixture", "success", "--frames", "0"), None, 2),
        Case("manifest", "evaluation_manifest", (manifest,),
             {"metadata_valid": True, "counts.recorded": 0, "counts.synthetic": 1, "approval_status": "pending"}),
        Case("catalog_draft", "audio_catalog", ("validate", catalog),
             {"metadata_valid": True, "phrases": 179, "missing_audio": 179, "distribution_ready": False}),
        Case("release_blocked", "audio_catalog", ("validate", catalog, "--require-release"), None, 2),
        Case("catalog_fixture", "audio_catalog", ("fixture", "--output", "results/catalog"),
             {"metadata_valid": True, "synthetic_audio": 179, "distribution_ready": False}),
        Case("catalog_pack", "audio_catalog", ("pack", "results/catalog", "--fixture", "--output", "results/catalog.zip"),
             {"package_created": True, "kind": "fixture", "files": 183}),
        Case("benchmark", "benchmark", ("--frames", "3", "--warmup", "1", "--output", "results/benchmark.json"),
             {"configuration.backend": "scripted", "processing_latency.samples": 3,
              "input": "synthetic_no_accuracy_evidence"}, artifact="results/benchmark.json"),
        Case("evaluation", "evaluation", (evaluation, "--output", "results/evaluation.json", "--review", "results/review.json",
             "--summary", "docs/experiments/summary.md"),
             {"overall.tp": 5, "overall.fp": 2, "overall.fn": 2, "acceptance_evaluated": False},
             artifact="results/evaluation.json"),
        Case("evaluation_no_overwrite", "evaluation", (evaluation, "--output", "results/evaluation.json"), None, 2),
    ])
    return checks


def check_case(case, workspace, environment, timeout):
    command = [sys.executable, "-B", "-m", "sonar_vision." + case.module, *case.arguments]
    reason = None
    try:
        result = subprocess.run(command, cwd=workspace, env=environment, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
        if result.returncode != case.exit_code:
            reason = "exit_code"
        elif case.expected is not None:
            if case.artifact:
                document = json.loads((workspace / case.artifact).read_text(encoding="utf-8"))
            elif case.line is not None:
                lines = result.stdout.splitlines()
                if len(lines) != 2:
                    raise ValueError("unexpected simulator record count")
                header = json.loads(lines[0])
                if not matches(header, {"mode": "in_process_fixture", "local_inputs": "simulated"}):
                    raise ValueError("unexpected simulator mode")
                document = json.loads(lines[case.line])
            else:
                document = json.loads(result.stdout)
            if not matches(document, case.expected):
                reason = "result_mismatch"
    except subprocess.TimeoutExpired:
        reason = "process_timeout"
    except (OSError, ValueError, TypeError, IndexError):
        reason = "unreadable_result"
    # Never publish subprocess output, arbitrary exceptions, paths or environment.
    return {"case": case.name, "passed": reason is None, "reason": reason,
            "expected_exit_code": case.exit_code}


def run_checks(root, *, timeout=30):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 1 <= timeout <= 60:
        raise ValueError("timeout must be between 1 and 60 seconds")
    root = Path(root).resolve()
    for relative in ("pyproject.toml", "src/sonar_vision/simulator.py", "docs/catalog/phrases.json",
                     "docs/catalog/manifest.json", "docs/experiments/manifest-example.json", "docs/experiments/issue-33-fixture.json"):
        if not (root / relative).is_file():
            raise ValueError("run from a complete source checkout")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root / "src")
    environment["PYTHONIOENCODING"] = "utf-8"
    environment.pop("SONAR_VISION_TOKEN", None)
    scratch = root / "results"
    scratch.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="sonar-demo-", dir=scratch) as directory:
        workspace = Path(directory)
        results = [check_case(case, workspace, environment, timeout) for case in cases(root)]
    return {"schema_version": 1, "evidence": "synthetic_only", "python": platform.python_version(),
            "passed": all(item["passed"] for item in results), "checks": results,
            "human_checkout_review": "pending", "real_vision_validated": False,
            "network_validated": False, "hardware_validated": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Complete source checkout, default: current directory")
    parser.add_argument("--timeout", type=float, default=30, help="Per-command seconds, 1..60; not protocol latency")
    parser.add_argument("--output", type=Path, help="Optional new JSON under results/ in the current workspace")
    args = parser.parse_args(argv)
    try:
        target = args.output.resolve() if args.output else None
        if target and (not target.is_relative_to((Path.cwd() / "results").resolve()) or target.exists()):
            raise ValueError("output must be new and private")
        report = run_checks(args.root, timeout=args.timeout)
        if target:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(report, stream, indent=2, allow_nan=False)
                stream.write("\n")
    except (OSError, ValueError):
        parser.exit(2, "Demo configuration or output unavailable; inspect checkout locally.\n")
    print(json.dumps(report, allow_nan=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
