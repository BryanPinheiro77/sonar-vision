"""Strict request validation before any effect: metadata JSON and JPEG header."""

from dataclasses import dataclass
import json
import re

from sonar_vision.core import identifier

from .errors import ApiError

MAX_METADATA_BYTES = 1024
METADATA_FIELDS = {"version", "session_id", "frame_id", "captured_at_ms"}
_COUNTER = re.compile(r"0|[1-9][0-9]*")
# Start-of-frame markers carry the dimensions; C4/C8/CC are not frames.
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


@dataclass(frozen=True)
class Metadata:
    session_id: str
    frame_id: str
    captured_at_ms: int


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON key")
    return dict(pairs)


def _no_constants(name):
    raise ValueError("NaN/Infinity are not JSON")


def parse_metadata(raw: bytes) -> Metadata:
    if len(raw) > MAX_METADATA_BYTES:
        raise ApiError(400, "metadata_too_large")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                          parse_constant=_no_constants)
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "metadata_not_json") from None
    # Extra fields are rejected in 0.1; absent fields never get silent defaults.
    if not isinstance(data, dict) or set(data) != METADATA_FIELDS:
        raise ApiError(400, "metadata_fields")
    if data["version"] != "0.1":
        raise ApiError(400, "metadata_version")
    session_id, frame_id, captured = data["session_id"], data["frame_id"], data["captured_at_ms"]
    try:
        identifier(session_id)
        identifier(frame_id)
    except ValueError:
        raise ApiError(400, "metadata_identifier") from None
    if not _COUNTER.fullmatch(frame_id):
        raise ApiError(400, "metadata_frame_id")
    if type(captured) is not int or not 0 <= captured <= 2**53 - 1:
        raise ApiError(400, "metadata_captured_at_ms")
    return Metadata(session_id, frame_id, captured)


def jpeg_dimensions(data: bytes, max_pixels: int) -> tuple[int, int]:
    """Return (height, width) from the JPEG header, before decoding any pixel."""
    if not data.startswith(b"\xff\xd8\xff"):
        raise ApiError(415, "image_not_jpeg")
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            raise ApiError(400, "jpeg_marker")
        marker = data[i + 1]
        if marker == 0xFF:  # fill byte
            i += 1
            continue
        if marker in (0x01, *range(0xD0, 0xD8)):  # markers without length
            i += 2
            continue
        if marker in (0xD9, 0xDA):  # EOI/SOS before a frame header
            break
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if length < 2 or i + 2 + length > len(data):
            raise ApiError(400, "jpeg_segment")
        if marker in _SOF:
            if length < 7:
                raise ApiError(400, "jpeg_frame_header")
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            if height == 0 or width == 0:
                raise ApiError(400, "jpeg_dimensions")
            if height * width > max_pixels:
                raise ApiError(413, "image_pixels")
            return height, width
        i += 2 + length
    raise ApiError(400, "jpeg_without_frame")
