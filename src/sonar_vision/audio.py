"""Deterministic, bounded audio suggestions for #31; no playback or local risk."""

from dataclasses import dataclass
import math
from numbers import Real
from time import monotonic
from uuid import uuid4

from .core import CLASSES, identifier

DIRECTIONS = frozenset({"left", "center", "right", "unknown"})
MOVEMENTS = frozenset({"approaching", "receding", "crossing", "stable", "unknown"})
NAMES = {"person": "Pessoa", "car": "Carro", "motorcycle": "Moto",
         "bus": "Ônibus", "bicycle": "Bicicleta", "chair": "Cadeira",
         "dining_table": "Mesa", "dog": "Cachorro", "stairs": "Escada"}
SIDES = {"left": "à esquerda", "center": "ao centro", "right": "à direita"}
MOTION = {"approaching": "com aproximação aparente",
          "receding": "com afastamento aparente",
          "crossing": "com movimento lateral aparente"}
FIELDS = {"version", "type", "session_id", "message_id", "frame_id",
          "captured_at_ms", "valid_for_ms", "tracker_epoch", "objects"}
OBJECT_FIELDS = {"track_id", "class_name", "confidence", "direction",
                 "movement", "stair_direction"}


@dataclass(frozen=True)
class AudioConfig:
    """Required experimental choices. No implicit production policy."""
    confidence_min: float
    track_cooldown_ms: int
    semantic_cooldown_ms: int
    memory_ttl_ms: int
    max_tracks: int
    max_semantics: int
    class_order: tuple[str, ...]

    def __post_init__(self):
        if (isinstance(self.confidence_min, bool)
                or not isinstance(self.confidence_min, Real)
                or not math.isfinite(self.confidence_min)
                or not 0 <= self.confidence_min <= 1):
            raise ValueError("invalid confidence threshold")
        for value in (self.track_cooldown_ms, self.semantic_cooldown_ms,
                      self.memory_ttl_ms, self.max_tracks, self.max_semantics):
            if type(value) is not int or value <= 0:
                raise ValueError("limits must be positive integers")
        if self.memory_ttl_ms < max(self.track_cooldown_ms, self.semantic_cooldown_ms):
            raise ValueError("memory TTL must preserve cooldowns")
        if (not isinstance(self.class_order, tuple)
                or len(self.class_order) != len(NAMES)
                or set(self.class_order) != set(NAMES)):
            raise ValueError("class_order must list each spoken class once")


def _integer(value, *, positive=False):
    return type(value) is int and (1 if positive else 0) <= value <= 2**53 - 1


def _validate(observation):
    if not isinstance(observation, dict) or set(observation) != FIELDS:
        raise ValueError("invalid observation fields")
    if observation["version"] != "0.1" or observation["type"] != "visual_observation":
        raise ValueError("unsupported observation")
    for name in ("session_id", "message_id", "frame_id", "tracker_epoch"):
        identifier(observation[name])
    frame = observation["frame_id"]
    if not frame.isascii() or not frame.isdecimal() or str(int(frame)) != frame:
        raise ValueError("invalid frame counter")
    if not _integer(observation["captured_at_ms"]) or not _integer(
            observation["valid_for_ms"], positive=True):
        raise ValueError("invalid timestamps")
    objects = observation["objects"]
    if not isinstance(objects, list) or len(objects) > 20:
        raise ValueError("invalid object count")
    ids = set()
    for obj in objects:
        if not isinstance(obj, dict) or set(obj) != OBJECT_FIELDS:
            raise ValueError("invalid object fields")
        if obj["track_id"] is not None:
            identifier(obj["track_id"])
            if obj["track_id"] in ids:
                raise ValueError("duplicate track ID")
            ids.add(obj["track_id"])
        score = obj["confidence"]
        if (isinstance(score, bool) or not isinstance(score, Real)
                or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("invalid confidence")
        if (not isinstance(obj["class_name"], str) or obj["class_name"] not in CLASSES
                or not isinstance(obj["direction"], str) or obj["direction"] not in DIRECTIONS
                or not isinstance(obj["movement"], str) or obj["movement"] not in MOVEMENTS):
            raise ValueError("invalid object vocabulary")
        stair = obj["stair_direction"]
        if obj["class_name"] == "stairs":
            if not isinstance(stair, str) or stair not in {"up", "down", "unknown"}:
                raise ValueError("invalid stairs direction")
        elif stair is not None:
            raise ValueError("unexpected stairs direction")


def _signature(obj):
    # Stable and unknown movement produce the same spoken content.
    return (obj["class_name"], obj["direction"],
            obj["movement"] if obj["movement"] in MOTION else "unknown",
            obj["stair_direction"])


def _text(signature):
    cls, direction, movement, stair = signature
    parts = [NAMES[cls]]
    if cls == "stairs" and stair in {"up", "down"}:
        parts.append("de subida" if stair == "up" else "de descida")
    if direction in SIDES:
        parts.append(SIDES[direction])
    if movement in MOTION:
        parts.append(MOTION[movement])
    return " ".join(parts)


class AudioPolicy:
    """One owner per authenticated device/session; caller serializes operations.

    The elapsed argument is a known LOWER BOUND on capture age. Device clocks
    cannot be compared to server clocks. ESP32 still checks actual age/orientation.
    This selector emits at most one suggestion and owns no playback queue.
    """
    def __init__(self, session_id, config: AudioConfig, *, clock=monotonic):
        identifier(session_id)
        self.session_id, self.config, self.clock = session_id, config, clock
        self._tracks = {}
        self._semantics = {}
        self._last_frame = -1
        self._last_capture = -1
        self._last_now = None

    def select(self, observation, *, capture_age_lower_bound_ms):
        _validate(observation)  # reject the complete envelope before effects
        if not _integer(capture_age_lower_bound_ms):
            raise ValueError("capture age lower bound must be a nonnegative integer")
        if observation["session_id"] != self.session_id:
            raise ValueError("session mismatch")
        frame, capture = int(observation["frame_id"]), observation["captured_at_ms"]
        if frame <= self._last_frame or capture < self._last_capture:
            raise ValueError("duplicate, out-of-order frame or clock regression")
        now = self.clock() * 1000
        if not math.isfinite(now) or now < 0 or (self._last_now is not None and now < self._last_now):
            raise ValueError("invalid policy clock")
        self._last_frame, self._last_capture, self._last_now = frame, capture, now
        ttl = self.config.memory_ttl_ms
        self._tracks = {k: v for k, v in self._tracks.items() if now - v[2] < ttl}
        self._semantics = {k: t for k, t in self._semantics.items() if now - t < ttl}
        if capture_age_lower_bound_ms >= min(observation["valid_for_ms"], 1000):
            return None
        candidates = []
        epoch = observation["tracker_epoch"]
        for index, obj in enumerate(observation["objects"]):
            if obj["class_name"] not in NAMES or obj["confidence"] < self.config.confidence_min:
                continue
            signature = _signature(obj)
            key = (epoch, obj["track_id"]) if obj["track_id"] is not None else None
            previous = self._tracks.get(key) if key is not None else None
            if previous is not None:
                if previous[0] == signature:
                    # Refresh presence, but do not periodically narrate a stable track.
                    self._tracks[key] = (previous[0], previous[1], now)
                    continue
                if now - previous[1] < self.config.track_cooldown_ms:
                    continue
            last_equivalent = self._semantics.get(signature)
            if last_equivalent is not None and now - last_equivalent < self.config.semantic_cooldown_ms:
                continue
            # Do not evict live suppression state to admit new targets.
            if key is not None and key not in self._tracks and len(self._tracks) >= self.config.max_tracks:
                continue
            if signature not in self._semantics and len(self._semantics) >= self.config.max_semantics:
                continue
            rank = (0 if previous is not None else 1,
                    self.config.class_order.index(obj["class_name"]),
                    -obj["confidence"], index)
            candidates.append((rank, key, signature))
        if not candidates:
            return None
        _, key, signature = min(candidates, key=lambda item: item[0])
        text = _text(signature)
        if not text or len(text) > 120:
            raise ValueError("text exceeds protocol limit")
        if key is not None:
            self._tracks[key] = (signature, now, now)
        self._semantics[signature] = now
        return {
            "version": "0.1", "type": "audio_suggestion",
            "session_id": self.session_id, "message_id": uuid4().hex,
            "frame_id": observation["frame_id"], "captured_at_ms": capture,
            "valid_for_ms": min(observation["valid_for_ms"], 1000),
            "observation_id": observation["message_id"],
            "text": text, "directional": signature[1] != "unknown" or signature[2] in MOTION,
        }
