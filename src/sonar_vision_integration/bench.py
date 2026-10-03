"""End-to-end timing over real HTTPS: `python -m sonar_vision_integration.bench`.

ENVIRONMENT-DEPENDENT measurement, not a test: numbers depend on the machine
and load and are not accuracy or hardware evidence. Default backend is the
simulated one; the real detector is opt-in with --weights (trusted local file).
Writes JSON to a new path (never overwrites); no images, tokens or paths saved.
"""

import argparse
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

from sonar_vision.benchmark import summarize

from .client import ClientBusy, DeviceClient, Discarded
from .server import Harness

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


def run(frames: int, weights: Path | None = None, delay_ms: int = 0) -> dict:
    outcomes, total_ms = {}, []
    with TemporaryDirectory() as directory, Harness(Path(directory), weights=weights) as harness:
        harness.control.delay_s = delay_ms / 1000
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
        server = harness.log.of("inference_request")
        backend = harness.backend
    stage = {}
    for key in ("read_ms", "decode_ms", "inference_ms", "policy_ms", "encode_ms", "work_ms", "total_ms"):
        values = [e[key] for e in server if isinstance(e.get(key), (int, float))]
        stage[key] = summarize(values) if values else None
    return {
        "schema_version": 1,
        "kind": "environment_dependent_benchmark",
        "backend": backend,
        "configuration": {"frames": frames, "simulated_delay_ms": delay_ms, "image": "synthetic_black_640x480",
                          "client_timeout_ms": 2000, "server_timeout_ms": 1500, "transport": "HTTPS local loopback"},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "machine": platform.machine(), "commit": _commit(), "packages": _versions()},
        "outcomes": outcomes,
        "client_round_trip": summarize(total_ms),
        "server_stages": stage,
        "server_statuses": {str(s): sum(1 for e in server if e.get("status") == s)
                            for s in sorted({e.get("status") for e in server}, key=str)},
        "limitations": ["Loopback network on one computer; no Wi-Fi, ESP32 or camera",
                        "Simulated backend unless --weights is given; no accuracy claim",
                        "Single device, sequential requests; concurrency is covered by tests, not timed here"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=50)
    parser.add_argument("--weights", type=Path, help="opt-in: trusted local .pt for the real detector")
    parser.add_argument("--delay-ms", type=int, default=0, help="simulated backend delay")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.frames < 1 or args.delay_ms < 0:
        parser.error("frames must be positive and delay nonnegative")
    if args.output.exists():
        parser.error("output already exists; use a new path")
    report = run(args.frames, args.weights, args.delay_ms)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"outcomes": report["outcomes"],
                      "client_p95_ms": report["client_round_trip"]["p95_ms"]}))


if __name__ == "__main__":
    main()
