"""Reproducible headless smoke/latency benchmark; never writes images or tracks."""

import argparse
import json
import math
from pathlib import Path
import platform
from statistics import mean
from time import perf_counter

from .core import Detection, Frame, VisionService


class SyntheticBackend:
    """Scripted detections, NOT a model or tracking accuracy evaluation."""

    def infer(self, image):
        return [Detection("person", 0.9, (0.1, 0.2, 0.3, 0.8), "1")]

    def close(self):
        pass


def summarize(latencies):
    if not latencies or any(not math.isfinite(v) or v < 0 for v in latencies):
        raise ValueError("need nonempty finite nonnegative latency samples")
    ordered = sorted(latencies)
    return {"samples": len(ordered), "mean_ms": mean(ordered),
            "p50_ms": ordered[math.ceil(0.5 * len(ordered)) - 1],
            "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1],
            "max_ms": ordered[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, help="Trusted local YOLO weights; absent = scripted backend")
    parser.add_argument("--video", type=Path, help="Authorized local clip; otherwise blank synthetic images")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 1 or args.warmup < 0:
        parser.error("frames must be positive and warmup nonnegative")
    if args.video and (not args.weights or not args.video.is_file()):
        parser.error("video requires real weights and an existing file")
    if args.output.exists():
        parser.error("output already exists; use a new path")

    capture = None
    metadata = {"backend": "scripted", "model": None}
    image = None
    source_fps = None
    shape = None
    if args.weights:
        import cv2
        import numpy as np
        from .ultralytics_backend import UltralyticsFactory, VisionConfig
        factory = UltralyticsFactory(args.weights, VisionConfig(
            confidence=args.confidence, image_size=args.image_size, device=args.device))
        metadata = factory.metadata
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        if args.video:
            capture = cv2.VideoCapture(str(args.video))
            source_fps = capture.get(cv2.CAP_PROP_FPS)
            if not capture.isOpened() or not math.isfinite(source_fps) or source_fps <= 0:
                capture.release()
                raise ValueError("video must open and report positive finite FPS")
    else:
        factory = SyntheticBackend

    service = VisionService(factory)
    service.open("benchmark", "benchmark-session")
    latency = []
    wall_started = None
    last = None
    reason = "frame_limit"
    try:
        for i in range(args.frames + args.warmup):
            if i == args.warmup:
                wall_started = perf_counter()
            if capture is not None:
                ok, image = capture.read()
                if not ok:
                    reason = "end_of_video_or_decode_failure"
                    break
            shape = list(image.shape[:2]) if image is not None else None
            timestamp = round(i * 1000 / source_fps) if source_fps else i * 33
            started = perf_counter()
            last = service.process(Frame("benchmark", "benchmark-session", str(i), timestamp, image))
            if i >= args.warmup:
                latency.append((perf_counter() - started) * 1000)
        elapsed = perf_counter() - wall_started if wall_started is not None else 0
    finally:
        if capture is not None:
            capture.release()
        service.close("benchmark", "benchmark-session")
    if not latency:
        raise ValueError("no measured frames after warmup")
    report = {
        "schema_version": 1, "configuration": metadata,
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "input": "authorized_local_video" if args.video else "synthetic_no_accuracy_evidence",
        "image_height_width": shape, "source_fps": source_fps,
        "timestamp_basis": "frame_index/source_fps" if source_fps else "synthetic_33ms",
        "warmup_frames": args.warmup, "stop_reason": reason,
        "processing_latency": summarize(latency),
        "effective_fps": len(latency) / elapsed,
        "measured_wall_seconds": elapsed,
        "last_frame_object_count": len(last.detections),
        "limitations": ["No identity ground truth or accuracy metric", "No network, firmware or safety validation",
                        "Latency includes detection, tracking and normalization; FPS also includes decoding",
                        "Warmup excluded; model loading excluded; no frames or identities saved"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
