"""Frozen synthetic holdout: evaluates parameters inherited from the lab.

These are projected boxes, not an independent annotated real-world dataset.
The misdeclared-camera control intentionally exposes a known false inference.
"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random

from .core import Detection
from .trajectory import TrajectoryConfig, TrajectoryEstimator


CASES = (
    ("static", "stable", "fixed", 0.0, 0.0),
    ("frontal_growth", "approaching", "fixed", 0.0, -.65),
    ("frontal_shrink", "receding", "fixed", 0.0, .65),
    ("left_to_right", "crossing", "fixed", .5, 0.0),
    ("right_to_left", "crossing", "fixed", -.5, 0.0),
    ("mixed", "unknown", "fixed", .5, -.65),
    ("pan_unknown_camera", "unknown", "unknown", .5, 0.0),
    ("zoom_moving_camera", "unknown", "moving", 0.0, -.65),
    ("zoom_wrongly_declared_fixed", "unknown", "fixed", 0.0, -.65),
)


def evaluate():
    config = TrajectoryConfig()
    cases = []
    for name, expected, camera, vx, vz in CASES:
        rng = random.Random(110022)
        estimator = TrajectoryEstimator(config)
        timestamp = 0
        samples = 0
        while timestamp <= 2400:
            t = timestamp/1000
            # Perspective projection, unlike exponential area fixtures in unit tests.
            depth = 5.0+vz*t
            center = .5+vx*t/depth+rng.uniform(-.001, .001)
            size = .7/depth
            detection = Detection("person", .9, (center-size/2, .5-size/2,
                                                  center+size/2, .5+size/2), "1")
            result = estimator.update(detection, timestamp, camera)
            samples += 1
            timestamp += rng.choice((65, 79, 97, 118, 151))
        cases.append({"case": name, "expected": expected, "observed": result.movement,
                      "match": expected == result.movement, "samples": samples,
                      "camera_context": camera, "final": asdict(result),
                      "known_negative_control": name == "zoom_wrongly_declared_fixed"})
    return {"schema_version": 1, "fixture_version": "projected-boxes-1", "seed": 110022,
            "config": asdict(config), "cases": cases,
            "mismatches": sum(not case["match"] for case in cases),
            "limitations": ["Synthetic held-out trajectories, not detection or tracking accuracy",
                            "Parameters frozen from lab before evaluation, no tuning on these cases",
                            "Camera context is supplied, not estimated; wrong fixed assertion can cause false motion",
                            "Real independent annotated evaluation remains pending in issue #7"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
