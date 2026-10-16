"""Paired motion metrics with known answers, not model accuracy."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision.core import Detection, Frame, VisionService
from sonar_vision.evaluation import canonical, frame_from_result, load_input
from sonar_vision.evaluate_motion import evaluate, main, motion_frame_from_result

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    return (load_input(ROOT / "docs/experiments/issue-33-fixture.json"),
            load_input(ROOT / "docs/experiments/issue-11-motion-fixture.json"))


def rebind(snapshot, sidecar):
    sidecar["snapshot_sha256"] = hashlib.sha256(canonical(snapshot)).hexdigest()


class MotionEvaluationTests(unittest.TestCase):
    def test_known_answer_keeps_missed_abstention_and_lateral_error(self):
        snapshot, sidecar = fixtures()
        before = deepcopy((snapshot, sidecar))
        report, review = evaluate(snapshot, sidecar)
        self.assertEqual((snapshot, sidecar), before)
        counts = report["overall"]
        self.assertEqual(counts["visible_references"], 7)
        self.assertEqual(counts["known_truth"], 6)
        self.assertEqual(counts["correct"], 2)
        self.assertEqual(counts["answered"], 3)
        self.assertEqual(counts["abstentions"], 1)
        self.assertEqual(counts["missed"], 2)
        self.assertAlmostEqual(counts["accuracy_all_known"], 2 / 6)
        self.assertEqual(counts["lateral_evaluable"], 1)
        self.assertEqual(counts["lateral_correct"], 0)
        self.assertEqual(counts["unknown_truth"], 1)
        self.assertEqual(report["camera_guard_violations"], 1)
        self.assertEqual(report["tracking"]["id_switch"], 1)
        self.assertEqual(len(review), 7)
        self.assertFalse(report["acceptance_evaluated"])

    def test_wrong_snapshot_or_frame_order_rejected(self):
        snapshot, sidecar = fixtures()
        wrong = deepcopy(snapshot)
        wrong["run"]["run_id"] = "other"
        with self.assertRaises(ValueError):
            evaluate(wrong, sidecar)
        sidecar["frames"][0], sidecar["frames"][1] = sidecar["frames"][1], sidecar["frames"][0]
        with self.assertRaises(ValueError):
            evaluate(snapshot, sidecar)

    def test_invalid_fields_types_time_and_labels(self):
        mutations = (
            lambda s: s.update(extra="private"),
            lambda s: s.update(schema_version=True),
            lambda s: s["trajectory_config"].pop("min_samples"),
            lambda s: s["trajectory_config"].update(min_samples=True),
            lambda s: s["frames"].pop(),
            lambda s: s["frames"][1].update(captured_at_ms=s["frames"][0]["captured_at_ms"]),
            lambda s: s["frames"][0].update(captured_at_ms=-1),
            lambda s: s["frames"][0].update(camera_motion=[]),
            lambda s: s["frames"][0]["references"].clear(),
            lambda s: s["frames"][0]["references"][0].update(reference_id="other"),
            lambda s: s["frames"][0]["references"][0].update(movement=[]),
            lambda s: s["frames"][0]["predictions"].clear(),
            lambda s: s["frames"][0]["predictions"][0].update(reason="private-value"),
            lambda s: s["frames"][0]["predictions"][0].update(lateral_direction="left_to_right"),
            lambda s: s["frames"][1]["references"][0].update(movement="stable"),
        )
        snapshot, sidecar = fixtures()
        for mutate in mutations:
            value = deepcopy(sidecar)
            mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                evaluate(snapshot, value)

    def test_invisible_and_warmup_are_separate_and_zero_denominator_is_null(self):
        snapshot, sidecar = fixtures()
        for base, motion in zip(snapshot["frames"], sidecar["frames"]):
            for ref in base["ground_truth"]:
                ref["visible"] = False
            for ref in motion["references"]:
                ref.update(movement="unknown", lateral_direction=None)
        snapshot["frames"][0]["status"] = "warmup"
        rebind(snapshot, sidecar)
        report, review = evaluate(snapshot, sidecar)
        self.assertEqual(report["warmup_frames"], 1)
        self.assertEqual(report["ignored_references"], 6)
        self.assertIsNone(report["overall"]["accuracy_all_known"])
        self.assertEqual(review, [])

    def test_confidence_filter_causes_missed_and_null_id_requires_abstention(self):
        snapshot, sidecar = fixtures()
        snapshot["frames"][0]["predictions"][0]["confidence"] = .1
        rebind(snapshot, sidecar)
        report, _ = evaluate(snapshot, sidecar)
        self.assertEqual(report["overall"]["missed"], 3)
        snapshot["frames"][0]["predictions"][0]["track_id"] = None
        rebind(snapshot, sidecar)
        with self.assertRaises(ValueError):
            evaluate(snapshot, sidecar)
        sidecar["frames"][0]["predictions"][0].update(movement="unknown", reason="no_track")
        evaluate(snapshot, sidecar)

    def test_segment_counts_do_not_treat_each_frame_as_a_segment(self):
        report, _ = evaluate(*fixtures())
        segments = report["segments"]
        self.assertEqual(segments["total"], 4)
        self.assertEqual(segments["known_truth"], 3)
        self.assertEqual(segments["with_missed"], 2)
        self.assertEqual(segments["with_abstention"], 1)
        self.assertEqual(segments["with_wrong_movement"], 1)

    def test_two_targets_with_same_segment_name_remain_distinct(self):
        snapshot, sidecar = fixtures()
        base, motion = snapshot["frames"][0], sidecar["frames"][0]
        reference = deepcopy(base["ground_truth"][0])
        reference.update(reference_id="other", box=[.6, .1, .9, .8])
        base["ground_truth"].append(reference)
        prediction = deepcopy(base["predictions"][0])
        prediction.update(track_id="4", box=[.6, .1, .9, .8])
        base["predictions"].append(prediction)
        label = deepcopy(motion["references"][0])
        label["reference_id"] = "other"
        motion["references"].append(label)
        motion["predictions"].append(deepcopy(motion["predictions"][0]))
        rebind(snapshot, sidecar)
        report, _ = evaluate(snapshot, sidecar)
        self.assertEqual(report["overall"]["known_truth"], 7)
        self.assertEqual(report["overall"]["correct"], 3)
        self.assertEqual(report["segments"]["total"], 5)

    def test_lateral_missing_and_wrong_direction_stay_in_denominator(self):
        snapshot, sidecar = fixtures()
        label = sidecar["frames"][4]["predictions"][0]
        label["lateral_direction"] = "left_to_right"
        report, _ = evaluate(snapshot, sidecar)
        self.assertEqual(report["overall"]["lateral_correct"], 1)
        label.update(movement="unknown", lateral_direction=None, reason="confirming_motion")
        report, _ = evaluate(snapshot, sidecar)
        self.assertEqual(report["overall"]["lateral_evaluable"], 1)
        self.assertEqual(report["overall"]["lateral_correct"], 0)

    def test_unknown_truth_has_no_known_accuracy_and_camera_control_not_hidden(self):
        snapshot, sidecar = fixtures()
        for frame in sidecar["frames"]:
            for ref in frame["references"]:
                ref.update(movement="unknown", lateral_direction=None)
        report, _ = evaluate(snapshot, sidecar)
        self.assertIsNone(report["overall"]["accuracy_all_known"])
        self.assertIsNone(report["overall"]["accuracy_when_answered"])
        self.assertEqual(report["overall"]["unknown_truth"], 7)
        self.assertEqual(report["camera_guard_violations"], 1)

    def test_aggregate_has_no_identity_paths_boxes_or_free_metadata(self):
        snapshot, sidecar = fixtures()
        snapshot["dataset_manifest"]["clips"][0]["measurement_method"] = "private-value"
        rebind(snapshot, sidecar)
        report, _ = evaluate(snapshot, sidecar)
        raw = json.dumps(report)
        for forbidden in ('"reference_id"', '"track_id"', '"box"', "private-value", '"segment_id"'):
            self.assertNotIn(forbidden, raw)


class MotionAdapterTests(unittest.TestCase):
    def test_adapter_copies_result_and_checks_predictions_not_only_count(self):
        class Backend:
            def infer(self, image):
                return image

            def close(self):
                pass

        service = VisionService(Backend)
        service.open("device", "session")
        try:
            result = service.process(Frame("device", "session", "0", 0,
                [Detection("person", .9, (.1, .1, .4, .8), "1")], camera_motion="fixed"))
            before = deepcopy(result.observation())
            reference = [{"reference_id": "r", "class_name": "person", "box": [.1, .1, .4, .8],
                          "visible": True, "stair_direction": None}]
            base = frame_from_result("clip", 0, result, reference, latency_ms=1)
            human = [{"reference_id": "r", "segment_id": "seg", "movement": "stable",
                      "lateral_direction": None}]
            record = motion_frame_from_result(base, result, camera_motion="fixed", references=human)
            self.assertEqual(record["captured_at_ms"], 0)
            self.assertEqual(record["predictions"][0]["reason"], "insufficient_history")
            self.assertEqual(result.observation(), before)
            record["references"][0]["movement"] = "unknown"
            self.assertEqual(human[0]["movement"], "stable")
            base["predictions"][0]["confidence"] = .8
            with self.assertRaises(ValueError):
                motion_frame_from_result(base, result, camera_motion="fixed", references=human)
        finally:
            service.close("device", "session")


class MotionCliTests(unittest.TestCase):
    def test_cli_validates_outputs_and_preserves_existing_file(self):
        snapshot, motion = fixtures()
        with TemporaryDirectory() as directory, patch("pathlib.Path.cwd", return_value=Path(directory)):
            root = Path(directory)
            a, b = root / "input.json", root / "motion.json"
            a.write_text(json.dumps(snapshot))
            b.write_text(json.dumps(motion))
            output, review = root / "results/report.json", root / "results/review.json"
            args = ["--snapshot", str(a), "--motion", str(b), "--output", str(output),
                    "--review", str(review)]
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(main(args), 0)
                if os.name != "nt":
                    self.assertEqual(review.stat().st_mode & 0o777, 0o600)
                before = output.read_bytes()
                self.assertEqual(main(args), 2)
                self.assertEqual(output.read_bytes(), before)
                bad = args[:]
                bad[5] = str(root / "outside.json")
                self.assertEqual(main(bad), 2)
                self.assertFalse((root / "outside.json").exists())
                b.write_text('{"schema_version":1,"schema_version":1,"private":"do-not-print"}')
                self.assertEqual(main(args), 2)
            self.assertNotIn("do-not-print", stdout.getvalue() + stderr.getvalue())
            self.assertNotIn(str(directory), stdout.getvalue() + stderr.getvalue())

    @unittest.skipIf(os.name == "nt", "symlink setup depends on host permissions")
    def test_results_symlink_cannot_redirect_output_outside_workspace(self):
        snapshot, motion = fixtures()
        with TemporaryDirectory() as directory, TemporaryDirectory() as outside:
            root = Path(directory)
            (root / "results").symlink_to(outside, target_is_directory=True)
            a, b = root / "input.json", root / "motion.json"
            a.write_text(json.dumps(snapshot))
            b.write_text(json.dumps(motion))
            with patch("pathlib.Path.cwd", return_value=root), redirect_stderr(io.StringIO()):
                status = main(["--snapshot", str(a), "--motion", str(b), "--output",
                               str(root / "results/report.json")])
            self.assertEqual(status, 2)
            self.assertFalse((Path(outside) / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
