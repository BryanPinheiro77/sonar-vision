"""Explicit offline model/policy options for the executable API (#52)."""

from dataclasses import fields
from hashlib import sha256
import json
from pathlib import Path

from sonar_vision.audio import AudioConfig


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_audio_config_key")
        result[key] = value
    return result


def load_audio_config(path: Path) -> AudioConfig:
    if path.stat().st_size > 8192:
        raise ValueError("audio_config_too_large")

    def reject(name):
        raise ValueError("nonfinite_audio_config")

    data = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_pairs,
        parse_constant=reject,
    )
    if not isinstance(data, dict) or set(data) != {f.name for f in fields(AudioConfig)}:
        raise ValueError("invalid_audio_config_fields")
    if not isinstance(data["class_order"], list):
        raise ValueError("invalid_audio_class_order")
    data["class_order"] = tuple(data["class_order"])
    return AudioConfig(**data)


def file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_weights(path, expected):
    actual = file_hash(path)
    if expected is not None and actual != expected:
        raise ValueError("model_hash_mismatch")
    return actual
