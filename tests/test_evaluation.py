"""Known-answer synthetic evaluation tests; no real accuracy or sensor evidence."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
from itertools import combinations, permutations
import json
from pathlib import Path
import random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision.core import Detection, Frame, VisionService
from sonar_vision.evaluation import (comparison, evaluate, frame_from_result, iou,
                                     load_input, main, markdown_summary, match,
                                     optimal_pairs, validate_input, write_outputs)

EXAMPLE = Path(__file__).resolve().parents[1] / "docs/experiments/issue-33-fixture.json"


def fixture():
    return load_input(EXAMPLE)


def single():
    value = fixture()
    value["dataset_manifest"]["clips"] = value["dataset_manifest"]["clips"][:1]
    value["frames"] = value["frames"][:1]
    return value


def gt(cls="person", identity="p", box=None, stair=None, visible=True):
    return {"reference_id": identity, "class_name": cls, "box": box or [0.1, 0.1, 0.4, 0.8],
            "visible": visible, "stair_direction": stair}


def pred(cls="person", identity="1", box=None, stair=None, score=0.8):
    return {"track_id": identity, "class_name": cls, "box": box or [0.1, 0.1, 0.4, 0.8],
            "confidence": score, "stair_direction": stair}


class MatchingTests(unittest.TestCase):
    def test_iou_exact_disjoint_and_partial_overlap(self):
        self.assertEqual(iou([0, 0, 1, 1], [0, 0, 1, 1]), 1)
        self.assertEqual(iou([0, 0, .5, .5], [.5, .5, 1, 1]), 0)
        self.assertAlmostEqual(iou([0, 0, 1, 1], [0, 0, .5, .5]), .25)

    def test_assignment_cardinality_precedes_largest_single_overlap(self):
        matrix = [[.99, .51], [.51, -1]]
        self.assertEqual(optimal_pairs(matrix), [(0, 1), (1, 0)])
        self.assertEqual(optimal_pairs([]), [])
        self.assertEqual(optimal_pairs([[]]), [])
        self.assertEqual(optimal_pairs([[-1, -1]]), [])
        self.assertEqual(optimal_pairs([[1, 1], [1, 1]]), [(0, 0), (1, 1)])

    def test_hungarian_agrees_with_independent_bruteforce_small_matrices(self):
        rng = random.Random(33)
        for rows, cols in ((1, 3), (3, 1), (2, 3), (3, 2), (3, 3)):
            for _ in range(12):
                matrix = [[rng.choice([-1, .5, .7, .9]) for _ in range(cols)] for _ in range(rows)]
                possibilities = [(0, 0)]
                for count in range(1, min(rows, cols) + 1):
                    for selected_rows in combinations(range(rows), count):
                        for selected_cols in permutations(range(cols), count):
                            values = [matrix[r][c] for r, c in zip(selected_rows, selected_cols)]
                            if all(v >= 0 for v in values):
                                possibilities.append((count, sum(values)))
                expected = max(possibilities)
                pairs = optimal_pairs(matrix)
                self.assertEqual(len(pairs), expected[0])
                self.assertAlmostEqual(sum(matrix[r][c] for r, c in pairs), expected[1])

    def test_iou_threshold_is_inclusive_class_aware_and_one_to_one(self):
        refs = [gt(box=[0, 0, 1, 1])]
        preds = [pred(box=[0, 0, .5, 1])]
        self.assertEqual(match(refs, preds, .5), [(0, 0)])
        self.assertEqual(match(refs, preds, .5001), [])
        preds[0]["class_name"] = "car"
        self.assertEqual(match(refs, preds, .5), [])
        self.assertEqual(match(refs, preds, .5, class_aware=False), [(0, 0)])


class EvaluationTests(unittest.TestCase):
    def test_fixture_known_answer_detection_latency_tracking_and_stairs(self):
        data = fixture()
        before = deepcopy(data)
        report, review = evaluate(data)
        self.assertEqual(data, before)
        self.assertEqual([report["overall"][k] for k in ("tp", "fp", "fn")], [5, 2, 2])
        self.assertAlmostEqual(report["overall"]["precision"], 5 / 7)
        self.assertAlmostEqual(report["overall"]["recall"], 5 / 7)
        self.assertEqual(report["by_class"]["person"]["tp"], 3)
        self.assertEqual(report["latency"], {"samples": 8, "mean_ms": 285,
                                           "p50_ms": 40, "p95_ms": 2000, "p99_ms": 2000, "max_ms": 2000})
        self.assertAlmostEqual(report["effective_fps"], 7 / 3)
        self.assertEqual(report["tracking"]["id_switch"], 1)
        self.assertEqual(report["tracking"]["fragmentation"], 1)
        self.assertEqual(report["tracking"]["epoch_reset"], 1)
        self.assertEqual(report["tracking"]["detection_loss"], 2)
        self.assertEqual(report["stairs"]["matrix"]["down"],
                         {"up": 1, "down": 0, "unknown": 1, "missed": 1})
        self.assertEqual(report["stairs"]["abstentions"], 1)
        self.assertEqual(report["stairs"]["accuracy_all_known"], 0)
        self.assertAlmostEqual(report["stairs"]["answer_coverage_all_known"], 1 / 3)
        self.assertFalse(report["acceptance_evaluated"])
        self.assertTrue(any(event["event"] == "id_switch" for event in review))

    def test_wrong_class_counts_fp_and_fn_and_records_confusion(self):
        data = single()
        data["frames"][0]["predictions"] = [pred("car")]
        report, _ = evaluate(data)
        self.assertEqual([report["overall"][k] for k in ("tp", "fp", "fn")], [0, 1, 1])
        self.assertEqual(report["class_confusions"], [{"truth": "person", "prediction": "car", "count": 1}])
        self.assertEqual(report["by_class"]["car"]["fp"], 1)
        self.assertEqual(report["by_class"]["person"]["fn"], 1)

    def test_duplicate_prediction_is_false_positive_not_another_person(self):
        data = single()
        data["frames"][0]["predictions"].append(pred(identity="2"))
        report, _ = evaluate(data)
        self.assertEqual([report["overall"][k] for k in ("tp", "fp", "fn")], [1, 1, 0])
        self.assertNotIn("people_count", report)
        self.assertNotIn("accuracy", report["overall"])

    def test_low_score_filter_boundary_and_confidence_not_accuracy(self):
        for score, tp in ((.4999, 0), (.5, 1), (.99, 1)):
            data = single()
            data["frames"][0]["predictions"][0]["confidence"] = score
            report, _ = evaluate(data)
            self.assertEqual(report["overall"]["tp"], tp)
            self.assertEqual(report["overall"]["filtered_predictions"], 1 - tp)
        data = single()
        data["frames"][0]["predictions"][0].update(confidence=.99, box=[.6, .1, .9, .8])
        report, _ = evaluate(data)
        self.assertEqual(report["overall"]["tp"], 0)
        self.assertEqual(report["overall"]["precision"], 0)

    def test_empty_negative_frames_no_zero_denominator_accuracy(self):
        data = single()
        data["dataset_manifest"]["clips"][0].update(scenario="negative", classes=[])
        data["frames"][0].update(ground_truth=[], predictions=[])
        report, _ = evaluate(data)
        self.assertIsNone(report["overall"]["precision"])
        self.assertIsNone(report["overall"]["recall"])
        self.assertIsNone(report["overall"]["f1"])
        self.assertIsNone(report["stairs"]["accuracy_all_known"])
        self.assertTrue(report["by_class"]["stairs"]["insufficient_sample"])

    def test_invisible_reference_and_overlapping_prediction_are_explicitly_ignored(self):
        data = single()
        data["frames"][0]["ground_truth"][0]["visible"] = False
        report, _ = evaluate(data)
        self.assertEqual([report["overall"][k] for k in ("tp", "fp", "fn")], [0, 0, 0])
        self.assertEqual(report["overall"]["ignored_references"], 1)
        self.assertEqual(report["overall"]["ignored_predictions"], 1)
        data["frames"][0]["predictions"][0]["box"] = [.6, .1, .9, .8]
        report, _ = evaluate(data)
        self.assertEqual(report["overall"]["fp"], 1)

    def test_visible_match_has_priority_over_ignore_region(self):
        data = single()
        data["frames"][0]["ground_truth"].append(gt(identity="hidden", visible=False))
        report, _ = evaluate(data)
        self.assertEqual(report["overall"]["tp"], 1)
        self.assertEqual(report["overall"]["ignored_predictions"], 0)

    def test_warmup_excluded_and_failures_not_erased_from_latency_or_detection(self):
        data = single()
        warmup = deepcopy(data["frames"][0])
        warmup.update(frame_index=0, status="warmup", latency_ms=999)
        data["frames"][0].update(frame_index=1, status="timeout", predictions=[], latency_ms=2000)
        data["frames"].insert(0, warmup)
        report, _ = evaluate(data)
        self.assertEqual(report["overall"]["evaluated_frames"], 1)
        self.assertEqual(report["overall"]["fn"], 1)
        self.assertEqual(report["latency"]["samples"], 1)
        self.assertEqual(report["latency"]["mean_ms"], 2000)
        self.assertEqual(report["statuses"], {"timeout": 1, "warmup": 1})

    def test_null_latency_and_no_fps_are_not_invented(self):
        data = single()
        data["run"]["elapsed_ms"] = None
        data["frames"][0].update(status="decode_error", predictions=[], latency_ms=None)
        report, _ = evaluate(data)
        self.assertIsNone(report["latency"])
        self.assertIsNone(report["effective_fps"])
        self.assertEqual(report["overall"]["fn"], 1)
        self.assertEqual(report["latency_by_condition"][0]["statuses"], {"decode_error": 1})

    def test_grouping_and_independence_use_sources_not_video_cuts(self):
        data = single()
        second = deepcopy(data["dataset_manifest"]["clips"][0])
        second["clip_id"] = "cut2"
        data["dataset_manifest"]["clips"].append(second)
        frame = deepcopy(data["frames"][0])
        frame["clip_id"] = "cut2"
        data["frames"].append(frame)
        report, _ = evaluate(data)
        self.assertEqual(report["overall"]["independent_sources"], 1)
        self.assertTrue(report["overall"]["insufficient_sample"])
        self.assertEqual(report["by_condition"][0]["evaluated_frames"], 2)

    def test_gap_epoch_null_id_and_occlusion_do_not_create_false_id_switches(self):
        data = single()
        for i, ident in ((1, None), (2, "2"), (6, "3"), (7, "4")):
            frame = deepcopy(data["frames"][0])
            frame.update(frame_index=i, tracker_epoch="reset" if i == 7 else "e1")
            frame["predictions"] = [pred(identity=ident)]
            data["frames"].append(frame)
        report, _ = evaluate(data)
        self.assertEqual(report["tracking"]["id_switch"], 1)
        self.assertEqual(report["tracking"]["fragmentation"], 1)
        self.assertEqual(report["tracking"]["continuity_break"], 1)
        self.assertEqual(report["tracking"]["epoch_reset"], 1)
        self.assertEqual(report["tracking"]["unassigned"], 1)
        data = single()
        hidden = deepcopy(data["frames"][0])
        hidden["frame_index"] = 1
        hidden["ground_truth"][0]["visible"] = False
        returning = deepcopy(data["frames"][0])
        returning["frame_index"] = 2
        returning["predictions"][0]["track_id"] = "other"
        data["frames"] += [hidden, returning]
        report, _ = evaluate(data)
        self.assertNotIn("id_switch", report["tracking"])

    def test_identity_transfer_and_track_isolation_between_clips(self):
        data = single()
        frame = deepcopy(data["frames"][0])
        frame["frame_index"] = 1
        frame["ground_truth"].append(gt(identity="other", box=[.6, .1, .9, .8]))
        frame["predictions"] = [pred(identity="1", box=[.6, .1, .9, .8])]
        data["frames"].append(frame)
        report, _ = evaluate(data)
        self.assertEqual(report["tracking"]["identity_transfer"], 1)
        self.assertEqual(report["tracking"]["detection_loss"], 1)
        data = fixture()
        data["frames"][-2]["predictions"] = [pred("person")]
        report, _ = evaluate(data)
        self.assertEqual(report["tracking"].get("identity_transfer", 0), 0)

    def test_unknown_stair_truth_and_correct_direction_denominators(self):
        data = single()
        data["dataset_manifest"]["clips"][0]["classes"] = ["stairs"]
        data["frames"][0].update(ground_truth=[gt("stairs", stair="unknown")],
                                predictions=[pred("stairs", stair="up")])
        report, _ = evaluate(data)
        self.assertEqual(report["stairs"]["unknown_truth"], 1)
        self.assertIsNone(report["stairs"]["accuracy_all_known"])
        data["frames"][0]["ground_truth"][0]["stair_direction"] = "up"
        report, _ = evaluate(data)
        self.assertEqual(report["stairs"]["correct"], 1)
        self.assertEqual(report["stairs"]["accuracy_all_known"], 1)

    def test_baseline_comparability_requires_same_annotations_and_measurement(self):
        data, baseline = fixture(), fixture()
        baseline["frames"][0]["predictions"] = []
        result = comparison(data, baseline)
        self.assertTrue(result["comparable"])
        self.assertEqual(result["overall_delta"], {"tp": 1, "fp": 0, "fn": -1})
        baseline["run"]["latency_scope"] = "processing"
        self.assertFalse(comparison(data, baseline)["comparable"])
        self.assertIsNone(comparison(data, baseline)["overall_delta"])

    def test_internal_result_adapter_uses_boxes_without_altering_protocol(self):
        class Backend:
            def infer(self, image):
                return [Detection("person", .8, (.1, .1, .4, .8), "1")]
            def close(self):
                pass
        service = VisionService(Backend)
        service.open("synthetic", "s")
        result = service.process(Frame("synthetic", "s", "0", 0, object()))
        service.close("synthetic", "s")
        data = single()
        data["frames"][0] = frame_from_result("a", 0, result, [gt()], latency_ms=10)
        report, _ = evaluate(data)
        self.assertEqual(report["overall"]["tp"], 1)
        self.assertNotIn("box", result.observation()["objects"][0])

    def test_public_markdown_omits_identities_boxes_and_configuration_strings(self):
        data = single()
        data["run"]["run_id"] = "PRIVATE_SENTINEL"
        data["frames"][0]["ground_truth"][0]["reference_id"] = "PRIVATE_SENTINEL"
        data["frames"][0]["predictions"] = []
        report, review = evaluate(data)
        self.assertIn("PRIVATE_SENTINEL", json.dumps(review))
        summary = markdown_summary(report)
        self.assertNotIn("PRIVATE_SENTINEL", summary)
        self.assertNotIn("reference_id", summary)
        self.assertNotIn("box", summary)
        self.assertIn("N/A", summary)
        self.assertIn("good", summary)


class ValidationAndCLITests(unittest.TestCase):
    def test_invalid_bounds_types_order_and_duplicate_ids(self):
        for mutate in (
            lambda d: d.update(schema_version=True),
            lambda d: d["run"]["protocol"].update(iou_threshold=0),
            lambda d: d["run"]["protocol"].update(iou_threshold=float("nan")),
            lambda d: d["run"]["protocol"].update(max_gap_frames=True),
            lambda d: d["run"]["configuration"].update(detector_confidence=True),
            lambda d: d["run"]["configuration"].update(token="secret"),
            lambda d: d["run"].update(latency_clock="subtract_remote_timestamps"),
            lambda d: d["run"].update(elapsed_ms=-1),
            lambda d: d["frames"][0].update(latency_ms=True),
            lambda d: d["frames"][0].update(frame_index=-1),
            lambda d: d["frames"][0]["predictions"][0].update(box=[0, 0, 0, 1]),
            lambda d: d["frames"][0]["predictions"][0].update(confidence=1.01),
            lambda d: d["frames"][0]["ground_truth"][0].update(stair_direction="down"),
            lambda d: d["frames"][0]["ground_truth"].append(deepcopy(d["frames"][0]["ground_truth"][0])),
            lambda d: d["frames"].append(deepcopy(d["frames"][0])),
            lambda d: d["frames"][0].update(status="timeout"),
            lambda d: d["frames"][0].update(clip_id="missing")):
            data = single()
            mutate(data)
            with self.assertRaises(ValueError):
                evaluate(data)

    def test_recorded_requires_model_hash_annotations_and_no_mixed_partitions(self):
        data = fixture()
        clip = data["dataset_manifest"]["clips"][0]
        clip.update(kind="recorded", split="tuning", recorded_on="2026-10-02",
                    camera="camera", sha256="a" * 64, permission_reference="permission",
                    ethics_reference="ethics", annotation_reference="annotation")
        with self.assertRaisesRegex(ValueError, "mixed_evidence"):
            validate_input(data)
        data["dataset_manifest"]["clips"] = [clip]
        data["frames"] = data["frames"][:4]
        with self.assertRaisesRegex(ValueError, "recorded_model_hash"):
            validate_input(data)
        data["run"]["model"]["sha256"] = "b" * 64
        self.assertEqual(len(validate_input(data)), 1)
        clip["annotation_reference"] = None
        with self.assertRaisesRegex(ValueError, "annotation_required"):
            validate_input(data)

    def test_json_duplicate_nonfinite_size_and_empty_data(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b"\xff", b"{}"):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    evaluate(load_input(path))
            path.write_bytes(b"{}" + b" " * 30)
            with patch("sonar_vision.evaluation.MAX_INPUT", 20), self.assertRaises(ValueError):
                load_input(path)

    def test_cli_private_reports_public_summary_exclusive_outputs_and_sanitized_failures(self):
        with TemporaryDirectory() as directory:
            with patch("sonar_vision.evaluation.Path.cwd", return_value=Path(directory)):
                report_path = Path(directory) / "results/report.json"
                review_path = Path(directory) / "results/review.json"
                summary_path = Path(directory) / "docs/experiments/summary.md"
                args = [str(EXAMPLE), "--output", str(report_path), "--review", str(review_path),
                        "--summary", str(summary_path), "--baseline", str(EXAMPLE)]
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(args), 0)
                report = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(report["overall"]["tp"], 5)
                self.assertTrue(report["comparison"]["comparable"])
                self.assertTrue(review_path.exists())
                self.assertTrue(summary_path.exists())
                before = report_path.read_bytes()
                stderr = io.StringIO()
                with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                    main(args)
                self.assertEqual(raised.exception.code, 2)
                self.assertNotIn(directory, stderr.getvalue())
                self.assertEqual(report_path.read_bytes(), before)
                public_raw = Path(directory) / "docs/private.json"
                report, review = evaluate(single())
                with self.assertRaises(ValueError):
                    write_outputs(report, review, public_raw)
                self.assertFalse(public_raw.exists())
                with self.assertRaises(ValueError):
                    write_outputs(report, review, Path(directory) / "results/new.json",
                                  review_path=Path(directory) / "results/new.json")


    def test_numerically_unrepresentable_boxes_or_throughput_fail_explicitly(self):
        data = single()
        data["frames"][0]["ground_truth"][0]["box"] = [0, 0, 1e-300, 1e-300]
        with self.assertRaisesRegex(ValueError, "normalized_box"):
            evaluate(data)
        data = single()
        data["run"]["elapsed_ms"] = 1e-320
        with self.assertRaisesRegex(ValueError, "nonfinite_metric"):
            evaluate(data)

    def test_tool_capacity_and_unmeasured_clips_are_explicit(self):
        data = single()
        with patch("sonar_vision.evaluation.MAX_FRAMES", 0), self.assertRaises(ValueError):
            evaluate(data)
        with patch("sonar_vision.evaluation.MAX_OBJECTS", 0), self.assertRaises(ValueError):
            evaluate(data)
        data = fixture()
        data["frames"] = [f for f in data["frames"] if f["clip_id"] == "a"]
        report, _ = evaluate(data)
        self.assertEqual(report["clips_without_frames"], 2)
        self.assertTrue(report["by_class"]["stairs"]["insufficient_sample"])

    def test_warmup_only_and_changed_reference_do_not_invent_measurements(self):
        data = single()
        data["frames"][0]["status"] = "warmup"
        report, _ = evaluate(data)
        self.assertIsNone(report["latency"])
        self.assertEqual(report["overall"]["evaluated_frames"], 0)
        baseline = single()
        current = single()
        current["frames"][0]["ground_truth"][0]["box"] = [.2, .1, .4, .8]
        self.assertFalse(comparison(current, baseline)["comparable"])


if __name__ == "__main__":
    unittest.main()
