"""End-to-end timing over real HTTPS: `python -m sonar_vision_integration.bench`.

ENVIRONMENT-DEPENDENT measurement, not a test: numbers depend on the machine
and load and are not accuracy or hardware evidence. Default backend is the
simulated one; the real detector is opt-in with --weights (trusted local file).
Writes JSON to a new path (never overwrites); no images, tokens or paths saved.
"""

import argparse
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter, process_time

try:
    import resource
except ImportError:  # Windows
    resource = None

from sonar_vision.benchmark import summarize

from .client import ClientBusy, DeviceClient, Discarded

PACKAGES = ("fastapi", "uvicorn", "python-multipart", "httpx2", "ultralytics", "opencv-python",
            "torch", "numpy")


def synthetic_jpeg(real: bool) -> bytes:
    """Black 640x480 frame. Header-only skeleton for the simulated backend."""
    if real:
        import cv2
        import numpy as np
        ok, data = cv2.imencode(".jpg", np.zeros((480, 640, 3), dtype=np.uint8))
        if not ok:
            raise RuntimeError("could not encode synthetic frame")
        return data.tobytes()
    sof = b"\xff\xc0\x00\x11\x08\x01\xe0\x02\x80\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    return b"\xff\xd8" + sof + b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00\x00\xff\xd9"


def _versions() -> dict:
    found = {}
    for name in PACKAGES:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = None
    return found


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _dirty() -> bool | None:
    try:
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                                check=True, timeout=5)
        return bool(status.stdout)
    except (OSError, subprocess.SubprocessError):
        return None


def run(frames: int, weights: Path | None = None, delay_ms: int = 0,
        video: Path | None = None, source_id: str | None = None) -> dict:
    if type(frames) is not int or frames < 1 or type(delay_ms) is not int or delay_ms < 0:
        raise ValueError("frames must be positive and delay nonnegative")
    if weights is not None and delay_ms:
        raise ValueError("simulated delay cannot be applied to the real detector")
    if video is not None and (weights is None or not source_id):
        raise ValueError("video requires real detector weights and a source identifier")
    if source_id is not None and video is None:
        raise ValueError("source identifier requires a video")
    video_hash = None
    if video is not None:
        digest = sha256()
        with Path(video).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        video_hash = digest.hexdigest()
    from .server import Harness

    outcomes, total_ms, capture_to_decision_ms = {}, [], []
    source_stop_reason = None
    wall_started, cpu_started = perf_counter(), process_time()
    with TemporaryDirectory() as directory, Harness(Path(directory), weights=weights) as harness:
        harness.control.delay_s = delay_ms / 1000
        if video is None:
            client = DeviceClient(harness.url, harness.tokens["glasses-01"], harness.tls["ca"])
            image = synthetic_jpeg(weights is not None)
            try:
                for _ in range(frames):
                    capture = client.capture(image)
                    started = perf_counter()
                    try:
                        client.send(capture)
                        outcome = "admitted"
                    except Discarded as error:
                        outcome = f"discarded:{error.reason}"
                    except ClientBusy:
                        outcome = "client_busy"
                    total_ms.append((perf_counter() - started) * 1000)
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
            finally:
                client.close()
        else:
            from sonar_vision.simulator import HTTPS, LocalState, OpenCVSource, Orientation, Simulator

            simulator = Simulator()
            transport = HTTPS(harness.url, harness.tokens["glasses-01"],
                              ca_file=str(harness.tls["ca"]))
            source = OpenCVSource(str(video))
            def local():
                return LocalState(Orientation.yaw(0))  # explicitly synthetic
            try:
                for _ in range(frames):
                    started = perf_counter()
                    result = simulator.exchange(source, transport, local)
                    if result.get("reason") == "source_ended_or_decode_failed":
                        source_stop_reason = result["reason"]
                        break
                    total_ms.append((perf_counter() - started) * 1000)
                    if result["latency_ms"] is not None:
                        capture_to_decision_ms.append(result["latency_ms"])
                    outcome = ("admitted" if result["outcome"] == "accepted" else
                               f"discarded:{result['reason']}")
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
            finally:
                source.close()
        server = harness.log.of("inference_request")
        backend = harness.backend
        model_metadata = harness.model_metadata
    if not total_ms:
        raise ValueError("video yielded no usable frames")
    elapsed = perf_counter() - wall_started
    cpu_seconds = process_time() - cpu_started
    peak_rss_bytes = None
    if resource is not None:
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak_rss_bytes = peak if platform.system() == "Darwin" else peak * 1024
    stage = {}
    for key in ("read_ms", "decode_ms", "inference_ms", "policy_ms", "encode_ms", "work_ms", "total_ms"):
        values = [e[key] for e in server if isinstance(e.get(key), (int, float))]
        stage[key] = summarize(values) if values else None
    return {
        "schema_version": 1,
        "kind": "environment_dependent_benchmark",
        "backend": backend,
        "configuration": {"frames": frames, "frames_observed": len(total_ms),
                          "source_stop_reason": source_stop_reason,
                          "simulated_delay_ms": delay_ms,
                          "image": "identified_video" if video else "synthetic_black_640x480",
                          "source_id": source_id if video else None,
                          "video_sha256": video_hash,
                          "client_timeout_ms": 2000, "server_timeout_ms": 1500, "transport": "HTTPS local loopback"},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "machine": platform.machine(), "logical_cpus": os.cpu_count(),
                        "commit": _commit(), "worktree_dirty": _dirty(), "packages": _versions()},
        "model": model_metadata,
        "outcomes": outcomes,
        "client_round_trip": summarize(total_ms),
        "capture_to_decision": summarize(capture_to_decision_ms) if capture_to_decision_ms else None,
        "client_timing_basis": "source read/encode through admission" if video else "send through admission",
        "process_cpu_seconds_including_startup": cpu_seconds,
        "process_wall_seconds_including_startup": elapsed,
        "process_cpu_percent_one_core_including_startup": 100 * cpu_seconds / elapsed,
        "process_peak_rss_bytes": peak_rss_bytes,
        "server_stages": stage,
        "server_statuses": {str(s): sum(1 for e in server if e.get("status") == s)
                            for s in sorted({e.get("status") for e in server}, key=str)},
        "limitations": ["Loopback network on one computer; no Wi-Fi or ESP32",
                        "Simulated backend unless --weights is given; no accuracy claim",
                        "Single device, sequential requests; concurrency is covered by tests, not timed here",
                        "Video source is a file, not a camera or sensor measurement" if video else
                        "Synthetic image is not a video or camera measurement"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=50)
    parser.add_argument("--weights", type=Path, help="opt-in: trusted local .pt for the real detector")
    parser.add_argument("--video", type=Path, help="opt-in: authorized video file for the #30 simulator")
    parser.add_argument("--source-id", help="non-personal identifier for the video source")
    parser.add_argument("--delay-ms", type=int, default=0, help="simulated backend delay")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.frames < 1 or args.delay_ms < 0:
        parser.error("frames must be positive and delay nonnegative")
    if args.video is not None and (args.weights is None or not args.source_id):
        parser.error("--video requires --weights and --source-id")
    if args.source_id is not None and args.video is None:
        parser.error("--source-id requires --video")
    if args.weights is not None and args.delay_ms:
        parser.error("--delay-ms is only supported by the simulated backend")
    if args.output.exists():
        parser.error("output already exists; use a new path")
    report = run(args.frames, args.weights, args.delay_ms, args.video, args.source_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"outcomes": report["outcomes"],
                      "client_p95_ms": report["client_round_trip"]["p95_ms"]}))


if __name__ == "__main__":
    main()
