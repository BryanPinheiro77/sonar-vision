"""Dependency-free interface and bounded session lifecycle for issue #21."""

from collections import deque
from dataclasses import dataclass, field
import math
from numbers import Real
import re
from threading import Lock
from time import monotonic, perf_counter
from typing import Callable, Protocol
from uuid import uuid4


CLASSES = frozenset({"person", "car", "motorcycle", "bus", "bicycle", "chair",
                     "dining_table", "dog", "stairs", "traffic_light", "unknown"})


def identifier(value: str) -> None:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 128:
        raise ValueError("IDs must contain 1..128 UTF-8 bytes")


def normalize_class(name: str) -> str:
    name = name.strip().lower().replace(" ", "_")
    return name if name in CLASSES else "unknown"


@dataclass(frozen=True)
class Frame:
    device_id: str  # supplied by the authenticated caller, not untrusted metadata
    session_id: str
    frame_id: str
    captured_at_ms: int
    image: object  # BGR uint8 HxWx3 for the real backend; opaque for test backends

    def __post_init__(self):
        for value in (self.device_id, self.session_id, self.frame_id):
            identifier(value)
        if not re.fullmatch(r"0|[1-9][0-9]*", self.frame_id):
            raise ValueError("frame_id must be a canonical decimal counter")
        if type(self.captured_at_ms) is not int or not 0 <= self.captured_at_ms <= 2**53 - 1:
            raise ValueError("captured_at_ms must be a nonnegative JSON-safe integer")


@dataclass(frozen=True)
class Detection:
    class_name: str
    confidence: float
    box: tuple[float, float, float, float]  # normalized xyxy in original image
    track_id: str | None = None
    stair_direction: str | None = None

    def __post_init__(self):
        if self.class_name not in CLASSES:
            raise ValueError("class_name must be normalized")
        if (isinstance(self.confidence, bool) or not isinstance(self.confidence, Real)
                or not math.isfinite(self.confidence) or not 0 <= self.confidence <= 1):
            raise ValueError("invalid confidence")
        object.__setattr__(self, "confidence", float(self.confidence))
        if len(self.box) != 4 or not all(math.isfinite(v) and 0 <= v <= 1 for v in self.box):
            raise ValueError("invalid normalized box")
        if self.box[0] >= self.box[2] or self.box[1] >= self.box[3]:
            raise ValueError("box must have positive area")
        object.__setattr__(self, "box", tuple(self.box))
        if self.track_id is not None:
            identifier(self.track_id)
        if self.class_name == "stairs":
            if self.stair_direction is None:
                object.__setattr__(self, "stair_direction", "unknown")
            elif self.stair_direction not in ("up", "down", "unknown"):
                raise ValueError("invalid stair direction")
        elif self.stair_direction is not None:
            raise ValueError("stair direction is only valid for stairs")


class Backend(Protocol):
    def infer(self, image: object) -> list[Detection]: ...
    def close(self) -> None: ...


class Busy(RuntimeError):
    """No admission capacity; caller must not queue the old frame."""


class SessionMissing(RuntimeError):
    """Explicit open required after close, expiry or backend failure."""


@dataclass(frozen=True)
class Sample:
    frame_id: str
    captured_at_ms: int
    box: tuple[float, float, float, float]


@dataclass
class _Track:
    samples: deque
    last_seen: int
    missing: bool = False


@dataclass
class _Session:
    backend: Backend
    epoch: str = field(default_factory=lambda: uuid4().hex)
    last_frame: int = -1
    last_capture: int = -1
    last_used: float = 0
    processed: int = 0
    tracks: dict[str, _Track] = field(default_factory=dict)


@dataclass(frozen=True)
class Result:
    session_id: str
    frame_id: str
    captured_at_ms: int
    tracker_epoch: str
    message_id: str
    detections: tuple[Detection, ...]
    events: tuple[tuple[str, str], ...]  # diagnostic (event, track_id), not identity truth
    history: dict[str, tuple[Sample, ...]]  # detached copy, never sent to the glasses
    processing_ms: float

    def observation(self) -> dict:
        """Existing v0.1 wire contract: no boxes, histories, risk or extra keys.

        Direction stays unknown until sector policy/calibration is implemented.
        Movement belongs to #11; stair direction is supplied by #16 when enabled.
        """
        return {
            "version": "0.1", "type": "visual_observation",
            "session_id": self.session_id, "message_id": self.message_id,
            "frame_id": self.frame_id, "captured_at_ms": self.captured_at_ms,
            "valid_for_ms": 1000, "tracker_epoch": self.tracker_epoch,
            "objects": [{
                "track_id": d.track_id, "class_name": d.class_name,
                "confidence": d.confidence, "direction": "unknown",
                "movement": "unknown",
                "stair_direction": d.stair_direction,
            } for d in self.detections],
        }


class VisionService:
    """One nonqueued operation per instance; factories MUST create fresh trackers.

    This conservative prototype serializes even different devices. API workers
    must route a session to its owning instance; #24 owns HTTP/auth/cancellation.
    """

    def __init__(self, factory: Callable[[], Backend], *, max_sessions=8,
                 history_size=60, max_tracks=256, missing_frames=60,
                 idle_seconds=60.0, clock=monotonic):
        for value in (max_sessions, history_size, max_tracks, missing_frames):
            if type(value) is not int or value <= 0:
                raise ValueError("capacity parameters must be positive integers")
        if not math.isfinite(idle_seconds) or idle_seconds <= 0:
            raise ValueError("idle_seconds must be positive and finite")
        self.factory, self.clock = factory, clock
        self.max_sessions, self.history_size = max_sessions, history_size
        self.max_tracks, self.missing_frames = max_tracks, missing_frames
        self.idle_seconds = idle_seconds
        self._sessions: dict[tuple[str, str], _Session] = {}
        self._lock = Lock()

    def _enter(self):
        if not self._lock.acquire(blocking=False):
            raise Busy("vision service is busy; discard rather than queue")

    def _drop(self, key):
        state = self._sessions.pop(key)
        state.tracks.clear()
        state.backend.close()

    def _reap(self):
        now = self.clock()
        for key, state in list(self._sessions.items()):
            if now - state.last_used >= self.idle_seconds:
                self._drop(key)

    def open(self, device_id: str, session_id: str) -> str:
        identifier(device_id)
        identifier(session_id)
        self._enter()
        try:
            self._reap()
            key = (device_id, session_id)
            if key in self._sessions:
                return self._sessions[key].epoch
            if len(self._sessions) >= self.max_sessions:
                raise Busy("session capacity reached")
            state = _Session(self.factory(), last_used=self.clock())
            self._sessions[key] = state
            return state.epoch
        finally:
            self._lock.release()

    def close(self, device_id: str, session_id: str) -> None:
        self._enter()
        try:
            if (device_id, session_id) in self._sessions:
                self._drop((device_id, session_id))
        finally:
            self._lock.release()

    def reset(self, device_id: str, session_id: str) -> str:
        self._enter()
        try:
            self._reap()
            key = (device_id, session_id)
            if key not in self._sessions:
                raise SessionMissing("session is not open")
            previous = self._sessions[key]
            self._drop(key)
            state = _Session(self.factory(), last_frame=previous.last_frame,
                             last_capture=previous.last_capture, last_used=self.clock())
            self._sessions[key] = state
            return state.epoch
        finally:
            self._lock.release()

    def process(self, frame: Frame) -> Result:
        self._enter()
        try:
            self._reap()
            key = (frame.device_id, frame.session_id)
            if key not in self._sessions:
                raise SessionMissing("session expired or not opened")
            state = self._sessions[key]
            if int(frame.frame_id) <= state.last_frame or frame.captured_at_ms < state.last_capture:
                raise ValueError("duplicate/out-of-order frame or clock regression")
            started = perf_counter()
            try:
                detections = tuple(state.backend.infer(frame.image))
                if not all(isinstance(d, Detection) for d in detections):
                    raise ValueError("backend returned invalid detections")
                ids = [d.track_id for d in detections if d.track_id is not None]
                if len(ids) != len(set(ids)):
                    raise ValueError("duplicate tracking IDs in one frame")
                # Keep the complete tracker update but bound exposed objects/history.
                detections = tuple(sorted(detections, key=lambda d: -d.confidence)[:20])
                events = self._update(state, detections, frame)
                result = Result(frame.session_id, frame.frame_id, frame.captured_at_ms,
                                state.epoch, uuid4().hex, detections, tuple(events),
                                {k: tuple(t.samples) for k, t in state.tracks.items()},
                                (perf_counter() - started) * 1000)
            except Exception:
                # A failed inference may have partially mutated its tracker.
                self._drop(key)
                raise
            state.last_frame = int(frame.frame_id)
            state.last_capture = frame.captured_at_ms
            state.last_used = self.clock()
            return result
        finally:
            self._lock.release()

    def _update(self, state, detections, frame):
        state.processed += 1
        events = []
        observed = {d.track_id for d in detections if d.track_id is not None}
        for track_id, track in list(state.tracks.items()):
            if state.processed - track.last_seen > self.missing_frames:
                del state.tracks[track_id]
                events.append(("expired", track_id))
            elif track_id not in observed and not track.missing:
                track.missing = True
                events.append(("lost", track_id))
        for detection in detections:
            track_id = detection.track_id
            if track_id is None:
                continue
            if track_id not in state.tracks:
                if len(state.tracks) >= self.max_tracks:
                    oldest = min(state.tracks, key=lambda k: state.tracks[k].last_seen)
                    del state.tracks[oldest]
                    events.append(("evicted", oldest))
                state.tracks[track_id] = _Track(deque(maxlen=self.history_size), state.processed)
                events.append(("appeared", track_id))
            track = state.tracks[track_id]
            if track.missing:
                events.append(("recovered", track_id))
                track.samples.clear()  # do not bridge unobserved motion across gaps
                track.missing = False
            track.samples.append(Sample(frame.frame_id, frame.captured_at_ms, detection.box))
            track.last_seen = state.processed
        return events
