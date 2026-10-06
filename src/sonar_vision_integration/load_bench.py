"""Offered load through loopback HTTPS, with one active request per device (#22)."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
from time import sleep

from sonar_vision.benchmark import summarize
from .bench import _commit, _dirty, _versions, synthetic_jpeg
from .load import ResourceSampler, run_load


def run(*, devices=1, fps=2.0, duration_s=10.0, weights=None, stair_weights=None,
        delay_ms=0, phase="aligned"):
    if type(devices) is not int or not 1 <= devices <= 8:
        raise ValueError("devices must fit the default eight-session capacity")
    if not math.isfinite(fps) or fps <= 0 or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("fps and duration must be finite and positive")
    if type(delay_ms) is not int or delay_ms < 0 or (weights is not None and delay_ms):
        raise ValueError("delay is nonnegative and only applies to the simulated backend")
    if phase not in ("aligned", "staggered"):
        raise ValueError("phase must be aligned or staggered")
    if stair_weights is not None and weights is None:
        raise ValueError("stair weights require a primary detector")
    from .client import DeviceClient
    from .server import Harness

    names = tuple(f"load-device-{index + 1}" for index in range(devices))
    reports, errors = [None] * devices, [None] * devices
    gate = Barrier(devices + 1)
    frames = [{"clip_id": "original-synthetic-black", "jpeg": synthetic_jpeg(weights is not None),
               "source_timestamp_ms": 0}]
    with TemporaryDirectory() as directory, Harness(Path(directory), devices=names,
                                                    weights=weights,
                                                    stair_direction_weights=stair_weights) as server:
        server.control.delay_s = delay_ms / 1000
        clients = [DeviceClient(server.url, server.tokens[name], server.tls["ca"]) for name in names]

        def worker(index):
            try:
                gate.wait()
                if phase == "staggered":
                    sleep(index / (fps * devices))
                reports[index] = run_load(clients[index], frames, fps=fps, duration_s=duration_s)
            except Exception as error:
                errors[index] = type(error).__name__  # never exception text or credentials

        threads = [Thread(target=worker, args=(index,)) for index in range(devices)]
        try:
            with ResourceSampler() as resources:
                for thread in threads:
                    thread.start()
                gate.wait()
                for thread in threads:
                    thread.join()
        finally:
            for client in clients:
                client.close()
        if any(errors):
            raise RuntimeError("load execution failed; no performance claim can be made")
        model = server.model_metadata
        backend = server.backend
    events = server.log.of("inference_request")
    offered = sum(report["offered_opportunities"] for report in reports)
    outcomes = Counter()
    opportunities = Counter()
    for report in reports:
        outcomes.update(report["attempt_outcomes"])
        opportunities.update(report["opportunity_counts"])
    timings = {}
    for stage in ("read_ms", "decode_ms", "inference_ms", "policy_ms", "encode_ms", "work_ms", "total_ms"):
        values = [event[stage] for event in events if isinstance(event.get(stage), (int, float))]
        timings[stage] = summarize(values) if values else None
    return {
        "schema_version": 1, "kind": "exploratory_loopback_offered_load",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "code": {"commit": _commit(), "worktree_dirty": _dirty(), "packages": _versions()},
        "configuration": {"devices": devices, "offered_fps_per_device": fps,
                          "offering_duration_s": duration_s, "simulated_delay_ms": delay_ms,
                          "backend": backend, "source": "original_synthetic_black_640x480",
                          "device_phase": phase,
                          "transport": "verified HTTPS loopback", "queue": False},
        "model": model, "offered_opportunities": offered,
        "opportunity_counts": dict(opportunities), "attempt_outcomes": dict(outcomes),
        "admitted_fraction_of_offered": outcomes["admitted"] / offered,
        "server_statuses": dict(Counter(str(event["status"]) for event in events)),
        "server_stages": timings, "process_resources": resources.report(),
        "devices": [{"device": name, **report} for name, report in zip(names, reports)],
        "acceptance_evaluated": False,
        "limitations": ["CPU/RSS include the client and server in one process",
                        "Synthetic preencoded input does not measure a camera or accuracy",
                        "Loopback does not measure Wi-Fi, AWS or hardware",
                        "One global API slot may admit devices unevenly; no fairness guarantee",
                        "Resource sampling includes benchmark overhead; peak RSS includes startup"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", type=int, default=1)
    parser.add_argument("--fps", type=float, default=2)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--weights", type=Path)
    parser.add_argument("--stair-direction-weights", type=Path)
    parser.add_argument("--delay-ms", type=int, default=0)
    parser.add_argument("--phase", choices=("aligned", "staggered"), default="aligned")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output exists; use a new path")
    try:
        report = run(devices=args.devices, fps=args.fps, duration_s=args.duration,
                     weights=args.weights, stair_weights=args.stair_direction_weights,
                     delay_ms=args.delay_ms, phase=args.phase)
    except ValueError as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"outcomes": report["attempt_outcomes"],
                      "admitted_fraction_of_offered": report["admitted_fraction_of_offered"]}))


if __name__ == "__main__":
    main()
