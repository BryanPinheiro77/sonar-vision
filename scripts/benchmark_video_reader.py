"""Isolated reader benchmark for #70; no HTTP, models, playback or hardware."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from sonar_vision.simulator import OpenCVSource

POSITIONS_MS = (0, 100, 200, 300, 400, 500, 600, 700, 2000, 2100)


class TimedCapture:
    def __init__(self, capture):
        self.capture = capture
        self.calls = Counter()
        self.seconds = Counter()

    def __getattr__(self, name):
        attribute = getattr(self.capture, name)
        if name not in ("set", "grab", "read"):
            return attribute

        def measured(*args):
            start = perf_counter()
            try:
                return attribute(*args)
            finally:
                self.calls[name] += 1
                self.seconds[name] += perf_counter() - start
        return measured


def synthetic_video(path):
    """Original procedural AGPL-3.0-only pixels; codec under its own license."""
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (640, 360))
    if not writer.isOpened():
        raise RuntimeError("synthetic MJPG writer unavailable")
    rng = np.random.default_rng(70)
    base = rng.integers(0, 256, (360, 640, 3), dtype=np.uint8)
    try:
        for index in range(90):
            image = base.copy()
            image[:60, :, :] = (index, index * 2 % 256, index * 3 % 256)
            writer.write(image)
    finally:
        writer.release()


def measure(path, repeats):
    import cv2

    trials = []
    for _ in range(repeats):
        source = OpenCVSource(str(path), max_edge=640, jpeg_quality=95)
        capture = source.cap = TimedCapture(source.cap)
        frames = []
        try:
            for position in POSITIONS_MS:
                start = perf_counter()
                jpeg, _ = source.read(lambda: position)
                frames.append({"position_ms": position, "source_frame_index": source._last_index,
                               "jpeg_sha256": sha256(jpeg).hexdigest(),
                               "read_ms": round((perf_counter() - start) * 1000, 3)})
        finally:
            source.close()
        trials.append({"frames": frames, "capture_calls": dict(capture.calls),
                       "capture_ms": {k: round(v * 1000, 3) for k, v in capture.seconds.items()}})
    signatures = [[(f["source_frame_index"], f["jpeg_sha256"]) for f in t["frames"]] for t in trials]
    assert all(s == signatures[0] for s in signatures)
    digest = sha256()
    with path.open("rb") as video:
        for chunk in iter(lambda: video.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"kind": "isolated_video_reader_benchmark", "python": platform.python_version(),
            "platform": platform.system(), "machine": platform.machine(), "opencv": cv2.__version__,
            "video_sha256": digest.hexdigest(), "positions_ms": POSITIONS_MS,
            "max_edge": 640, "jpeg_quality": 95, "same_frames_across_trials": True,
            "median_trial_mean_read_ms": round(median(
                sum(f["read_ms"] for f in t["frames"]) / len(t["frames"]) for t in trials), 3),
            "trials": trials, "http_or_inference_measured": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, help="authorized local video >= 2.2 s; default synthetic MJPG")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True, help="new private JSON, no images or paths")
    args = parser.parse_args()
    if args.repeats <= 0:
        parser.error("repeats must be positive")
    with TemporaryDirectory(prefix="sonar-reader-") as directory:
        video = args.video or Path(directory) / "synthetic.avi"
        if args.video is None:
            synthetic_video(video)
        result = measure(video, args.repeats)
        result["input_kind"] = "authorized_local_video" if args.video else "original_synthetic_MJPG"
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({"median_trial_mean_read_ms": result["median_trial_mean_read_ms"],
                      "same_frames_across_trials": result["same_frames_across_trials"]}))


if __name__ == "__main__":
    main()
