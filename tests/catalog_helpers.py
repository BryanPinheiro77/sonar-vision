"""Synthetic voice packages for #26 tests: generated silence, never real voices."""

from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path
import wave

from sonar_vision_local_audio.catalog import CANDIDATE_PROFILE

PHRASES = [("local.urgent", "Atenção"),
           ("local.visual_unavailable", "Assistência visual indisponível"),
           ("local.visual_restored", "Assistência visual restabelecida"),
           ("visual.person.unknown.unknown.none", "Pessoa")]


def silence(ms=100, rate=16000, channels=1, width=2) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        writer.writeframes(b"\x00" * (rate * ms // 1000) * channels * width)
    return buffer.getvalue()


def audio_entry(path: str, data: bytes, rate=16000) -> dict:
    with wave.open(BytesIO(data)) as reader:
        frames = reader.getnframes()
    return {"path": path, "sha256": sha256(data).hexdigest(), "size_bytes": len(data),
            "frames": frames, "duration_ms": math.ceil(frames * 1000 / rate),
            # Test-only references: these files are generated silence in a temp dir.
            "origin": {"kind": "recording", "provider": "test-fixture", "plan": "test-fixture",
                       "voice": "silence-not-speech", "configuration": {},
                       "generation_version": "test", "source_reference": "test:generated"},
            "rights": {"license": "test:license", "distribution_reference": "test:rights",
                       "voice_permission_reference": "test:permission", "attribution": None},
            "review": {"status": "approved", "pronunciation_reference": "test:review",
                       "comprehension_reference": "test:review"}}


def make_package(root: Path, version="1.0.0") -> tuple[dict, dict[str, bytes]]:
    """Write manifest.json + audio/*.wav under root; return (manifest, files)."""
    (root / "audio").mkdir(parents=True)
    entries, files = [], {}
    for phrase_id, text in PHRASES:
        path = f"audio/{phrase_id}.wav"
        data = silence()
        files[path] = data
        (root / path).write_bytes(data)
        entries.append({"id": phrase_id, "text": text,
                        "text_sha256": sha256(text.encode("utf-8")).hexdigest(),
                        "audio": audio_entry(path, data)})
    manifest = {"schema_version": 1, "catalog_version": version, "status": "released",
                "phrase_version": version, "phrases_sha256": "0" * 64,
                "approval": {"interface_reference": "test:25", "firmware_reference": "test:18",
                             "provider_reference": "test:provider"},
                "profile": dict(CANDIDATE_PROFILE), "entries": entries}
    write_manifest(root, manifest)
    return manifest, files


def write_manifest(root: Path, manifest: dict) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
