"""Publication of the voice catalog for authenticated devices (#26).

The package is a directory with `manifest.json` (format of #32) and the WAV
files it references under `audio/`. It is validated once at startup and served
from memory, so a file changed on disk later is never sent unverified.
No database: updating means pointing to a new directory and restarting.
"""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import re
import wave

from sonar_vision_local_audio.catalog import CatalogRejected, check_catalog

MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_PACKAGE_BYTES = 64 * 1024 * 1024  # tooling bound from #32, not an ESP32 budget
PROFILE_FIELDS = {"container", "encoding", "sample_rate_hz", "channels", "sample_width_bytes"}
# Flat, lowercase names only: no traversal, absolute, drive, ADS or hidden paths.
AUDIO_PATH = re.compile(r"audio/[a-z0-9][a-z0-9._-]{0,127}\.wav")
ALLOWED_TOP_LEVEL = {"manifest.json", "phrases.json", "audio", "SHA256SUMS", "PACKAGE_KIND.txt"}


class PackageRejected(ValueError):
    """The directory cannot be published; `reason` is a stable code for logs."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _require(condition, reason):
    if not condition:
        raise PackageRejected(reason)


def _reference(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON key")
    return dict(pairs)


def _reject_constant(name):
    raise ValueError("NaN/Infinity are not JSON")


@dataclass(frozen=True)
class PublishedCatalog:
    manifest_bytes: bytes
    manifest_sha256: str
    catalog_version: str
    files: dict[str, bytes]  # path -> verified bytes, only paths the manifest references
    hashes: dict[str, str]  # path -> SHA-256 hex, as declared and verified

    @property
    def etag(self) -> str:
        return f'"{self.manifest_sha256}"'


def _wav_matches(data: bytes, audio: dict, profile: dict) -> None:
    try:
        with wave.open(BytesIO(data)) as reader:
            channels, width = reader.getnchannels(), reader.getsampwidth()
            rate, frames = reader.getframerate(), reader.getnframes()
            compression = reader.getcomptype()
    except (wave.Error, EOFError):
        raise PackageRejected("audio_not_pcm_wav") from None
    _require(compression == "NONE" and profile["container"] == "wav"
             and profile["encoding"] == "pcm", "audio_format_mismatch")
    _require((channels, width, rate) == (profile["channels"], profile["sample_width_bytes"],
                                          profile["sample_rate_hz"]), "audio_format_mismatch")
    _require(audio.get("frames") == frames and frames > 0
             and audio.get("duration_ms") == math.ceil(frames * 1000 / rate), "audio_metadata_mismatch")


def _rights_ready(audio: dict) -> None:
    """Origin/license are declared by humans (#32); we only refuse to publish without them.

    Nothing here assumes a TTS provider's output is AGPL or freely redistributable.
    """
    origin, rights, review = audio.get("origin"), audio.get("rights"), audio.get("review")
    _require(isinstance(origin, dict) and origin.get("kind") in ("tts", "recording"), "origin_not_distributable")
    _require(isinstance(rights, dict) and all(_reference(rights.get(name)) for name in
             ("license", "distribution_reference", "voice_permission_reference")), "rights_missing")
    _require(isinstance(review, dict) and review.get("status") == "approved"
             and _reference(review.get("pronunciation_reference"))
             and _reference(review.get("comprehension_reference")), "review_not_approved")


def load_package(root: Path) -> PublishedCatalog:
    root = Path(root)
    _require(root.is_dir(), "package_missing")
    for item in root.iterdir():
        _require(item.name in ALLOWED_TOP_LEVEL and not item.is_symlink(), "unexpected_file")
    manifest_path = root / "manifest.json"
    _require(manifest_path.is_file(), "manifest_missing")
    raw = manifest_path.read_bytes()
    _require(len(raw) <= MAX_MANIFEST_BYTES, "manifest_too_large")
    try:
        manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates,
                              parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError):
        raise PackageRejected("manifest_not_json") from None
    _require(isinstance(manifest, dict), "manifest_not_object")
    profile = manifest.get("profile")
    _require(isinstance(profile, dict) and set(profile) == PROFILE_FIELDS, "profile_missing")
    approval = manifest.get("approval")
    _require(isinstance(approval, dict) and all(_reference(approval.get(name)) for name in
             ("interface_reference", "firmware_reference", "provider_reference")), "approval_missing")

    referenced, total = {}, len(raw)
    for entry in manifest.get("entries") or []:
        audio = entry.get("audio") if isinstance(entry, dict) else None
        if audio is None:
            continue
        _require(isinstance(audio, dict), "audio_invalid")
        path = audio.get("path")
        _require(isinstance(path, str) and AUDIO_PATH.fullmatch(path), "audio_path_invalid")
        _require(path not in referenced, "audio_path_duplicate")
        target = root / path
        _require(target.is_file() and not target.is_symlink()
                 and target.resolve().parent == (root / "audio").resolve(), "audio_file_missing")
        data = target.read_bytes()
        total += len(data)
        _require(total <= MAX_PACKAGE_BYTES, "package_too_large")
        _wav_matches(data, audio, profile)
        _rights_ready(audio)
        referenced[path] = data
    audio_dir = root / "audio"
    if audio_dir.exists():
        on_disk = {f"audio/{item.name}" for item in audio_dir.iterdir()}
        # Files nobody references are not served and signal a stale/mixed package.
        _require(on_disk == set(referenced), "unreferenced_file")
    try:
        # Same acceptance rules the glasses apply (#25): hashes, sizes, essentials.
        check_catalog(manifest, referenced, profile)
    except CatalogRejected as error:
        raise PackageRejected(error.reason) from None
    hashes = {path: sha256(data).hexdigest() for path, data in referenced.items()}
    return PublishedCatalog(raw, sha256(raw).hexdigest(), manifest["catalog_version"],
                            referenced, hashes)
