"""Pinned Ultralytics adapter: shared detector, independent ByteTrack per session.

Imports are optional; importing sonar_vision does not load torch or download models.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from importlib.metadata import version
from itertools import count
import math
from pathlib import Path
from threading import Lock
from types import SimpleNamespace

from .core import Busy, Detection, normalize_class


STAIR_ASSOCIATION_IOU = 0.5  # frozen exploratory #16 image protocol


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iou(first, second) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    area_first = (first[2] - first[0]) * (first[3] - first[1])
    area_second = (second[2] - second[0]) * (second[3] - second[1])
    return intersection / (area_first + area_second - intersection)


def _stair_direction(candidates) -> str:
    directions = {item.stair_direction for item in candidates}
    return directions.pop() if len(directions) == 1 else "unknown"


def _merge_stairs(base: list[Detection], candidates: list[Detection]) -> list[Detection]:
    """Keep primary detections; add unmatched local stairs without tracker IDs."""
    merged = list(base)
    groups = {index: [] for index, item in enumerate(base) if item.class_name == "stairs"}
    unmatched = []
    for candidate in candidates:
        best = max(((index, _iou(candidate.box, base[index].box)) for index in groups),
                   key=lambda pair: pair[1], default=None)
        if best is not None and best[1] >= STAIR_ASSOCIATION_IOU:
            groups[best[0]].append(candidate)
        else:
            unmatched.append(candidate)
    for index, group in groups.items():
        if group:
            merged[index] = replace(base[index], stair_direction=_stair_direction(group))

    # Merge overlapping specialist boxes, including conflicting up/down boxes.
    clusters: list[list[Detection]] = []
    for candidate in sorted(unmatched, key=lambda item: -item.confidence):
        matches = [group for group in clusters
                   if any(_iou(candidate.box, item.box) >= STAIR_ASSOCIATION_IOU
                          for item in group)]
        if not matches:
            clusters.append([candidate])
        else:
            matches[0].append(candidate)
            for group in matches[1:]:
                matches[0].extend(group)
                clusters.remove(group)
    for cluster in clusters:
        merged.append(replace(cluster[0], stair_direction=_stair_direction(cluster)))
    return merged


@dataclass(frozen=True)
class VisionConfig:
    confidence: float = 0.35
    image_size: int = 640
    device: str = "cpu"
    track_high_thresh: float = 0.35
    track_low_thresh: float = 0.25
    new_track_thresh: float = 0.35
    track_buffer: int = 60
    match_thresh: float = 0.8
    fuse_score: bool = True
    max_detections: int = 300
    association_confidence: float = 0.25
    reactivation_margin: float = 0.02

    def __post_init__(self):
        for value in (self.confidence, self.association_confidence,
                      self.track_high_thresh, self.track_low_thresh,
                      self.new_track_thresh, self.match_thresh, self.reactivation_margin):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("thresholds must be finite in [0,1]")
        for value in (self.image_size, self.track_buffer, self.max_detections):
            if type(value) is not int or value <= 0:
                raise ValueError("sizes must be positive integers")
        if self.track_low_thresh >= self.track_high_thresh:
            raise ValueError("low tracker threshold must be below high threshold")


def _guard_reactivation_costs(costs, tracks, detections, threshold, margin):
    """Reject ambiguous lost-track pairs without changing active-track costs.

    All decisions use the original matrix. Two ambiguous lost hypotheses may
    both be rejected; this deliberately favors abstention over forced identity.
    """
    if margin == 0 or len(tracks) < 2 or not detections:
        return costs
    import numpy as np
    from ultralytics.trackers.basetrack import TrackState

    lost = np.array([track.state == TrackState.Lost for track in tracks])
    if not lost.any():
        return costs
    classes = np.array([track.cls for track in tracks])
    detection_classes = np.array([detection.cls for detection in detections])
    viable = (classes[:, None] == detection_classes) & (costs <= threshold)
    eligible_costs = np.where(viable, costs, np.inf)
    # Per detection, the cheapest competing row is either the best or the
    # second-best eligible row. This avoids a quadratic Python search.
    best_two = np.partition(eligible_costs, 1, axis=0)[:2]
    best_row = np.argmin(eligible_costs, axis=0)
    competing_cost = np.where(np.arange(len(tracks))[:, None] == best_row,
                              best_two[1], best_two[0])
    blocked = lost[:, None] & viable & (competing_cost <= costs + margin)
    guarded = costs.copy()
    guarded[blocked] = 1e6
    return guarded


def create_tracker(config: VisionConfig):
    """Avoid BaseTrack's process-global ID counter (including reset side effects)."""
    from ultralytics.trackers.byte_tracker import BYTETracker, STrack
    from ultralytics.trackers.utils import matching

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

        def _first_association(self, pool, detections, activated, refind):
            if config.reactivation_margin == 0:
                return super()._first_association(pool, detections, activated, refind)
            costs = _guard_reactivation_costs(
                self.get_dists(pool, detections), pool, detections,
                self.args.match_thresh, config.reactivation_margin)
            matches, unmatched_tracks, unmatched_detections = matching.linear_assignment(
                costs, thresh=self.args.match_thresh)
            self._apply_matches(matches, pool, detections, activated, refind)
            return unmatched_tracks, unmatched_detections

    args = SimpleNamespace(**asdict(config))
    # Weak detections may maintain an ID, but may not create one. Preserve this
    # property when a caller raises the public/output confidence cutoff.
    args.track_high_thresh = max(config.track_high_thresh, config.confidence)
    args.new_track_thresh = max(config.new_track_thresh, config.confidence)
    return SessionTracker(args)


class UltralyticsFactory:
    """Loads trusted local weights once. Call to allocate a fresh session backend."""

    def __init__(self, weights: str | Path, config: VisionConfig | None = None,
                 *, stair_direction_weights: str | Path | None = None):
        path = Path(weights)
        if not path.is_file() or path.suffix != ".pt":
            raise ValueError("provide an existing trusted local .pt file; no implicit downloads")
        direction_path = Path(stair_direction_weights) if stair_direction_weights is not None else None
        if direction_path is not None and (not direction_path.is_file() or
                                           direction_path.suffix != ".pt"):
            raise ValueError("provide existing trusted local stair direction .pt weights")
        if version("ultralytics") != "8.4.137":
            raise RuntimeError("adapter requires ultralytics==8.4.137; rerun tests before upgrading")
        from ultralytics import YOLO

        self.config = config or VisionConfig()
        self._model = YOLO(str(path), task="detect")
        if self._model.task != "detect":
            raise ValueError("only axis-aligned object detection models are supported")
        if set(self._model.names.values()) == {"stairs_up", "stairs_down"}:
            raise ValueError("pass two-class stair weights as stair_direction_weights")
        self._direction_model = YOLO(str(direction_path), task="detect") if direction_path else None
        if self._direction_model is not None and (
                self._direction_model.task != "detect" or
                set(self._direction_model.names.values()) != {"stairs_up", "stairs_down"}):
            raise ValueError("stair direction weights must detect stairs_up and stairs_down")
        self._lock = Lock()
        self.metadata = {
            "model": path.name, "weights_sha256": _file_hash(path),
            "packages": {p: version(p) for p in ("ultralytics", "opencv-python", "lap", "torch", "numpy")},
            "config": asdict(self.config), "tracker": "ByteTrack",
            "effective_detection_confidence": min(self.config.confidence,
                                                  self.config.association_confidence),
            "effective_track_high_thresh": max(self.config.confidence,
                                               self.config.track_high_thresh),
            "effective_new_track_thresh": max(self.config.confidence,
                                              self.config.new_track_thresh),
        }
        if direction_path is not None:
            self.metadata["stair_direction_model"] = direction_path.name
            self.metadata["stair_direction_sha256"] = _file_hash(direction_path)
            self.metadata["stair_association_iou"] = STAIR_ASSOCIATION_IOU

    def __call__(self):
        backend = UltralyticsBackend(self._predict, self.config)
        if self._direction_model is None:
            return backend
        return StairAugmentedBackend(backend, self._predict_stairs)

    def warmup(self):
        """Initialize inference using a disposable tracker before accepting requests."""
        import numpy as np

        backend = self()
        try:
            backend.infer(np.zeros((480, 640, 3), dtype=np.uint8))
        finally:
            backend.close()

    def _predict(self, image):
        if not self._lock.acquire(blocking=False):
            raise Busy("detector busy")
        try:
            return self._model.predict(
                image, conf=min(self.config.confidence, self.config.association_confidence),
                imgsz=self.config.image_size,
                device=self.config.device, max_det=self.config.max_detections,
                verbose=False, save=False,
            )[0]
        finally:
            self._lock.release()

    def _predict_stairs(self, image):
        if not self._lock.acquire(blocking=False):
            raise Busy("stair direction detector busy")
        try:
            return self._direction_model.predict(
                image, conf=self.config.confidence, imgsz=self.config.image_size,
                device=self.config.device, max_det=self.config.max_detections,
                verbose=False, save=False,
            )[0]
        finally:
            self._lock.release()


class StairAugmentedBackend:
    """Experimental semantic second pass; original detector/tracker stay intact."""

    def __init__(self, primary: UltralyticsBackend, predict_stairs):
        self._primary = primary
        self._predict_stairs = predict_stairs

    def infer(self, image):
        primary = self._primary.infer(image)
        result = self._predict_stairs(image)
        boxes = result.boxes.cpu().numpy()
        height, width = image.shape[:2]
        candidates = []
        for xyxy, score, cls in zip(boxes.xyxy, boxes.conf, boxes.cls):
            direction = result.names[int(cls)].removeprefix("stairs_")
            if direction not in ("up", "down"):
                raise ValueError("unexpected stair direction class")
            coords = tuple(float(value) for value in xyxy)
            if not all(math.isfinite(value) for value in coords):
                raise ValueError("nonfinite stair box from model")
            normalized = tuple(max(0.0, min(1.0, value / scale))
                               for value, scale in zip(coords, (width, height, width, height)))
            if normalized[0] >= normalized[2] or normalized[1] >= normalized[3]:
                continue
            candidates.append(Detection("stairs", float(score), normalized,
                                        stair_direction=direction))
        return _merge_stairs(primary, candidates)

    def close(self):
        self._primary.close()


class UltralyticsBackend:
    def __init__(self, predict, config: VisionConfig):
        self._predict = predict
        self._output_confidence = config.confidence
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
            if float(score) < self._output_confidence:
                continue
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
