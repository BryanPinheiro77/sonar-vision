"""Per-device bearer credentials. The server stores only SHA-256 hashes.

Token file format, one device per line (comments with #):
    <device_id> <sha256 hex of the token>
Revocation: remove the line and restart the API.
"""

from hashlib import sha256
import re
import secrets

from sonar_vision.core import identifier

from .errors import ApiError

_HEX = re.compile(r"[0-9a-f]{64}")


def token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


class TokenStore:
    def __init__(self, entries: dict[str, str]):
        self._by_hash = {}
        for device_id, digest in entries.items():
            identifier(device_id)
            if not _HEX.fullmatch(digest) or digest in self._by_hash:
                raise ValueError("token hashes must be unique lowercase SHA-256 hex")
            self._by_hash[digest] = device_id

    @classmethod
    def from_file(cls, path) -> "TokenStore":
        entries = {}
        with open(path, encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                fields = line.split()
                if len(fields) != 2 or fields[0] in entries:
                    raise ValueError(f"invalid or duplicate token entry at line {number}")
                entries[fields[0]] = fields[1]
        if not entries:
            raise ValueError("token file has no devices")
        return cls(entries)

    def authenticate(self, header: str | None) -> str:
        """Return the device_id bound to the credential; the body never chooses it."""
        scheme, _, token = (header or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise ApiError(401, "missing_credential")
        # Lookup by the hash of a high-entropy secret: timing reveals nothing usable
        # about the token, and the plaintext is never stored or compared.
        device_id = self._by_hash.get(token_hash(token.strip()))
        if device_id is None:
            raise ApiError(401, "unknown_credential")
        return device_id
