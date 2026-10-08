"""#22 offered load against a separately operated HTTPS API, without provisioning."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from threading import Barrier, Thread
from time import sleep
from urllib.parse import urlsplit

from sonar_vision.benchmark import summarize
from sonar_vision.core import identifier
from sonar_vision_api.validation import jpeg_dimensions
from .bench import _commit, _dirty, _versions, synthetic_jpeg
from .load import ResourceSampler, run_load


def validate(endpoint, credentials, fps, duration_s, warmup_s, phase):
    url = urlsplit(endpoint)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("", "/")
    ):
        raise ValueError(
            "HTTPS base URL required, without credentials/path/query/fragment"
        )
    if not 1 <= len(credentials) <= 8:
        raise ValueError("one to eight distinct device credentials required")
    names, tokens = set(), set()
    for name, token in credentials:
        identifier(name)
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 1024
            or any(x.isspace() for x in token)
        ):
            raise ValueError("invalid credential file")
        if name in names or token in tokens:
            raise ValueError("devices must have distinct names and credentials")
        names.add(name)
        tokens.add(token)
    if (
        not all(math.isfinite(x) for x in (fps, duration_s, warmup_s))
        or fps <= 0
        or duration_s <= 0
        or warmup_s < 0
        or phase not in ("aligned", "staggered")
    ):
        raise ValueError("invalid offered load profile")


def attach_server_log(report, path):
    """Join independent server durations by authenticated device/session/frame."""
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("server_log_too_large")
    expected = {
        (d["device"], r["session_id"], r["frame_id"])
        for d in report["devices"]
        for r in d["rows"]
    }
    seen, events = set(), []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if len(line) > 65536:
                raise ValueError("server_log_record_too_large")
            try:
                value = json.loads(line)
            except ValueError:
                continue  # Docker logs also contain uvicorn startup lines.
            if not isinstance(value, dict) or value.get("event") != "inference_request":
                continue
            key = (
                value.get("device_id"),
                value.get("session_id"),
                value.get("frame_id"),
            )
            if key not in expected:
                continue
            if key in seen:
                raise ValueError("duplicate_server_request")
            seen.add(key)
            events.append(value)
    stages = {}
    for stage in (
        "read_ms",
        "decode_ms",
        "inference_ms",
        "policy_ms",
        "encode_ms",
        "work_ms",
        "total_ms",
    ):
        values = [x[stage] for x in events if type(x.get(stage)) in (int, float)]
        stages[stage] = summarize(values) if values else None
    report["server_observations"] = {
        "source_sha256": sha256(path.read_bytes()).hexdigest(),
        "matched": len(events),
        "missing": len(expected - seen),
        "statuses": dict(Counter(str(x.get("status")) for x in events)),
        "stages": stages,
        "scope": "operator-exported API durations; clocks not subtracted across hosts",
    }
    return report


def measurement_continuity(resources):
    """Flag suspension or clock changes; not a cross-host latency measurement."""
    samples = resources.get("samples", [])
    differences = []
    for first, second in zip(samples, samples[1:]):
        utc_elapsed = (
            datetime.fromisoformat(second["sampled_at_utc"])
            - datetime.fromisoformat(first["sampled_at_utc"])
        ).total_seconds()
        monotonic_elapsed = second["elapsed_s"] - first["elapsed_s"]
        differences.append(abs(utc_elapsed - monotonic_elapsed))
    maximum = max(differences, default=None)
    return {
        "continuous": None if maximum is None else maximum <= 1.0,
        "maximum_sample_clock_difference_s": maximum,
        "tolerance_s": 1.0,
        "scope": "client UTC versus monotonic sample intervals",
        "limitation": "Flags suspension or clock adjustment; does not identify the cause",
    }


def run(
    *,
    endpoint,
    credentials,
    ca_file=None,
    fps=10.0,
    duration_s=10.0,
    warmup_s=0.0,
    phase="aligned",
    frames=None,
    source_id=None,
    client_factory=None,
):
    validate(endpoint, credentials, fps, duration_s, warmup_s, phase)
    if frames is None:
        frames = [
            {
                "clip_id": "original_synthetic_black",
                "jpeg": synthetic_jpeg(True),
                "source_timestamp_ms": 0,
            }
        ]
        source_id = "original_synthetic_black"
    if not frames or not source_id:
        raise ValueError("identified preencoded source required")
    corpus = []
    for frame in frames:
        data = frame["jpeg"]
        shape = jpeg_dimensions(data, 1600 * 1200)
        if len(data) > 512 * 1024 - 16384:
            raise ValueError("source_exceeds_upload_budget")
        corpus.append(
            {
                "jpeg_sha256": sha256(data).hexdigest(),
                "bytes": len(data),
                "height_width": list(shape),
            }
        )
    from .client import DeviceClient

    factory = client_factory or DeviceClient
    clients = []
    reports = [None] * len(credentials)
    errors = [None] * len(credentials)
    barrier = Barrier(len(credentials) + 1)
    warmups = []
    try:
        for name, token in credentials:
            clients.append(factory(endpoint.rstrip("/"), token, ca_file))
        for client in clients:
            if warmup_s:
                warmups.append(run_load(client, frames, fps=fps, duration_s=warmup_s))
            client.restart()

        def worker(index):
            try:
                barrier.wait()
                if phase == "staggered":
                    sleep(index / (fps * len(clients)))
                reports[index] = run_load(
                    clients[index], frames, fps=fps, duration_s=duration_s
                )
            except Exception as error:
                errors[index] = type(
                    error
                ).__name__  # never arbitrary exception/URL/token text

        workers = [Thread(target=worker, args=(i,)) for i in range(len(clients))]
        with ResourceSampler() as resources:
            for thread in workers:
                thread.start()
            barrier.wait()
            for thread in workers:
                thread.join()
        if any(errors):
            raise RuntimeError("remote_load_worker_failed")
    finally:
        for client in clients:
            client.close()
    outcomes = Counter()
    opportunities = Counter()
    for r in reports:
        outcomes.update(r["attempt_outcomes"])
        opportunities.update(r["opportunity_counts"])
    resource_report = resources.report()
    return {
        "schema_version": 1,
        "kind": "external_https_offered_load",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_code": {
            "commit": _commit(),
            "worktree_dirty": _dirty(),
            "packages": _versions(),
        },
        "configuration": {
            "devices": len(clients),
            "offered_fps_per_device": fps,
            "offering_duration_s": duration_s,
            "warmup_s_per_device": warmup_s,
            "phase": phase,
            "source_id": source_id,
            "corpus": corpus,
            "transport": "verified HTTPS to operator endpoint",
            "queue": False,
        },
        "opportunity_counts": dict(opportunities),
        "attempt_outcomes": dict(outcomes),
        "devices": [
            {"device": name, **r} for (name, _), r in zip(credentials, reports)
        ],
        "warmup_attempt_outcomes": [r["attempt_outcomes"] for r in warmups],
        "client_process_resources": resource_report,
        "measurement_continuity": measurement_continuity(resource_report),
        "server_observations": None,
        "acceptance_evaluated": False,
        "limitations": [
            "Preencoded input does not measure camera acquisition/encoding or accuracy",
            "CPU/RSS here are client process only; server resources require separate sampling",
            "No endpoint/token/image/path is written; receipt/session identifiers remain private",
            "One global API slot can admit devices unevenly; report each device separately",
            "Server model hashes/configuration must be exported by the operator",
            "Synthetic source is not evidence for tracking/trajectory or physical feedback",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--endpoint", required=True, help="HTTPS base URL, not /v1/inference"
    )
    parser.add_argument("--device-id", action="append", required=True)
    parser.add_argument("--token-file", type=Path, action="append", required=True)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--fps", type=float, default=10)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--warmup", type=float, default=0)
    parser.add_argument("--phase", choices=("aligned", "staggered"), default="aligned")
    parser.add_argument(
        "--image",
        type=Path,
        action="append",
        help="authorized preencoded JPEG; absent=synthetic black",
    )
    parser.add_argument("--source-id")
    parser.add_argument("--server-log", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or len(args.device_id) != len(args.token_file):
        parser.error("new output and one token file per device required")
    if bool(args.image) != bool(args.source_id):
        parser.error("images require a nonpersonal source-id")
    try:
        credentials = [
            (name, path.read_text().strip())
            for name, path in zip(args.device_id, args.token_file)
        ]
        frames = (
            [
                {"clip_id": "corpus", "jpeg": p.read_bytes(), "source_timestamp_ms": i}
                for i, p in enumerate(args.image)
            ]
            if args.image
            else None
        )
        report = run(
            endpoint=args.endpoint,
            credentials=credentials,
            ca_file=args.ca_file,
            fps=args.fps,
            duration_s=args.duration,
            warmup_s=args.warmup,
            phase=args.phase,
            frames=frames,
            source_id=args.source_id,
        )
        if args.server_log:
            attach_server_log(report, args.server_log)
        with os.fdopen(
            os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        ) as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
    except (ValueError, OSError, RuntimeError):
        parser.exit(
            2,
            "Remote benchmark configuration/execution failed; inspect local inputs.\n",
        )
    print(
        json.dumps(
            {
                "outcomes": report["attempt_outcomes"],
                "admitted_fps_by_device": [
                    r["admitted_fps_within_offering_window"] for r in report["devices"]
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
