"""Device-side acceptance of a voice catalog (#25), using the #32 manifest format.

The device only needs a subset of the bench manifest: version fields, profile,
and per entry id/text and audio path/hash/size. Origin, rights and review are
checked on the bench (#32), not on the glasses.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping
import unicodedata

SUPPORTED_SCHEMA_VERSIONS = frozenset({1})
ESSENTIAL_IDS = ("local.urgent", "local.visual_unavailable", "local.visual_restored")
# Candidate for review with firmware (#18); NOT an approved operational format.
CANDIDATE_PROFILE = {"container": "wav", "encoding": "pcm", "sample_rate_hz": 16000,
                     "channels": 1, "sample_width_bytes": 2}


class CatalogRejected(ValueError):
    """The candidate catalog cannot be installed; `reason` is a stable code."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Entry:
    id: str
    text: str
    path: str | None  # None: phrase known, audio not provided (visual only)


@dataclass(frozen=True)
class InstalledCatalog:
    catalog_version: str
    phrase_version: str
    entries: Mapping[str, Entry]
    by_text: Mapping[str, Entry]

    def resolve_text(self, text: str) -> Entry | None:
        """Exact match on the NFC text; no fuzzy matching or synthesis fallback."""
        return self.by_text.get(text)

    def playable(self, phrase_id: str) -> bool:
        entry = self.entries.get(phrase_id)
        return entry is not None and entry.path is not None


def _require(condition, reason):
    if not condition:
        raise CatalogRejected(reason)


def check_catalog(manifest: dict, files: Mapping[str, bytes], device_profile: dict, *,
                  allow_draft: bool = False) -> InstalledCatalog:
    """Validate a candidate catalog against what the device can play."""
    _require(isinstance(manifest, dict), "manifest_not_object")
    _require(manifest.get("schema_version") in SUPPORTED_SCHEMA_VERSIONS, "schema_unsupported")
    for name in ("catalog_version", "phrase_version"):
        _require(isinstance(manifest.get(name), str) and manifest[name], "version_missing")
    _require(manifest.get("status") == "released" or (allow_draft and manifest.get("status") == "draft"),
             "catalog_not_released")
    _require(manifest.get("profile") == device_profile, "profile_incompatible")
    entries, by_text = {}, {}
    _require(isinstance(manifest.get("entries"), list), "entries_missing")
    for item in manifest["entries"]:
        _require(isinstance(item, dict), "entry_invalid")
        phrase_id, text = item.get("id"), item.get("text")
        _require(isinstance(phrase_id, str) and phrase_id, "entry_invalid")
        _require(isinstance(text, str) and text and len(text) <= 120
                 and unicodedata.is_normalized("NFC", text), "entry_text_invalid")
        _require(item.get("text_sha256") == sha256(text.encode("utf-8")).hexdigest(),
                 "text_hash_mismatch")
        _require(phrase_id not in entries, "duplicate_id")
        _require(text not in by_text, "duplicate_text")
        audio, path = item.get("audio"), None
        if audio is not None:
            _require(isinstance(audio, dict), "audio_invalid")
            path = audio.get("path")
            data = files.get(path) if isinstance(path, str) else None
            _require(data is not None, "audio_file_missing")
            _require(audio.get("size_bytes") == len(data), "audio_size_mismatch")
            _require(audio.get("sha256") == sha256(data).hexdigest(), "audio_hash_mismatch")
        entries[phrase_id] = by_text[text] = Entry(phrase_id, text, path)
    for phrase_id in ESSENTIAL_IDS:
        _require(phrase_id in entries, "essential_missing")
        _require(entries[phrase_id].path is not None, "essential_audio_missing")
    return InstalledCatalog(manifest["catalog_version"], manifest["phrase_version"],
                            entries, by_text)


def install(current: InstalledCatalog | None, manifest: dict, files: Mapping[str, bytes],
            device_profile: dict, **options) -> tuple[InstalledCatalog | None, str]:
    """Atomic replacement: a rejected candidate never removes the working catalog."""
    try:
        return check_catalog(manifest, files, device_profile, **options), "installed"
    except CatalogRejected as error:
        return current, f"rejected:{error.reason}"
