"""Synthetic catalog tests; no real voices, permissions or firmware evidence."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import io
from itertools import product
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave
import zipfile

from sonar_vision.audio import AudioConfig, AudioPolicy, NAMES
from sonar_vision.audio_catalog import (
    CatalogError, ESSENTIALS, MAX_AUDIO, MAX_JSON, asset_path, digest,
    load_bundle, lookup_text, main, package_bundle, proposed_manifest,
    proposed_source, read_json, serialized, validate_bundle, validate_phrases,
    validate_profile, wav_metadata, write_proposal,
)

REPO = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "catalog"
        small_source = proposed_source()
        small_source["phrases"] = small_source["phrases"][:4]
        with patch("sonar_vision.audio_catalog.proposed_source", return_value=small_source):
            write_proposal(self.root, fixture=True)
        self.source, self.raw = read_json(self.root / "phrases.json")
        self.manifest, _ = read_json(self.root / "manifest.json")
        # Small catalog containing every essential plus one visual phrase.
        self.source["phrases"] = self.source["phrases"][:4]
        self.raw = serialized(self.source)
        self.manifest["entries"] = self.manifest["entries"][:4]
        self.manifest["phrases_sha256"] = digest(self.raw)
        self.save()

    def save(self):
        (self.root / "phrases.json").write_bytes(self.raw)
        (self.root / "manifest.json").write_bytes(serialized(self.manifest))

    def validate(self, release=False):
        return validate_bundle(self.source, self.manifest, self.root,
                               require_release=release)

    def declare_mock_release(self):
        # Test declarations only. Silence is NEVER approved as production content.
        self.source["approval_reference"] = "mock-only-text-review"
        self.source["phrase_version"] = "1.0.0"
        self.raw = serialized(self.source)
        self.manifest.update(status="released", catalog_version="1.0.0",
                             phrase_version="1.0.0", phrases_sha256=digest(self.raw))
        self.manifest["approval"] = {k: "mock-only-review" for k in self.manifest["approval"]}
        for entry in self.manifest["entries"]:
            audio = entry["audio"]
            audio["origin"].update(kind="recording", provider="mock-only", plan="not-applicable",
                                   voice="mock-only", source_reference="mock-only-origin")
            audio["rights"].update(license="mock-only-license", distribution_reference="mock-only-rights",
                                   voice_permission_reference="mock-only-permission")
            audio["review"].update(status="approved", pronunciation_reference="mock-only-pronunciation",
                                   comprehension_reference="mock-only-comprehension")
        self.save()

    def test_checked_in_proposal_has_no_audio_or_approval(self):
        result = load_bundle(REPO / "docs" / "catalog")
        self.assertEqual(result["phrases"], 179)
        self.assertEqual(result["missing_audio"], 179)
        self.assertFalse(result["distribution_ready"])
        self.assertEqual(result["status"], "draft")

    def test_all_policy_outputs_map_exactly_and_unknown_does_not_gain_a_voice(self):
        source = proposed_source()
        config = AudioConfig(0.5, 2000, 10000, 30000, 32, 32, tuple(NAMES))
        ids = set()
        for cls, direction, movement in product(
                NAMES, ("unknown", "left", "center", "right"),
                ("unknown", "stable", "approaching", "receding", "crossing")):
            for stair in (("unknown", "up", "down") if cls == "stairs" else (None,)):
                obs = {"version": "0.1", "type": "visual_observation", "session_id": "s",
                       "message_id": "obs", "frame_id": "1", "captured_at_ms": 0,
                       "valid_for_ms": 1000, "tracker_epoch": "epoch", "objects": [{
                           "track_id": "1", "class_name": cls, "confidence": 0.8,
                           "direction": direction, "movement": movement, "stair_direction": stair}]}
                audio = AudioPolicy("s", config).select(obs, capture_age_lower_bound_ms=0)
                ident = lookup_text(source, audio["text"])
                self.assertIsNotNone(ident)
                phrase = next(p for p in source["phrases"] if p["id"] == ident)
                self.assertEqual(phrase["directional"], audio["directional"])
                ids.add(ident)
        self.assertEqual(len(ids), 176)
        self.assertIsNone(lookup_text(source, "unknown"))
        self.assertIsNone(lookup_text(source, "Atenção"))
        self.assertEqual(lookup_text(source, "Atenção", kind="essential_local"), "local.urgent")
        self.assertFalse(any("travess" in p["text"].lower() or "atraves" in p["text"].lower()
                             for p in source["phrases"]))

    def test_fixture_metadata_and_release_are_distinct(self):
        result = self.validate()
        self.assertEqual(result["synthetic_audio"], 4)
        self.assertEqual(result["missing_audio"], 0)
        self.assertFalse(result["distribution_ready"])
        self.assertEqual(self.manifest["entries"][0]["audio"]["duration_ms"], 100)
        with self.assertRaisesRegex(CatalogError, "release_not_ready"):
            self.validate(release=True)
        self.declare_mock_release()
        self.assertTrue(self.validate(release=True)["distribution_ready"])
        self.manifest["entries"][0]["audio"]["origin"]["kind"] = "synthetic_fixture"
        with self.assertRaisesRegex(CatalogError, "release_not_ready"):
            self.validate()

    def test_each_release_approval_is_mandatory(self):
        self.declare_mock_release()
        for key in self.manifest["approval"]:
            good = self.manifest["approval"][key]
            self.manifest["approval"][key] = None
            with self.assertRaisesRegex(CatalogError, "release_not_ready"):
                self.validate()
            self.manifest["approval"][key] = good
        self.source["approval_reference"] = None
        self.raw = serialized(self.source)
        self.manifest["phrases_sha256"] = digest(self.raw)
        with self.assertRaisesRegex(CatalogError, "release_not_ready"):
            self.validate()

    def test_missing_audio_and_duplicate_ids_paths_are_rejected(self):
        audio = self.manifest["entries"][0]["audio"]
        original_path = audio["path"]
        audio["path"] = "audio/missing.wav"
        with self.assertRaisesRegex(CatalogError, "audio_missing"):
            self.validate()
        audio["path"] = original_path
        self.manifest["entries"][1]["audio"]["path"] = original_path
        with self.assertRaisesRegex(CatalogError, "duplicate_audio_path"):
            self.validate()
        self.manifest["entries"][1]["audio"]["path"] = "audio/local.visual_unavailable.wav"
        self.manifest["entries"][1]["id"] = self.manifest["entries"][0]["id"]
        with self.assertRaisesRegex(CatalogError, "duplicate_id"):
            self.validate()

    def test_text_manifest_and_source_hash_divergence_rejected(self):
        entry = self.manifest["entries"][0]
        entry["text"] = "Outra frase"
        with self.assertRaisesRegex(CatalogError, "text_mismatch"):
            self.validate()
        entry["text"] = self.source["phrases"][0]["text"]
        entry["text_sha256"] = "0" * 64
        with self.assertRaisesRegex(CatalogError, "text_mismatch"):
            self.validate()
        self.manifest["phrases_sha256"] = "0" * 64
        with self.assertRaisesRegex(CatalogError, "phrase_source_mismatch"):
            self.validate()

    def test_hash_content_duration_size_and_audio_format_rejected(self):
        audio = self.manifest["entries"][0]["audio"]
        baseline = deepcopy(audio)
        for key, bad, reason in (
                ("sha256", "0" * 64, "hash_mismatch"),
                ("size_bytes", audio["size_bytes"] + 1, "audio_metadata_mismatch"),
                ("duration_ms", audio["duration_ms"] + 1, "audio_metadata_mismatch"),
                ("frames", True, "audio_metadata_mismatch")):
            with self.subTest(key=key):
                audio[key] = bad
                with self.assertRaisesRegex(CatalogError, reason):
                    self.validate()
                audio.update(deepcopy(baseline))
        self.manifest["profile"]["sample_rate_hz"] = 8000
        with self.assertRaisesRegex(CatalogError, "audio_format_mismatch"):
            self.validate()
        self.manifest["profile"]["sample_rate_hz"] = 16000
        path = self.root / audio["path"]
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(CatalogError, "hash_mismatch"):
            self.validate()

    def test_invalid_truncated_and_oversized_wav(self):
        data = (self.root / self.manifest["entries"][0]["audio"]["path"]).read_bytes()
        for bad in (b"not-wave", data[:20], data[:-2]):
            with self.assertRaises(CatalogError):
                wav_metadata(bad)
        with patch("sonar_vision.audio_catalog.MAX_AUDIO", 20):
            with self.assertRaisesRegex(CatalogError, "audio_too_large"):
                wav_metadata(data)

    def test_path_traversal_absolute_windows_paths_and_symlink_rejected(self):
        for path in ("../outside.wav", "audio/../outside.wav", "/audio/a.wav",
                     "audio//a.wav", "audio/./a.wav", "C:/private.wav",
                     "audio\\a.wav", "audio/a.mp3", "audio/a.wav:secret"):
            with self.subTest(path=path), self.assertRaises(CatalogError):
                asset_path(self.root, path)
        external = Path(self.temp.name) / "external.wav"
        external.write_bytes(b"private")
        link = self.root / "audio" / "link.wav"
        try:
            link.symlink_to(external)
        except OSError:
            # Windows without symlink privileges: exercise equivalent resolved escape.
            with patch("sonar_vision.audio_catalog.Path.resolve", side_effect=[self.root, external]):
                with self.assertRaisesRegex(CatalogError, "audio_outside_package"):
                    asset_path(self.root, "audio/link.wav")
        else:
            with self.assertRaisesRegex(CatalogError, "audio_outside_package"):
                asset_path(self.root, "audio/link.wav")

    def test_invalid_phrase_limits_types_essentials_and_selectors(self):
        original = deepcopy(self.source)
        for value in ("", " " * 2, "é" * 121, "Pessoa\n", "Pesso\x00a", "e\u0301", []):
            source = deepcopy(original)
            source["phrases"][0]["text"] = value
            with self.subTest(value=value), self.assertRaises(CatalogError):
                validate_phrases(source)
        source = deepcopy(original)
        source["phrases"][0]["text"] = "é" * 120
        self.assertIn("local.urgent", validate_phrases(source))
        for mutate in (
                lambda s: s["phrases"].pop(0),
                lambda s: s["phrases"].append(deepcopy(s["phrases"][0])),
                lambda s: s["phrases"][0].update(directional=True),
                lambda s: s["phrases"][-1]["selector"].update(class_name="unknown"),
                lambda s: s["phrases"][-1].update(directional=True),
                lambda s: s.update(schema_version=True),
                lambda s: s.update(phrase_version="bad")):
            source = deepcopy(original)
            mutate(source)
            with self.assertRaises(CatalogError):
                validate_phrases(source)

    def test_config_and_review_permissions_boundaries(self):
        audio = self.manifest["entries"][0]["audio"]
        for config in ({"token": "secret"}, {"model": {"nested": "secret"}}, {"speed": float("nan")}):
            audio["origin"]["configuration"] = config
            with self.assertRaises(CatalogError):
                self.validate()
        audio["origin"]["configuration"] = {}
        audio["review"]["status"] = "approved"
        with self.assertRaisesRegex(CatalogError, "review_reference"):
            self.validate()
        audio["review"]["status"] = "pending"
        self.declare_mock_release()
        audio["rights"]["distribution_reference"] = None
        with self.assertRaisesRegex(CatalogError, "release_not_ready"):
            self.validate()

    def test_profile_has_no_implicit_production_format(self):
        manifest = proposed_manifest(self.source)
        result = validate_bundle(self.source, manifest, self.root)
        self.assertEqual(result["missing_audio"], 4)
        self.assertIsNone(manifest["profile"])
        for profile in ({"container": "mp3"}, {**self.manifest["profile"], "channels": True},
                        {**self.manifest["profile"], "sample_rate_hz": 0}):
            with self.assertRaises(CatalogError):
                validate_profile(profile)

    def test_offline_fixture_zip_is_deterministic_and_integrity_is_verifiable(self):
        first = Path(self.temp.name) / "first.zip"
        second = Path(self.temp.name) / "second.zip"
        result = package_bundle(self.root, first, fixture=True)
        package_bundle(self.root, second, fixture=True)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(result["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())
        with zipfile.ZipFile(first) as package:
            self.assertEqual(len(package.namelist()), len(set(package.namelist())))
            self.assertIn(b"NOT FOR DEVICE", package.read("PACKAGE_KIND.txt"))
            for ident in ESSENTIALS:
                self.assertIn("audio/" + ident + ".wav", package.namelist())
            for line in package.read("SHA256SUMS").decode().splitlines():
                expected, name = line.split("  ", 1)
                self.assertEqual(digest(package.read(name)), expected)
        with self.assertRaisesRegex(CatalogError, "output_exists"):
            package_bundle(self.root, first, fixture=True)

    def test_release_package_missing_file_never_creates_archive(self):
        self.declare_mock_release()
        path = Path(self.temp.name) / "release.zip"
        result = package_bundle(self.root, path)
        self.assertEqual(result["kind"], "release")
        with zipfile.ZipFile(path) as package:
            self.assertEqual(package.read("PACKAGE_KIND.txt"), b"RELEASE\n")
        (self.root / self.manifest["entries"][0]["audio"]["path"]).unlink()
        output = Path(self.temp.name) / "missing.zip"
        with self.assertRaisesRegex(CatalogError, "audio_missing"):
            package_bundle(self.root, output)
        self.assertFalse(output.exists())

    def test_version_reuse_and_aggregate_package_limit(self):
        previous = Path(self.temp.name) / "previous"
        small_source = proposed_source()
        small_source["phrases"] = small_source["phrases"][:4]
        with patch("sonar_vision.audio_catalog.proposed_source", return_value=small_source):
            write_proposal(previous, fixture=True)
        old_manifest, _ = read_json(previous / "manifest.json")
        old_manifest["entries"][0]["audio"]["origin"]["generation_version"] = "2"
        (previous / "manifest.json").write_bytes(serialized(old_manifest))
        # Same version with a different (valid) phrase inventory is not immutable.
        with self.assertRaisesRegex(CatalogError, "version_reused"):
            package_bundle(self.root, Path(self.temp.name) / "changed.zip", fixture=True, previous=previous)
        with patch("sonar_vision.audio_catalog.MAX_PACKAGE", 1):
            with self.assertRaisesRegex(CatalogError, "package_too_large"):
                package_bundle(self.root, Path(self.temp.name) / "large.zip", fixture=True)

    def test_cli_creation_validation_pack_and_failure_suppress_private_details(self):
        output = Path(self.temp.name) / "cli"
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main(["fixture", "--output", str(output)]), 0)
            self.assertEqual(main(["validate", str(output)]), 0)
            self.assertEqual(main(["pack", str(output), "--fixture", "--output",
                                   str(Path(self.temp.name) / "cli.zip")]), 0)
        self.assertIn('"synthetic_audio": 179', stdout.getvalue())
        with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
            main(["validate", str(output), "--require-release"])
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn(str(output), stderr.getvalue())
        with self.assertRaisesRegex(CatalogError, "output_exists"):
            write_proposal(output)

    def test_duplicate_nonfinite_json_and_size_bound(self):
        path = Path(self.temp.name) / "bad.json"
        for bad in (b'{"a":1,"a":2}', b'{"a":NaN}', b"\xff", b"{"):
            path.write_bytes(bad)
            with self.assertRaises(CatalogError):
                read_json(path)
        path.write_bytes(b"{}" + b" " * 40)
        with patch("sonar_vision.audio_catalog.MAX_JSON", 20):
            with self.assertRaisesRegex(CatalogError, "json_too_large"):
                read_json(path)


    def test_source_checksum_survives_checkout_crlf_and_json_formatting(self):
        source = (self.root / "phrases.json").read_bytes()
        (self.root / "phrases.json").write_bytes(source.replace(b"\n", b"\r\n"))
        self.assertTrue(load_bundle(self.root)["metadata_valid"])
        (self.root / "phrases.json").write_text(
            json.dumps(self.source, ensure_ascii=False), encoding="utf-8")
        self.assertTrue(load_bundle(self.root)["metadata_valid"])

    def test_phrase_and_file_versions_are_immutable_with_previous_catalog(self):
        previous = Path(self.temp.name) / "previous-text"
        small_source = proposed_source()
        small_source["phrases"] = small_source["phrases"][:4]
        with patch("sonar_vision.audio_catalog.proposed_source", return_value=small_source):
            write_proposal(previous, fixture=True)
        old_source, _ = read_json(previous / "phrases.json")
        old_manifest, _ = read_json(previous / "manifest.json")
        old_source["phrases"][0]["text"] = "Aviso local"
        old_manifest["catalog_version"] = "0.0.1-draft.1"
        old_manifest["phrases_sha256"] = digest(serialized(old_source))
        old_manifest["entries"][0]["text"] = "Aviso local"
        old_manifest["entries"][0]["text_sha256"] = digest(b"Aviso local")
        (previous / "phrases.json").write_bytes(serialized(old_source))
        (previous / "manifest.json").write_bytes(serialized(old_manifest))
        with self.assertRaisesRegex(CatalogError, "phrase_version_reused"):
            package_bundle(self.root, Path(self.temp.name) / "bad-text.zip",
                           fixture=True, previous=previous)
        self.source["phrase_version"] = "0.1.0-draft.2"
        self.raw = serialized(self.source)
        self.manifest.update(phrase_version=self.source["phrase_version"],
                             phrases_sha256=digest(self.raw))
        self.save()
        self.assertEqual(package_bundle(self.root, Path(self.temp.name) / "updated.zip",
                                        fixture=True, previous=previous)["kind"], "fixture")

    def test_empty_missing_entry_unknown_field_and_schema_rejected(self):
        baseline = deepcopy(self.manifest)
        for mutate in (
                lambda m: m.update(schema_version=True),
                lambda m: m.update(status="production"),
                lambda m: m.update(extra="unsupported"),
                lambda m: m["entries"].pop(),
                lambda m: m["entries"][0].update(id="unknown.id")):
            self.manifest = deepcopy(baseline)
            mutate(self.manifest)
            with self.assertRaises(CatalogError):
                self.validate()
        self.manifest = deepcopy(baseline)
        self.manifest["entries"][0]["audio"] = None
        self.assertEqual(self.validate()["missing_audio"], 1)
        output = Path(self.temp.name) / "draft.zip"
        with self.assertRaisesRegex(CatalogError, "release_not_ready"):
            package_bundle(self.root, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
