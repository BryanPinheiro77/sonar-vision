"""Reference model of how the glasses obtain and replace the voice catalog (#26).

Executable specification, NOT firmware (#18 implements it in C++). Transport is
injected so the same rules run against fakes or the real HTTPS API:

- never download or install while a local urgency is active (checked before every
  request and again after the last transfer, right before installing);
- verify each file's size and SHA-256 as declared in the manifest before use;
- install only through `install()` (#25): atomic, essentials required;
- any failure keeps the catalog already installed, so local warnings keep working.
"""

from hashlib import sha256
import json
from typing import Callable

from .catalog import InstalledCatalog, install


class TransferError(Exception):
    """Network/HTTP failure; `reason` is a stable code (e.g. catalog_unavailable)."""

    def __init__(self, reason: str = "transfer"):
        super().__init__(reason)
        self.reason = reason


# fetch_manifest(etag_or_None) -> None when unchanged (304), else (etag, raw bytes)
FetchManifest = Callable[[str | None], tuple[str, bytes] | None]
FetchFile = Callable[[str], bytes]


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON key")
    return dict(pairs)


def update_catalog(current: InstalledCatalog | None, current_etag: str | None, *,
                   fetch_manifest: FetchManifest, fetch_file: FetchFile, device_profile: dict,
                   urgent: Callable[[], bool], attempts_per_file: int = 2
                   ) -> tuple[InstalledCatalog | None, str | None, str]:
    """Return (catalog in use, its etag, status). The previous pair is kept on failure."""
    keep = (current, current_etag)
    if urgent():
        return (*keep, "deferred:urgent")
    try:
        response = fetch_manifest(current_etag)
    except TransferError as error:
        return (*keep, f"failed:{error.reason}")
    if response is None:
        return (*keep, "up_to_date")
    etag, raw = response
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
        entries = [e for e in manifest["entries"] if e.get("audio") is not None]
        wanted = {e["audio"]["path"]: e["audio"] for e in entries}
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, AttributeError):
        return (*keep, "rejected:manifest_invalid")

    files = {}
    for path, audio in wanted.items():
        cause = "transfer"
        for _ in range(attempts_per_file):
            if urgent():
                return (*keep, "deferred:urgent")
            try:
                data = fetch_file(path)
            except TransferError as error:
                cause = error.reason
                continue
            if len(data) == audio.get("size_bytes") and sha256(data).hexdigest() == audio.get("sha256"):
                files[path] = data
                break
            cause = "integrity"  # corrupted or truncated in transit: fetch again
        if path not in files:
            return (*keep, f"failed:{cause}")
    # Urgency may have started during the last transfer: never install in that window.
    if urgent():
        return (*keep, "deferred:urgent")
    catalog, status = install(current, manifest, files, device_profile)
    return (catalog, etag if status == "installed" else current_etag, status)
