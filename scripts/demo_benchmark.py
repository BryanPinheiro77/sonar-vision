"""Compare a single HTTPS inference source with 0/1/3 simulated spectators.

Run each condition in a separate invocation, against an explicitly SIMULATED
source. Model backend may be real. Resource evidence is collected separately on
the server with sample_container.py; this client cannot measure remote CPU/RAM.
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import ssl
from threading import Event
from time import monotonic
from urllib.parse import urlsplit


def percentile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * q) - 1)], 3)


def main():
    import httpx2
    from demo_source import synthetic_jpeg
    from sonar_vision_integration.client import DeviceClient, Discarded

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--spectators", required=True, type=int, choices=(0, 1, 3))
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--fps", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = urlsplit(args.endpoint)
    if (url.scheme != "https" or not url.netloc or url.username or url.password or
            url.path not in ("", "/") or url.query or url.fragment):
        parser.error("HTTPS origin without path/credentials/query required")
    if (not math.isfinite(args.duration) or not 1 <= args.duration <= 600 or
            not math.isfinite(args.fps) or not 0 < args.fps <= 10):
        parser.error("duration 1..600 s; fps >0..10")
    origin = args.endpoint.rstrip("/")
    context = ssl.create_default_context(cafile=args.ca_file)
    with httpx2.Client(verify=context, follow_redirects=False, timeout=4) as client:
        response = client.get(origin + "/v1/demo/snapshot")
        response.raise_for_status()
        snapshot = response.json()
    if snapshot["source"]["kind"] != "simulated" or snapshot["source"]["session_id"] != args.session:
        parser.error("matching session and explicitly SIMULATED source required")
    image = synthetic_jpeg(0)
    device = DeviceClient(origin, args.token_file.read_text().strip(), args.ca_file)
    device.session_id = args.session
    device._next_frame = int(monotonic() * 1000)
    stop = Event()

    def spectator(index):
        counts = Counter()
        with httpx2.Client(verify=context, follow_redirects=False, timeout=4) as client:
            stop.wait(index * .1)
            while not stop.is_set():
                before = monotonic()
                try:
                    response = client.get(origin + "/v1/demo/snapshot")
                    counts["snapshot_http_" + str(response.status_code)] += 1
                    if response.status_code == 200:
                        frame = response.json()["image"]["data"]
                        if frame:
                            response = client.get(origin + "/v1/demo/image", params={
                                "frame_id": frame["frame_id"], "sha256": frame["jpeg_sha256"]})
                            counts["image_http_" + str(response.status_code)] += 1
                            if response.status_code == 200:
                                counts["jpeg_bytes"] += len(response.content)
                except httpx2.HTTPError:
                    counts["transport_error"] += 1
                stop.wait(max(0, 2 - (monotonic() - before)))
        return dict(counts)

    # Exclusive private output: don't overwrite a failed condition's evidence.
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        times, failures = [], Counter()
        # The source/configuration probe above consumes one read quota. Don't
        # count its startup contention as a fourth measured spectator.
        stop.wait(1.1)
        started = monotonic()
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                viewers = [pool.submit(spectator, i) for i in range(args.spectators)]
                target = started
                try:
                    while monotonic() - started < args.duration:
                        if device.busy:
                            stop.wait(.001)
                            continue
                        before = monotonic()
                        try:
                            device.send(device.capture(image))
                            times.append((monotonic() - before) * 1000)
                        except Discarded as error:
                            failures[error.reason] += 1
                        target = max(target + 1 / args.fps, monotonic())
                        stop.wait(max(0, target - monotonic()))
                finally:
                    elapsed = monotonic() - started
                    stop.set()
                viewer_results = [v.result() for v in viewers]
        finally:
            device.close()
        report = {"schema_version": 1, "kind": "demo_spectator_comparison_condition",
                  "scope": "synthetic JPEG source over HTTPS; not physical ESP or accuracy",
                  "backend": snapshot["backend"], "client_platform": platform.platform(),
                  "spectators": args.spectators, "poll_ms": 2000, "requested_fps": args.fps,
                  "requested_duration_s": args.duration, "elapsed_s": elapsed,
                  "jpeg_sha256": sha256(image).hexdigest(), "jpeg_bytes": len(image),
                  "admitted": len(times), "admitted_per_second": len(times) / elapsed,
                  "failures": dict(failures), "spectator_results": viewer_results,
                  "https_admitted_ms": {"p50": percentile(times, .50),
                                        "p95": percentile(times, .95), "p99": percentile(times, .99)},
                  "server_resources": "collect separately with sample_container.py; not measured by client"}
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"admitted": len(times), "failures": dict(failures), "spectators": args.spectators}))


if __name__ == "__main__":
    main()
