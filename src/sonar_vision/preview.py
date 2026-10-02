"""Local developer viewer: boxes, IDs and apparent motion, without saving media."""

import argparse
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
import platform
from time import monotonic, perf_counter

from .core import Frame, VisionService
from .trajectory import Motion, TrajectoryConfig


def video_timestamp_ms(index, fps):
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("video FPS must be finite and positive")
    return round(index*1000/fps)


def selected_frame(index, stride=1, drop_every=0):
    return index % stride == 0 and (not drop_every or (index+1) % drop_every != 0)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--video", type=Path)
    source.add_argument("--camera", type=int)
    parser.add_argument("--assume-fixed-camera", action="store_true",
                        help="Controlled experiment only: no IMU verification/compensation")
    parser.add_argument("--stride", type=int, default=1, help="Process every Nth captured frame")
    parser.add_argument("--drop-every", type=int, default=0, help="Skip every Nth captured frame")
    parser.add_argument("--max-frames", type=int, default=0, help="Processed frames; 0 = until EOF/q")
    parser.add_argument("--headless", action="store_true", help="No window; draw in memory for smoke tests")
    parser.add_argument("--output", type=Path, help="New aggregate JSON report, no images/identities")
    parser.add_argument("--trajectory-config", type=Path, help="JSON overrides of experimental parameters")
    parser.add_argument("--confidence", type=float, default=.35)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    if args.stride < 1 or args.drop_every < 0 or args.drop_every == 1 or args.max_frames < 0:
        parser.error("stride >= 1, drop-every = 0 or >= 2, max-frames >= 0")
    if args.camera is not None and args.camera < 0:
        parser.error("camera index must be nonnegative")
    if args.output and args.output.exists():
        parser.error("output already exists; choose a new path")
    return args


def draw_overlay(image, result, *, camera_motion):
    import cv2
    import numpy as np

    h, w = image.shape[:2]
    scale = min(1.0, 1280/w, 720/h)
    canvas = cv2.resize(image, (max(1, round(w*scale)), max(1, round(h*scale))))
    h, w = canvas.shape[:2]
    labels = {"unknown": "INCONCLUSIVO", "stable": "ESTAVEL (imagem)",
              "approaching": "APROX. APARENTE", "receding": "AFAST. APARENTE",
              "crossing": "CRUZANDO (imagem)"}
    for detection in result.detections:
        x1, y1, x2, y2 = detection.box
        start = (min(w-1, int(x1*w)), min(h-1, int(y1*h)))
        end = (min(w-1, int(x2*w)), min(h-1, int(y2*h)))
        motion = result.motions.get(detection.track_id, Motion(reason="no_track"))
        color = (0, 200, 255) if motion.movement == "unknown" else (255, 200, 0)
        cv2.rectangle(canvas, start, end, color, 2)
        arrow = {"left_to_right": " ->", "right_to_left": " <-"}.get(motion.lateral_direction, "")
        label = (f"ID {detection.track_id or '-'} | {detection.class_name} {detection.confidence:.2f}"
                 f" | {labels[motion.movement]}{arrow}")
        label_width = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, .42, 1)[0][0]
        label_x = max(0, min(start[0], w-label_width-2))
        cv2.putText(canvas, label, (label_x, max(15, start[1]-7)),
                    cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1, cv2.LINE_AA)
        cv2.putText(canvas, motion.reason, (label_x, min(h-5, start[1]+17)),
                    cv2.FONT_HERSHEY_SIMPLEX, .38, color, 1, cv2.LINE_AA)
        history = result.history.get(detection.track_id, ())
        points = [(min(w-1, int((s.box[0]+s.box[2])*w/2)),
                   min(h-1, int((s.box[1]+s.box[3])*h/2))) for s in history]
        for a, b in zip(points, points[1:]):
            cv2.line(canvas, a, b, color, 1, cv2.LINE_AA)
    header = np.zeros((80, w, 3), dtype=np.uint8)
    lines = ["SONAR VISION | teste visual, NAO risco/distancia/TTC",
             f"camera={camera_motion} (sem compensacao IMU) | frame={result.frame_id}",
             f"epoch={result.tracker_epoch[:8]} | processamento={result.processing_ms:.1f} ms | q: sair"]
    for i, text in enumerate(lines):
        cv2.putText(header, text, (8, 20+i*23), cv2.FONT_HERSHEY_SIMPLEX,
                    .43, (230, 230, 230), 1, cv2.LINE_AA)
    return np.concatenate((header, canvas), axis=0)


def main(argv=None):
    args = parse_args(argv)
    import cv2
    from .ultralytics_backend import UltralyticsFactory, VisionConfig

    if args.video and not args.video.is_file():
        raise ValueError("video file not found")
    config = TrajectoryConfig(**(json.loads(args.trajectory_config.read_text(encoding="utf-8"))
                                 if args.trajectory_config else {}))
    factory = UltralyticsFactory(args.weights, VisionConfig(
        confidence=args.confidence, image_size=args.image_size, device=args.device))
    service = VisionService(factory, trajectory_config=config)
    capture = cv2.VideoCapture(str(args.video) if args.video else args.camera)
    processed = skipped = index = 0
    counts, reasons = Counter(), Counter()
    status = "unknown"
    camera_motion = "fixed" if args.assume_fixed_camera else "unknown"
    started = monotonic()
    resolution = None
    source_fps = None
    try:
        if not capture.isOpened():
            raise RuntimeError("cannot open source; check path, camera index and permissions")
        if args.video:
            source_fps = capture.get(cv2.CAP_PROP_FPS)
            video_timestamp_ms(0, source_fps)  # validate before any processing
        service.open("local-preview", "preview-session")
        while not args.max_frames or processed < args.max_frames:
            step_started = perf_counter()
            ok, image = capture.read()
            captured = round((monotonic()-started)*1000)
            if not ok:
                status = "end_or_decode_failure" if args.video else "camera_read_failure"
                break
            current = index
            index += 1
            if not selected_frame(current, args.stride, args.drop_every):
                skipped += 1
                continue
            timestamp = video_timestamp_ms(current, source_fps) if args.video else captured
            resolution = list(image.shape[:2])
            result = service.process(Frame("local-preview", "preview-session", str(current),
                                           timestamp, image, camera_motion=camera_motion))
            motions = [result.motions.get(d.track_id, Motion(reason="no_track")) for d in result.detections]
            counts.update(m.movement for m in motions)
            reasons.update(m.reason for m in motions)
            processed += 1
            annotated = draw_overlay(image, result, camera_motion=camera_motion)
            if not args.headless:
                cv2.imshow("Sonar Vision - local preview", annotated)
                delay = max(1, round(1000*args.stride/source_fps-(perf_counter()-step_started)*1000)) if args.video else 1
                if cv2.waitKey(delay) & 0xFF == ord("q"):
                    status = "user_quit"
                    break
        else:
            status = "frame_limit"
    except KeyboardInterrupt:
        status = "interrupted"
    finally:
        capture.release()
        service.close("local-preview", "preview-session")
        if not args.headless:
            cv2.destroyAllWindows()
    report = {
        "schema_version": 1, "source": "video" if args.video else "camera",
        "model": factory.metadata, "trajectory": asdict(config),
        "python": platform.python_version(), "platform": platform.platform(),
        "camera_motion_assumption": camera_motion, "imu_compensation": False,
        "timestamp_basis": "frame_index/source_fps" if args.video else "host_read_completion_monotonic",
        "source_fps": source_fps, "image_height_width": resolution,
        "stride": args.stride, "drop_every": args.drop_every,
        "processed_frames": processed, "skipped_frames": skipped, "stop_reason": status,
        "movement_observations": dict(counts), "reason_observations": dict(reasons),
        "limitations": ["Counts are per-object/frame observations, not events or accuracy",
                        "No annotated identity/motion ground truth; no collision or safety validation",
                        "Fixed camera is an operator assumption, NOT IMU evidence",
                        "No media, IDs or trajectories saved; webcam timestamps approximate read completion"],
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
