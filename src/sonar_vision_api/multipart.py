"""Exactly two multipart parts: `metadata` (application/json) and `image` (image/jpeg).

Parsed from an already size-limited body with python-multipart's low-level
parser, so part content types are checked even when the client sends no filename.
"""

from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import MultipartParser, parse_options_header

from .errors import ApiError
from .validation import MAX_METADATA_BYTES

EXPECTED = {"metadata": b"application/json", "image": b"image/jpeg"}


def parse_form(body: bytes, content_type: str | None) -> tuple[bytes, bytes]:
    kind, params = parse_options_header(content_type)
    if kind != b"multipart/form-data" or not params.get(b"boundary"):
        raise ApiError(415, "request_not_multipart")
    parts, state = [], {}

    def on_part_begin():
        state.update(headers={}, chunks=[], field=b"")

    def on_header_field(data, start, end):
        state["field"] += data[start:end]

    def on_header_value(data, start, end):
        name = state["field"].lower().decode("latin-1")
        state["headers"][name] = state["headers"].get(name, b"") + data[start:end]

    def on_header_end():
        state["field"] = b""

    def on_part_data(data, start, end):
        if len(parts) >= len(EXPECTED):
            raise ApiError(400, "multipart_extra_part")
        state["chunks"].append(data[start:end])

    def on_part_end():
        parts.append((state["headers"], b"".join(state["chunks"])))

    def on_end():
        state["ended"] = True

    parser = MultipartParser(params[b"boundary"], {
        "on_part_begin": on_part_begin, "on_header_field": on_header_field,
        "on_header_value": on_header_value, "on_header_end": on_header_end,
        "on_part_data": on_part_data, "on_part_end": on_part_end, "on_end": on_end,
    }, max_header_count=4, max_header_size=1024)
    try:
        parser.write(body)
        parser.finalize()
    except MultipartParseError:
        raise ApiError(400, "multipart_malformed") from None
    if not state.get("ended"):
        raise ApiError(400, "multipart_incomplete")

    found = {}
    for headers, payload in parts:
        disposition, options = parse_options_header(headers.get("content-disposition"))
        name = options.get(b"name", b"").decode("utf-8", "replace")
        if disposition != b"form-data" or name not in EXPECTED or name in found:
            raise ApiError(400, "multipart_parts")
        media, _ = parse_options_header(headers.get("content-type"))
        if media != EXPECTED[name]:
            raise ApiError(415, f"{name}_media_type")
        found[name] = payload
    if set(found) != set(EXPECTED):
        raise ApiError(400, "multipart_parts")
    if len(found["metadata"]) > MAX_METADATA_BYTES:
        raise ApiError(400, "metadata_too_large")
    return found["metadata"], found["image"]
