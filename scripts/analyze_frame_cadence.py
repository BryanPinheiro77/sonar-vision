"""#23 deterministic cadence replay from private load rows; no network/cloud.

Uses each admitted duration once. This is a counterfactual timing model, not a
new benchmark or an accuracy measurement. Exports aggregates, never identifiers.
"""

import argparse
import json
import math
from pathlib import Path


def replay(durations_ms, fps=10.0):
    if not durations_ms or not math.isfinite(fps) or fps <= 0:
        raise ValueError("nonempty durations and finite positive rate required")
    if any(
        type(x) not in (int, float) or not math.isfinite(x) or not 0 < x < 60000
        for x in durations_ms
    ):
        raise ValueError("positive finite measured durations below 60s required")
    period = 1 / fps
    results = {}
    for mode in ("periodic", "when_available"):
        previous_start = -period
        previous_end = 0.0
        starts = []
        for ms in durations_ms:
            eligible = max(previous_start + period, previous_end)
            start = (
                math.ceil(eligible / period - 1e-10) * period
                if mode == "periodic"
                else eligible
            )
            starts.append(start)
            previous_start, previous_end = start, start + ms / 1000
        results[mode] = {
            "requests": len(durations_ms),
            "modeled_cohort_duration_s": previous_end,
            "modeled_admitted_fps": len(durations_ms) / previous_end,
            "minimum_start_interval_ms": min(
                ((b - a) * 1000 for a, b in zip(starts, starts[1:])), default=None
            ),
        }
    return {
        "kind": "cadence_counterfactual_replay_not_benchmark",
        "maximum_start_fps": fps,
        "durations_over_offering_interval": sum(
            x > period * 1000 for x in durations_ms
        ),
        "results": results,
        "assumptions": [
            "Each recorded admitted request duration is replayed once in the same order",
            "Durations assumed unchanged under a different schedule; not validated",
            "Only one request active; fresh capture after eligibility; no image queue",
            "Maximum capture start rate unchanged; no protocol or risk parameter change",
        ],
        "acceptance_evaluated": False,
        "cloud_actions": False,
    }


def analyze(report, fps=None):
    devices = report["devices"]
    if len(devices) != 1:
        raise ValueError("single glasses trace required")
    device = devices[0]
    rows = device["rows"]
    if not rows or any(row["outcome"] != "admitted" for row in rows):
        raise ValueError("successful complete trace required; do not omit failures")
    result = replay(
        [row["synthetic_capture_to_admission_ms"] for row in rows],
        device["offered_fps"] if fps is None else fps,
    )
    observed = device["admitted_fps_within_offering_window"]
    if (
        type(observed) not in (int, float)
        or not math.isfinite(observed)
        or observed < 0
    ):
        raise ValueError("finite observed rate required")
    result["observed_admitted_fps_in_window"] = observed
    counts = {
        key: device["opportunity_counts"][key]
        for key in ("attempted", "busy_before_capture", "scheduler_late")
        if key in device["opportunity_counts"]
    }
    if any(type(value) is not int or value < 0 for value in counts.values()):
        raise ValueError("nonnegative opportunity counts required")
    result["observed_opportunities"] = counts
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.report.stat().st_size > 128 * 1024 * 1024:
            raise ValueError("report too large")
        result = analyze(json.loads(args.report.read_text()))
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(
            2,
            "Cadence analysis failed; inspect private report without omitting failed requests.\n",
        )
    print("Aggregate cadence replay saved; not an experimental acceptance.")


if __name__ == "__main__":
    main()
