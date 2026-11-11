"""#22 native CPU memory-format probe, using explicit private operator mounts.

Requires trusted general/R21 models at /models, 177 prepared JPEGs/manifest
under /run/sonar/layout-input, and private writable layout-results directory.
No API, downloads, training, cloud provisioning or production default change.
"""

import os


def main():
    import json
    import time
    import hashlib
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    import cv2
    import numpy as np
    import torch
    from sonar_vision.ultralytics_backend import UltralyticsFactory
    from sonar_vision.benchmark import summarize

    os.umask(0o077)
    root = Path("/run/sonar/layout-input")
    out = Path("/run/sonar/layout-results")
    kwargs = {"stair_direction_weights": Path("/models/stairs.pt")}
    factories = [
        UltralyticsFactory(Path("/models/general.pt"), **kwargs) for _ in range(2)
    ]
    for f in factories:
        f.warmup()
    torch.set_num_threads(1)
    checks = []
    for yolo in (factories[1]._model, factories[1]._direction_model):
        m = yolo.predictor.model.model
        before = {k: v.detach().clone() for k, v in m.state_dict().items()}
        m.to(memory_format=torch.channels_last)
        checks.append(all(torch.equal(v, m.state_dict()[k]) for k, v in before.items()))

        def convert(module, args):
            x = args[0]
            if isinstance(x, torch.Tensor) and x.ndim == 4:
                return (x.to(memory_format=torch.channels_last),) + args[1:]

        m.register_forward_pre_hook(convert)
    assert all(checks)
    backends = [f() for f in factories]
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    for b in backends:
        for _ in range(5):
            b.infer(image)
    values = {"contiguous": [], "channels_last": []}
    names = ["contiguous", "channels_last"]
    wall = datetime.now(timezone.utc)
    mono = time.perf_counter()
    for i in range(60):
        for n in [0, 1] if i % 2 == 0 else [1, 0]:
            started = time.perf_counter()
            backends[n].infer(image)
            values[names[n]].append((time.perf_counter() - started) * 1000)
    clock = abs(
        (datetime.now(timezone.utc) - wall).total_seconds()
        - (time.perf_counter() - mono)
    )
    for b in backends:
        b.close()
    report = {
        "scope": "paired EC2 native inference; not HTTPS throughput",
        "intraop_threads": torch.get_num_threads(),
        "precision": "float32 unchanged",
        "parameter_values_preserved": checks,
        "warmup_per_mode": 5,
        "samples_per_mode": 60,
        "order": "alternating on same EC2, independent model instances",
        "timing": {k: summarize(v) for k, v in values.items()},
        "clock_difference_s": clock,
        "clock_continuous": clock <= 1,
        "profile": factories[0].metadata,
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (out / "timing.json").write_text(json.dumps(report, indent=2))
    print("TIMING " + json.dumps(report), flush=True)
    rows = []
    for i, c in enumerate(
        json.loads((root / "known177-manifest.json").read_text())["cases"]
    ):
        im = cv2.imread(str(root / "known177" / (str(i).zfill(3) + ".jpg")))
        bb = [f() for f in factories]
        try:
            predictions = [[asdict(x) for x in b.infer(im)] for b in bb]
        finally:
            for b in bb:
                b.close()
        rows.append(
            {
                "id": c["id"],
                "contiguous": predictions[0],
                "channels_last": predictions[1],
                "exact_equal": predictions[0] == predictions[1],
            }
        )
    (out / "predictions-private.json").write_text(json.dumps(rows))
    report["known_cases"] = len(rows)
    report["exact_equal_cases"] = sum(r["exact_equal"] for r in rows)
    report["different_cases"] = [r["id"] for r in rows if not r["exact_equal"]]
    report["mean_speedup"] = (
        report["timing"]["contiguous"]["mean_ms"]
        / report["timing"]["channels_last"]["mean_ms"]
    )
    (out / "report.json").write_text(json.dumps(report, indent=2))
    print("LAYOUT_COMPLETE " + json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
