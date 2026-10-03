"""Shared fixtures for API tests: synthetic JPEG headers, no real images."""

import json


def jpeg(height=480, width=640) -> bytes:
    """Header-valid baseline JPEG skeleton (SOI, SOF0, SOS, EOI); not decodable pixels."""
    sof = (b"\xff\xc0\x00\x11\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big")
           + b"\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")
    sos = b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00"
    return b"\xff\xd8" + b"\xff\xe0\x00\x04ab" + sof + sos + b"\x00" + b"\xff\xd9"


def metadata(session_id="boot-1", frame_id="1", captured_at_ms=1000, **extra) -> bytes:
    data = {"version": "0.1", "session_id": session_id, "frame_id": frame_id,
            "captured_at_ms": captured_at_ms, **extra}
    return json.dumps(data).encode()


def multipart(meta: bytes, image: bytes, boundary="sonarboundary", *,
              meta_type="application/json", image_type="image/jpeg", extra=b"") -> tuple[bytes, str]:
    def part(name, ctype, payload):
        return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n"
                f"Content-Type: {ctype}\r\n\r\n").encode() + payload + b"\r\n"
    body = part("metadata", meta_type, meta) + part("image", image_type, image) + extra
    return body + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"
