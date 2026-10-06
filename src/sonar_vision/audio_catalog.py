"""Local voice catalog tooling for #32. No provider, network or playback."""
import argparse
import hashlib
import io
from itertools import product
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
import wave
import zipfile

from .audio import NAMES, SIDES, MOTION

MAX_JSON = 2 * 1024 * 1024
MAX_AUDIO = 32 * 1024 * 1024  # tooling bound, not an ESP32 storage budget
MAX_PACKAGE = 64 * 1024 * 1024
ESSENTIALS = {"local.urgent", "local.visual_unavailable", "local.visual_restored"}
PHRASE_FIELDS = {"id", "kind", "event", "selector", "text", "directional"}
SELECTOR_FIELDS = {"class_name", "direction", "movement", "stair_direction"}
PROFILE_FIELDS = {"container", "encoding", "sample_rate_hz", "channels", "sample_width_bytes"}
AUDIO_FIELDS = {"path", "sha256", "size_bytes", "duration_ms", "frames", "origin", "rights", "review"}
ORIGIN_FIELDS = {"kind", "provider", "plan", "voice", "configuration",
                 "generation_version", "source_reference"}
RIGHTS_FIELDS = {"license", "distribution_reference", "voice_permission_reference", "attribution"}
REVIEW_FIELDS = {"status", "pronunciation_reference", "comprehension_reference"}
APPROVAL_FIELDS = {"interface_reference", "firmware_reference", "provider_reference"}
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?")
TOKEN = re.compile(r"[a-z][a-z0-9_.-]{0,127}")


class CatalogError(ValueError):
    """Fixed structural errors; never include private paths/configuration."""


def require(condition, code):
    if not condition:
        raise CatalogError(code)


def fields(value, names, code):
    require(isinstance(value, dict) and set(value) == names, code)


def reference(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256


def positive(value):
    return type(value) is int and 0 < value <= 2**53 - 1


def digest(data):
    return hashlib.sha256(data).hexdigest()


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_JSON + 1)
    require(len(data) <= MAX_JSON, "json_too_large")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(CatalogError("invalid_number")))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise CatalogError("invalid_json") from exc
    return value, data


def validate_phrases(source):
    fields(source, {"schema_version", "phrase_version", "locale", "approval_reference", "phrases"}, "phrase_fields")
    require(type(source["schema_version"]) is int and source["schema_version"] == 1, "phrase_schema")
    require(isinstance(source["phrase_version"], str) and VERSION.fullmatch(source["phrase_version"]), "phrase_version")
    require(source["locale"] == "pt-BR", "locale")
    require(source["approval_reference"] is None or reference(source["approval_reference"]), "phrase_approval")
    phrases = source["phrases"]
    require(isinstance(phrases, list) and 1 <= len(phrases) <= 512, "phrase_count")
    ids, texts, selectors, events = set(), set(), set(), set()
    for phrase in phrases:
        fields(phrase, PHRASE_FIELDS, "phrase_entry")
        ident, text = phrase["id"], phrase["text"]
        require(isinstance(ident, str) and TOKEN.fullmatch(ident), "invalid_id")
        require(ident not in ids, "duplicate_id")
        ids.add(ident)
        require(isinstance(text, str) and 1 <= len(text) <= 120 and text == text.strip()
                and unicodedata.normalize("NFC", text) == text
                and all(unicodedata.category(c) not in ("Cc", "Cs", "Cf") for c in text), "invalid_text")
        require(type(phrase["directional"]) is bool, "directional")
        require(phrase["kind"] in ("essential_local", "visual"), "phrase_kind")
        text_key = (phrase["kind"], text)
        require(text_key not in texts, "duplicate_text")
        texts.add(text_key)
        if phrase["kind"] == "essential_local":
            require(ident in ESSENTIALS and phrase["event"] == ident.split(".", 1)[1]
                    and phrase["selector"] is None and phrase["directional"] is False, "local_phrase")
            events.add(ident)
        else:
            require(ident.startswith("visual.") and phrase["event"] is None, "visual_phrase")
            selector = phrase["selector"]
            fields(selector, SELECTOR_FIELDS, "selector_fields")
            cls, direction, movement, stair = (selector[k] for k in (
                "class_name", "direction", "movement", "stair_direction"))
            require(isinstance(cls, str) and cls in NAMES
                    and direction in ("left", "center", "right", "unknown")
                    and movement in ("approaching", "receding", "crossing", "unknown"), "selector_vocabulary")
            require(stair in ("up", "down", "unknown") if cls == "stairs" else stair is None, "selector_stairs")
            require(phrase["directional"] == (direction != "unknown" or movement != "unknown"), "selector_direction")
            key = (cls, direction, movement, stair)
            require(key not in selectors, "duplicate_selector")
            selectors.add(key)
    require(events == ESSENTIALS, "missing_essential")
    return {phrase["id"]: phrase for phrase in phrases}


def validate_profile(profile):
    fields(profile, PROFILE_FIELDS, "profile_fields")
    require(profile["container"] == "wav" and profile["encoding"] == "pcm", "unsupported_format")
    require(positive(profile["sample_rate_hz"]) and profile["sample_rate_hz"] <= 192000
            and type(profile["channels"]) is int and profile["channels"] in (1, 2)
            and type(profile["sample_width_bytes"]) is int and profile["sample_width_bytes"] in (1, 2, 3, 4),
            "invalid_profile")


def asset_path(root, value):
    require(isinstance(value, str) and re.fullmatch(r"audio/[A-Za-z0-9_./-]+\.wav", value), "invalid_audio_path")
    relative = PurePosixPath(value)
    require(all(part not in (".", "..") for part in value.split("/")) and str(relative) == value, "invalid_audio_path")
    base = Path(root).resolve()
    target = (base / value).resolve()
    require(target.is_relative_to(base), "audio_outside_package")
    return target


def wav_metadata(data):
    require(len(data) <= MAX_AUDIO, "audio_too_large")
    try:
        with wave.open(io.BytesIO(data), "rb") as stream:
            require(stream.getcomptype() == "NONE" and stream.getnframes() > 0, "invalid_wav")
            frames, rate = stream.getnframes(), stream.getframerate()
            channels, width = stream.getnchannels(), stream.getsampwidth()
            require(rate > 0, "invalid_wav")
            pcm = stream.readframes(frames)
            require(len(pcm) == frames * channels * width, "truncated_wav")
            return {"frames": frames, "duration_ms": (frames * 1000 + rate - 1) // rate,
                    "size_bytes": len(data), "sha256": digest(data),
                    "profile": {"container": "wav", "encoding": "pcm", "sample_rate_hz": rate,
                                "channels": channels, "sample_width_bytes": width}}
    except (wave.Error, EOFError) as exc:
        raise CatalogError("invalid_wav") from exc


def read_audio(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_AUDIO + 1)
    require(len(data) <= MAX_AUDIO, "audio_too_large")
    return data


def validate_bundle(source, manifest, root, *, require_release=False):
    phrases = validate_phrases(source)
    fields(manifest, {"schema_version", "catalog_version", "status", "phrase_version", "phrases_sha256",
                      "approval", "profile", "entries"}, "manifest_fields")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1, "manifest_schema")
    require(isinstance(manifest["catalog_version"], str) and VERSION.fullmatch(manifest["catalog_version"]), "catalog_version")
    require(manifest["status"] in ("draft", "released"), "catalog_status")
    require(manifest["phrase_version"] == source["phrase_version"]
            and manifest["phrases_sha256"] == digest(serialized(source)), "phrase_source_mismatch")
    fields(manifest["approval"], APPROVAL_FIELDS, "approval_fields")
    for value in manifest["approval"].values():
        require(value is None or reference(value), "approval_reference")
    profile = manifest["profile"]
    if profile is not None:
        validate_profile(profile)
    entries = manifest["entries"]
    require(isinstance(entries, list) and len(entries) == len(phrases), "entry_count")
    ids, paths = set(), set()
    missing, synthetic, reviewed, rights_ready = [], [], 0, 0
    for entry in entries:
        fields(entry, {"id", "text", "text_sha256", "audio"}, "entry_fields")
        ident = entry["id"]
        require(isinstance(ident, str) and ident in phrases, "unknown_id")
        require(ident not in ids, "duplicate_id")
        ids.add(ident)
        require(entry["text"] == phrases[ident]["text"]
                and entry["text_sha256"] == digest(phrases[ident]["text"].encode("utf-8")), "text_mismatch")
        audio = entry["audio"]
        if audio is None:
            missing.append(ident)
            continue
        fields(audio, AUDIO_FIELDS, "audio_fields")
        require(profile is not None, "profile_missing")
        target = asset_path(root, audio["path"])
        require(target not in paths, "duplicate_audio_path")
        paths.add(target)
        require(target.is_file(), "audio_missing")
        actual = wav_metadata(read_audio(target))
        require(actual["sha256"] == audio["sha256"], "hash_mismatch")
        for name in ("size_bytes", "duration_ms", "frames"):
            require(positive(audio[name]) and audio[name] == actual[name], "audio_metadata_mismatch")
        require(actual["profile"] == profile, "audio_format_mismatch")
        origin, rights, review = audio["origin"], audio["rights"], audio["review"]
        fields(origin, ORIGIN_FIELDS, "origin_fields")
        require(origin["kind"] in ("tts", "recording", "synthetic_fixture"), "origin_kind")
        for name in ("provider", "plan", "voice", "generation_version", "source_reference"):
            require(reference(origin[name]), "origin_reference")
        config = origin["configuration"]
        require(isinstance(config, dict) and len(config) <= 16, "voice_configuration")
        for key, value in config.items():
            require(key in ("model", "speed", "pitch", "stability", "similarity", "style")
                    and type(value) in (str, int, float, bool) and len(str(value)) <= 128,
                    "voice_configuration")
        # JSON roundtrip rejects non-finite configuration and unsupported values.
        try:
            json.dumps(config, allow_nan=False)
        except ValueError as exc:
            raise CatalogError("voice_configuration") from exc
        fields(rights, RIGHTS_FIELDS, "rights_fields")
        for name in RIGHTS_FIELDS:
            require(rights[name] is None or reference(rights[name]), "rights_reference")
        if all(reference(rights[k]) for k in ("license", "distribution_reference", "voice_permission_reference")):
            rights_ready += 1
        fields(review, REVIEW_FIELDS, "review_fields")
        require(review["status"] in ("pending", "approved"), "review_status")
        for name in ("pronunciation_reference", "comprehension_reference"):
            require(review[name] is None or reference(review[name]), "review_reference")
        if review["status"] == "approved":
            require(all(reference(review[k]) for k in ("pronunciation_reference", "comprehension_reference")),
                    "review_reference")
            reviewed += 1
        if origin["kind"] == "synthetic_fixture":
            synthetic.append(ident)
    require(ids == set(phrases), "missing_id")
    ready = (reference(source["approval_reference"])
             and all(reference(v) for v in manifest["approval"].values())
             and profile is not None and not missing and not synthetic
             and reviewed == len(entries) and rights_ready == len(entries))
    if manifest["status"] == "released" or require_release:
        require(manifest["status"] == "released" and ready, "release_not_ready")
        require("-" not in manifest["catalog_version"] and "-" not in source["phrase_version"], "release_version")
    return {"metadata_valid": True, "status": manifest["status"], "phrases": len(phrases),
            "essential_local": len(ESSENTIALS), "missing_audio": len(missing),
            "synthetic_audio": len(synthetic), "auditory_reviewed": reviewed,
            "distribution_ready": bool(ready and manifest["status"] == "released"),
            "limitations": ["References are declarations, not proof of permission or review",
                            "Hashes bind intended text and bytes, not spoken content or authenticity",
                            "No firmware, network, playback or physical safety validation"]}


def load_bundle(root, *, require_release=False):
    root = Path(root)
    source, raw = read_json(root / "phrases.json")
    manifest, _ = read_json(root / "manifest.json")
    return validate_bundle(source, manifest, root, require_release=require_release)


def lookup_text(source, text, *, kind="visual"):
    phrases = validate_phrases(source)
    require(kind in ("visual", "essential_local"), "phrase_kind")
    return next((ident for ident, p in phrases.items() if p["kind"] == kind and p["text"] == text), None)


def proposed_source():
    phrases = [{
        "id": "local." + event, "kind": "essential_local", "event": event,
        "selector": None, "text": text, "directional": False,
    } for event, text in (
        ("urgent", "Atenção"),
        ("visual_unavailable", "Assistência visual indisponível"),
        ("visual_restored", "Assistência visual restabelecida"))]
    for cls, direction, movement in product(NAMES, ("unknown", "left", "center", "right"),
                                             ("unknown", "approaching", "receding", "crossing")):
        for stair in (("unknown", "up", "down") if cls == "stairs" else (None,)):
            parts = [NAMES[cls]]
            if stair in ("up", "down"):
                parts.append("de subida" if stair == "up" else "de descida")
            if direction in SIDES:
                parts.append(SIDES[direction])
            if movement in MOTION:
                parts.append(MOTION[movement])
            ident = ".".join(("visual", cls, direction, movement, stair or "none"))
            phrases.append({"id": ident, "kind": "visual", "event": None,
                            "selector": dict(class_name=cls, direction=direction, movement=movement,
                                             stair_direction=stair),
                            "text": " ".join(parts), "directional": direction != "unknown" or movement != "unknown"})
    return {"schema_version": 1, "phrase_version": "0.1.0-draft.1", "locale": "pt-BR",
            "approval_reference": None, "phrases": phrases}


def proposed_manifest(source):
    return {"schema_version": 1, "catalog_version": "0.1.0-draft.1", "status": "draft",
            "phrase_version": source["phrase_version"], "phrases_sha256": digest(serialized(source)),
            "approval": {k: None for k in sorted(APPROVAL_FIELDS)}, "profile": None,
            "entries": [{"id": p["id"], "text": p["text"],
                         "text_sha256": digest(p["text"].encode("utf-8")), "audio": None}
                        for p in source["phrases"]]}


def write_proposal(output, *, fixture=False):
    """New directory only; never overwrite a reviewed catalog."""
    output = Path(output)
    require(not output.exists(), "output_exists")
    source = proposed_source()
    raw = serialized(source)
    manifest = proposed_manifest(source)
    output.mkdir(parents=True)
    if fixture:
        # Silence is a test artifact, never voice or a firmware format decision.
        manifest["profile"] = {"container": "wav", "encoding": "pcm", "sample_rate_hz": 16000,
                               "channels": 1, "sample_width_bytes": 2}
        (output / "audio").mkdir()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b"\x00" * 3200)
        data = buffer.getvalue()
        meta = wav_metadata(data)
        for entry in manifest["entries"]:
            path = "audio/" + entry["id"] + ".wav"
            (output / path).write_bytes(data)
            entry["audio"] = {k: meta[k] for k in ("sha256", "size_bytes", "duration_ms", "frames")}
            entry["audio"].update({
                "path": path,
                "origin": {"kind": "synthetic_fixture", "provider": "stdlib-wave", "plan": "not-applicable",
                           "voice": "silence-not-speech", "configuration": {}, "generation_version": "1",
                           "source_reference": "original-in-memory-silence"},
                "rights": {"license": "AGPL-3.0-only", "distribution_reference": None,
                           "voice_permission_reference": None, "attribution": None},
                "review": {"status": "pending", "pronunciation_reference": None, "comprehension_reference": None},
            })
    (output / "phrases.json").write_bytes(raw)
    (output / "manifest.json").write_bytes(serialized(manifest))
    return load_bundle(output)


def package_bundle(root, output, *, fixture=False, previous=None):
    """Offline archive; release requires declared approvals and complete files."""
    root, output = Path(root), Path(output)
    source, source_raw = read_json(root / "phrases.json")
    manifest, manifest_raw = read_json(root / "manifest.json")
    validate_bundle(source, manifest, root, require_release=not fixture)
    if fixture:
        require(manifest["status"] == "draft" and all(e["audio"] is not None
                and e["audio"]["origin"]["kind"] == "synthetic_fixture" for e in manifest["entries"]),
                "fixture_only")
    if previous is not None:
        load_bundle(previous)
        old, _ = read_json(Path(previous) / "manifest.json")
        require(old["catalog_version"] != manifest["catalog_version"]
                or old == manifest, "version_reused")
        old_source, _ = read_json(Path(previous) / "phrases.json")
        require(old_source["phrase_version"] != source["phrase_version"]
                or old_source == source, "phrase_version_reused")
    require(not output.exists(), "output_exists")
    files = {"phrases.json": source_raw, "manifest.json": manifest_raw,
             "PACKAGE_KIND.txt": b"TEST FIXTURE - SILENCE - NOT FOR DEVICE\n" if fixture else b"RELEASE\n"}
    total = sum(len(data) for data in files.values())
    for entry in manifest["entries"]:
        audio = entry["audio"]
        data = read_audio(asset_path(root, audio["path"]))
        total += len(data)
        require(total <= MAX_PACKAGE, "package_too_large")
        require(digest(data) == audio["sha256"], "hash_mismatch")
        files[audio["path"]] = data
    sums = "".join(digest(data) + "  " + name + "\n" for name, data in sorted(files.items())).encode()
    # Exclusive creation also protects against an output created since the precheck.
    with output.open("xb") as stream:
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
            info = zipfile.ZipInfo("SHA256SUMS", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, sums)
    with output.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"package_created": True, "kind": "fixture" if fixture else "release",
            "sha256": archive_hash, "files": len(files) + 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("draft", "fixture"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("directory", type=Path)
    validate.add_argument("--require-release", action="store_true")
    package = commands.add_parser("pack")
    package.add_argument("directory", type=Path)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--fixture", action="store_true")
    package.add_argument("--previous", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in ("draft", "fixture"):
            result = write_proposal(args.output, fixture=args.command == "fixture")
        elif args.command == "validate":
            result = load_bundle(args.directory, require_release=args.require_release)
        else:
            result = package_bundle(args.directory, args.output, fixture=args.fixture, previous=args.previous)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        # Structural failure only; no arbitrary paths, response text or credentials.
        parser.exit(2, "Catalog invalid, incomplete, incompatible or output unavailable; review locally.\n")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
