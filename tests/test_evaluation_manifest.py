from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest

from sonar_vision.evaluation_manifest import validate_manifest, load_manifest, main, _unique_keys

EXAMPLE = Path(__file__).resolve().parents[1] / "docs/experiments/manifest-example.json"


def recorded(split="test", *, clip_id="recorded-1", group="take-1", digest="a"):
    manifest = json.loads(EXAMPLE.read_text(encoding="utf-8-sig"))
    clip = manifest["clips"][0]
    clip.update(clip_id=clip_id, source_group_id=group, sha256=digest * 64,
                kind="recorded", recorded_on="2026-10-01", camera="camera-model",
                split=split, permission_reference="permission-record-1",
                ethics_reference="institution-review-1", annotation_reference="annotation-v1")
    return manifest


class ManifestTests(unittest.TestCase):
    def test_synthetic_example_does_not_count_as_real_coverage(self):
        report = load_manifest(EXAMPLE)
        self.assertEqual(report["counts"], {"recorded": 0, "synthetic": 1})
        self.assertEqual(len(report["missing_recorded_classes"]), 9)
        self.assertEqual(len(report["missing_recorded_scenarios"]), 8)
        self.assertEqual(len(report["missing_recorded_lighting"]), 3)
        self.assertEqual(report["approval_status"], "pending")

    def test_real_metadata_updates_only_declared_coverage(self):
        report = validate_manifest(recorded())
        self.assertEqual(report["counts"]["recorded"], 1)
        self.assertNotIn("person", report["missing_recorded_classes"])
        self.assertIn("stairs", report["missing_recorded_classes"])
        self.assertEqual(report["approval_status"], "pending")

    def test_missing_fields_and_unknown_fields_rejected(self):
        base = recorded()
        variants = []
        for scope in ("manifest", "clip"):
            bad = deepcopy(base)
            target = bad if scope == "manifest" else bad["clips"][0]
            target["extra"] = "not allowed"
            variants.append(bad)
            bad = deepcopy(base)
            target = bad if scope == "manifest" else bad["clips"][0]
            del target["approval" if scope == "manifest" else "camera"]
            variants.append(bad)
        for bad in variants:
            with self.assertRaises(ValueError):
                validate_manifest(bad)

    def test_invalid_dates_numbers_classes_and_vocabulary(self):
        for key, value in (("recorded_on", "2026-02-30"), ("recorded_on", "20261001"),
                           ("fps", float("nan")), ("width", True), ("height", 0),
                           ("duration_s", -1), ("lux", -1), ("distance_start_m", float("inf")),
                           ("classes", ["person", "person"]), ("classes", ["child"]),
                           ("scenario", []), ("lighting", "invented"), ("sha256", "bad")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                manifest = recorded()
                manifest["clips"][0][key] = value
                validate_manifest(manifest)

    def test_permission_ethics_and_annotations_required_for_test_recordings(self):
        for key in ("permission_reference", "ethics_reference", "annotation_reference"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                manifest = recorded()
                manifest["clips"][0][key] = None
                validate_manifest(manifest)

    def test_exploration_and_demo_are_not_independent_controlled_tests(self):
        manifest = recorded("exploration")
        manifest["clips"][0]["stage"] = "exploratory"
        self.assertTrue(validate_manifest(manifest)["metadata_valid"])
        manifest["clips"][0]["split"] = "test"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest = recorded("demo")
        manifest["clips"][0]["stage"] = "integrated"
        self.assertTrue(validate_manifest(manifest)["metadata_valid"])

    def test_group_leakage_between_tuning_and_test(self):
        manifest = recorded("tuning")
        other = recorded("test", clip_id="recorded-2", digest="b")["clips"][0]
        manifest["clips"].append(other)
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_exploratory_source_is_not_independent_test_material(self):
        manifest = recorded("exploration")
        manifest["clips"][0]["stage"] = "exploratory"
        manifest["clips"].append(recorded("test", clip_id="recorded-2", digest="b")["clips"][0])
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_same_content_cannot_cross_partitions_under_another_group(self):
        manifest = recorded("tuning")
        other = recorded("test", clip_id="recorded-2", group="take-2")["clips"][0]
        manifest["clips"].append(other)
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_duplicates_and_synthetic_mislabeling_rejected(self):
        manifest = recorded()
        manifest["clips"].append(deepcopy(manifest["clips"][0]))
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest = json.loads(EXAMPLE.read_text(encoding="utf-8-sig"))
        manifest["clips"][0]["split"] = "test"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_approval_requires_references_but_does_not_claim_verification(self):
        manifest = recorded()
        manifest["approval"]["status"] = "approved"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest["approval"].update(reference="group-review-record",
                                    parameters_reference="frozen-protocol-v1")
        report = validate_manifest(manifest)
        self.assertEqual(report["approval_status"], "approved")
        self.assertIn("Structure only", report["limitations"][0])

    def test_stairs_and_negative_controls(self):
        manifest = recorded()
        manifest["clips"][0].update(scenario="stairs_up")
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
        manifest["clips"][0]["classes"] = ["stairs"]
        self.assertTrue(validate_manifest(manifest)["metadata_valid"])
        manifest["clips"][0].update(scenario="negative", classes=[])
        self.assertTrue(validate_manifest(manifest)["metadata_valid"])

    def test_unknown_measurements_remain_null_not_invented(self):
        manifest = recorded()
        before = deepcopy(manifest)
        validate_manifest(manifest)
        self.assertEqual(manifest, before)
        self.assertIsNone(manifest["clips"][0]["lux"])
        self.assertIsNone(manifest["clips"][0]["distance_start_m"])

    def test_duplicate_json_keys_and_cli_success_failure(self):
        with self.assertRaises(ValueError):
            json.loads('{"schema_version":1,"schema_version":1}', object_pairs_hook=_unique_keys)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([str(EXAMPLE)]), 0)
        self.assertEqual(json.loads(output.getvalue())["counts"]["recorded"], 0)
        errors = io.StringIO()
        with redirect_stderr(errors), self.assertRaises(SystemExit) as raised:
            main([str(EXAMPLE.parent / "missing-private-path.json")])
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn("missing-private-path", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
