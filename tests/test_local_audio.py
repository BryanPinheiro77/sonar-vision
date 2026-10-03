"""#25 local audio interface: documented examples and reference-model rules."""

from contextlib import redirect_stdout
import copy
from io import StringIO
from pathlib import Path
import unittest

from sonar_vision_local_audio.arbiter import Arbiter, Profile, Suggestion
from sonar_vision_local_audio.catalog import (CANDIDATE_PROFILE, ESSENTIAL_IDS, CatalogRejected,
                                              check_catalog, install)
from sonar_vision_local_audio.examples import build, load, main, run, to_suggestion

EXAMPLES = Path(__file__).resolve().parents[1] / "docs" / "protocol" / "exemplos-audio-local.json"


class DocumentedExamplesTests(unittest.TestCase):
    def setUp(self):
        self.doc = load(EXAMPLES)

    def test_every_documented_case_matches_the_model(self):
        self.assertEqual(run(self.doc), [])
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(main([str(EXAMPLES)]), 0)
        self.assertIn("failures=0", output.getvalue())

    def test_checker_detects_a_wrong_expectation(self):
        broken = copy.deepcopy(self.doc)
        broken["scenarios"][0]["expected"] = [["start", "local.urgent"]]
        broken["catalog_cases"][0]["expected"] = "installed"
        self.assertEqual(len(run(broken)), 2)

    def test_examples_cover_success_limits_and_failures(self):
        names = {s["name"] for s in self.doc["scenarios"]}
        for required in ("visual_valid", "visual_expired", "urgency_interrupts_and_blocks_old_captures",
                         "urgency_without_catalog", "catalog_misses", "availability_cooldown_and_oscillation"):
            self.assertIn(required, names)
        reasons = {c["expected"] for c in self.doc["catalog_cases"]}
        self.assertIn("rejected:essential_missing", reasons)
        self.assertIn("rejected:profile_incompatible", reasons)

    def test_examples_messages_are_contract_0_1(self):
        for scenario in self.doc["scenarios"]:
            for step in scenario["steps"]:
                if step["op"] == "suggestion" and scenario["name"] != "invalid_envelope_extra_field":
                    to_suggestion(step["message"])

    def test_examples_use_only_the_candidate_profile(self):
        self.assertEqual(self.doc["device_profile"], CANDIDATE_PROFILE)
        self.assertEqual(self.doc["catalog"]["profile"], CANDIDATE_PROFILE)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.doc = load(EXAMPLES)
        self.manifest, self.files = build(self.doc)

    def test_essential_warnings_are_required_locally(self):
        catalog = check_catalog(self.manifest, self.files, CANDIDATE_PROFILE)
        for phrase_id in ESSENTIAL_IDS:
            self.assertTrue(catalog.playable(phrase_id))

    def test_rejected_candidate_keeps_working_catalog(self):
        working, status = install(None, self.manifest, self.files, CANDIDATE_PROFILE)
        self.assertEqual(status, "installed")
        broken = {**self.manifest, "schema_version": 99}
        kept, status = install(working, broken, self.files, CANDIDATE_PROFILE)
        self.assertIs(kept, working)
        self.assertEqual(status, "rejected:schema_unsupported")

    def test_text_resolution_is_exact(self):
        catalog = check_catalog(self.manifest, self.files, CANDIDATE_PROFILE)
        self.assertIsNotNone(catalog.resolve_text("Pessoa à esquerda"))
        decomposed = "Pessoa à esquerda"  # same glyphs, not NFC
        self.assertIsNone(catalog.resolve_text(decomposed))
        self.assertIsNone(catalog.resolve_text("pessoa"))

    def test_non_nfc_or_long_text_is_rejected(self):
        for text in ("Pessoa à esquerda", "x" * 121, ""):
            manifest = copy.deepcopy(self.manifest)
            manifest["entries"][4]["text"] = text
            with self.assertRaises(CatalogRejected) as caught:
                check_catalog(manifest, self.files, CANDIDATE_PROFILE)
            self.assertEqual(caught.exception.reason, "entry_text_invalid")

    def test_bench_draft_only_with_explicit_flag(self):
        draft = {**self.manifest, "status": "draft"}
        with self.assertRaises(CatalogRejected):
            check_catalog(draft, self.files, CANDIDATE_PROFILE)
        check_catalog(draft, self.files, CANDIDATE_PROFILE, allow_draft=True)


class ArbiterTests(unittest.TestCase):
    def setUp(self):
        manifest, files = build(load(EXAMPLES))
        self.catalog = check_catalog(manifest, files, CANDIDATE_PROFILE)
        self.orientation = {}
        self.arbiter = Arbiter(self.catalog, "boot", {"1": 1000},
                               lambda captured: self.orientation.get(captured, 0.0))

    def suggestion(self, **changes):
        values = dict(message_id="m-1", session_id="boot", frame_id="1", captured_at_ms=1000,
                      valid_for_ms=1000, text="Pessoa à esquerda", directional=True)
        values.update(changes)
        return Suggestion(**values)

    def test_validity_boundary_is_age_equal_limit(self):
        self.arbiter.suggestion(1999, self.suggestion())
        self.assertEqual(self.arbiter.log[0], ("accepted", "m-1"))
        other = Arbiter(self.catalog, "boot", {"1": 1000}, lambda captured: 0.0)
        other.suggestion(2000, self.suggestion())
        self.assertEqual(other.log, [("discard", "m-1", "expired")])

    def test_remote_validity_cannot_extend_local_limit(self):
        self.arbiter.suggestion(2500, self.suggestion(valid_for_ms=5000))
        self.assertEqual(self.arbiter.log, [("discard", "m-1", "expired")])

    def test_orientation_boundary_is_strictly_greater(self):
        self.orientation[1000] = 15.0
        self.arbiter.suggestion(1100, self.suggestion())
        self.assertEqual(self.arbiter.log[-1][0], "start")
        self.orientation[1000] = 15.01
        self.arbiter.tick(1200)
        self.assertEqual(self.arbiter.log[-1][2], "orientation_changed")

    def test_directional_speech_expires_while_playing(self):
        self.arbiter.suggestion(1100, self.suggestion())
        self.arbiter.tick(2000)
        self.assertEqual(self.arbiter.log[-1], ("interrupt", "visual.person.left.unknown.none", "expired"))

    def test_urgent_warning_is_generic(self):
        self.arbiter.suggestion(1100, self.suggestion())
        self.arbiter.urgency(1200, True)
        started = [event[1] for event in self.arbiter.log if event[0] == "start"]
        self.assertEqual(started[-1], "local.urgent")
        self.assertEqual(self.catalog.entries["local.urgent"].text, "Atenção")

    def test_invalid_availability_state(self):
        with self.assertRaises(ValueError):
            self.arbiter.availability(1, "maybe")

    def test_profile_defaults_match_contract_0_1(self):
        self.assertEqual(Profile(), Profile(1000, 15.0, 10000))


if __name__ == "__main__":
    unittest.main()
