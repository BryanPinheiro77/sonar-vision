"""Pinned Ultralytics adapter: shared detector, independent ByteTrack per session.

Imports are optional; importing sonar_vision does not load torch or download models.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from importlib.metadata import version
from itertools import count
import math
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from .core import Busy, Detection, normalize_class


@dataclass(frozen=True)
class VisionConfig:
    confidence: float = 0.35
    image_size: int = 640
    device: str = "cpu"
    track_high_thresh: float = 0.25
    track_low_thresh: float = 0.1
    new_track_thresh: float = 0.25
    track_buffer: int = 60
    match_thresh: float = 0.8
    fuse_score: bool = True
    max_detections: int = 300

    def __post_init__(self):
        for value in (self.confidence, self.track_high_thresh, self.track_low_thresh,
                      self.new_track_thresh, self.match_thresh):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("thresholds must be finite in [0,1]")
        for value in (self.image_size, self.track_buffer, self.max_detections):
            if type(value) is not int or value <= 0:
                raise ValueError("sizes must be positive integers")
        if self.track_low_thresh >= self.track_high_thresh:
            raise ValueError("low tracker threshold must be below high threshold")


def create_tracker(config: VisionConfig):
    """Avoid BaseTrack's process-global ID counter (including reset side effects)."""
    from ultralytics.trackers.byte_tracker import BYTETracker, STrack

    ids = count(1)

    class SessionTrack(STrack):
        @staticmethod
        def next_id():
            return next(ids)

    class SessionTracker(BYTETracker):
        track_class = SessionTrack

        @staticmethod
        def reset_id():
            # Lifecycle reset replaces this tracker, with a new counter + epoch.
            pass

    return SessionTracker(SimpleNamespace(**asdict(config)))


class UltralyticsFactory:
    """Loads trusted local weights once. Call to allocate a fresh session backend."""

    def __init__(self, weights: str | Path, config: VisionConfig | None = None):
        path = Path(weights)
        if not path.is_file() or path.suffix != ".pt":
            raise ValueError("provide an existing trusted local .pt file; no implicit downloads")
        if version("ultralytics") != "8.4.137":
            raise RuntimeError("adapter requires ultralytics==8.4.137; rerun tests before upgrading")
        from ultralytics import YOLO

        self.config = config or VisionConfig()
        self._model = YOLO(str(path), task="detect")
        if self._model.task != "detect":
            raise ValueError("only axis-aligned object detection models are supported")
        self._lock = Lock()
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        self.metadata = {
            "model": path.name, "weights_sha256": digest.hexdigest(),
            "packages": {p: version(p) for p in ("ultralytics", "opencv-python", "lap", "torch", "numpy")},
            "config": asdict(self.config), "tracker": "ByteTrack",
        }

    def __call__(self):
        return UltralyticsBackend(self._predict, self.config)

    def _predict(self, image):
        if not self._lock.acquire(blocking=False):
            raise Busy("detector busy")
        try:
            return self._model.predict(
                image, conf=self.config.confidence, imgsz=self.config.image_size,
                device=self.config.device, max_det=self.config.max_detections,
                verbose=False, save=False,
            )[0]
        finally:
            self._lock.release()


class UltralyticsBackend:
    def __init__(self, predict, config: VisionConfig):
        self._predict = predict
        self._tracker = create_tracker(config)
        self._shape = None

    def infer(self, image):
        import numpy as np

        if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
                or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1):
            raise ValueError("image must be a nonempty HxWx3 BGR uint8 array")
        if self._tracker is None:
            raise RuntimeError("backend closed")
        shape = image.shape[:2]
        if self._shape is not None and shape != self._shape:
            raise ValueError("resolution changed: reset tracker before processing")
        self._shape = shape
        result = self._predict(image)
        boxes = result.boxes.cpu().numpy()
        # Update even with zero detections, so missing-frame aging still runs.
        tracks = self._tracker.update(boxes, image)
        # ByteTrack row = xyxy, ID, score, class, original detection index.
        # Preserve all detections; unconfirmed/unmatched ones get explicit None.
        ids = {int(row[-1]): str(int(row[4])) for row in tracks}
        h, w = shape
        detections = []
        for i, (xyxy, score, cls) in enumerate(zip(boxes.xyxy, boxes.conf, boxes.cls)):
            coords = tuple(float(v) for v in xyxy)
            if not all(math.isfinite(v) for v in coords):
                raise ValueError("nonfinite box from model")
            normalized = tuple(max(0.0, min(1.0, v / scale))
                               for v, scale in zip(coords, (w, h, w, h)))
            if normalized[0] >= normalized[2] or normalized[1] >= normalized[3]:
                continue
            detections.append(Detection(normalize_class(result.names[int(cls)]),
                                        float(score), normalized, ids.get(i)))
        return detections

    def close(self):
        self._tracker = None
        self._shape = None
