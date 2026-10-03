"""Validate and serialize the 200 response of contract 0.1 before sending it."""

import json
import math
from numbers import Real

from sonar_vision.core import CLASSES, identifier

MAX_RESPONSE_BYTES = 16384
MAX_OBJECTS = 20
MAX_TEXT = 120
ENVELOPE = {"version", "type", "session_id", "message_id", "frame_id",
            "captured_at_ms", "valid_for_ms"}
OBSERVATION_FIELDS = ENVELOPE | {"tracker_epoch", "objects"}
OBJECT_FIELDS = {"track_id", "class_name", "confidence", "direction", "movement",
                 "stair_direction"}
AUDIO_FIELDS = ENVELOPE | {"observation_id", "text", "directional"}
DIRECTIONS = {"left", "center", "right", "unknown"}
MOVEMENTS = {"approaching", "receding", "crossing", "stable", "unknown"}


class ContractViolation(ValueError):
    """Server produced a message outside contract 0.1; never sent to the client."""


def _check(condition, reason):
    if not condition:
        raise ContractViolation(reason)


def _json_int(value, *, positive=False):
    return type(value) is int and (1 if positive else 0) <= value <= 2**53 - 1


def _ids(message, names):
    for name in names:
        try:
            identifier(message[name])
        except ValueError:
            raise ContractViolation(f"invalid {name}") from None


def validate_observation(obs) -> None:
    _check(isinstance(obs, dict) and set(obs) == OBSERVATION_FIELDS, "observation fields")
    _check(obs["version"] == "0.1" and obs["type"] == "visual_observation", "observation type")
    _ids(obs, ("session_id", "message_id", "frame_id", "tracker_epoch"))
    _check(_json_int(obs["captured_at_ms"]) and _json_int(obs["valid_for_ms"], positive=True),
           "observation times")
    objects = obs["objects"]
    _check(isinstance(objects, list) and len(objects) <= MAX_OBJECTS, "object count")
    for item in objects:
        _check(isinstance(item, dict) and set(item) == OBJECT_FIELDS, "object fields")
        if item["track_id"] is not None:
            _ids(item, ("track_id",))
        score = item["confidence"]
        _check(not isinstance(score, bool) and isinstance(score, Real)
               and math.isfinite(score) and 0 <= score <= 1, "confidence")
        _check(item["class_name"] in CLASSES and item["direction"] in DIRECTIONS
               and item["movement"] in MOVEMENTS, "object vocabulary")
        if item["class_name"] == "stairs":
            _check(item["stair_direction"] in ("up", "down", "unknown"), "stair_direction")
        else:
            _check(item["stair_direction"] is None, "stair_direction")


def validate_audio(audio, obs) -> None:
    _check(isinstance(audio, dict) and set(audio) == AUDIO_FIELDS, "audio fields")
    _check(audio["version"] == "0.1" and audio["type"] == "audio_suggestion", "audio type")
    _ids(audio, ("message_id", "observation_id"))
    # References must match the observation that produced the suggestion.
    _check(audio["observation_id"] == obs["message_id"] != audio["message_id"], "audio reference")
    for name in ("session_id", "frame_id", "captured_at_ms"):
        _check(type(audio[name]) is type(obs[name]) and audio[name] == obs[name],
               f"audio {name}")
    _check(_json_int(audio["valid_for_ms"], positive=True)
           and audio["valid_for_ms"] <= obs["valid_for_ms"], "audio validity")
    text = audio["text"]
    _check(isinstance(text, str) and text.strip() and len(text) <= MAX_TEXT, "audio text")
    _check(type(audio["directional"]) is bool, "audio directional")


def encode(obs: dict, audio: dict | None) -> bytes:
    """Serialize exactly what was validated, bounded to 16 KiB of UTF-8."""
    validate_observation(obs)
    if audio is not None:
        validate_audio(audio, obs)
    body = json.dumps({"observation": obs, "audio": audio}, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")
    _check(len(body) <= MAX_RESPONSE_BYTES, "response size")
    return body
