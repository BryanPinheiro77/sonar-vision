"""Offline paired apparent-motion evaluation for #11; no media, network or risk."""

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys

from .core import Result
from .evaluation import (
    canonical, evaluate as evaluate_detection, fields, frame_from_result,
    integer, load_input, match, ratio, require, token, validate_input,
)
from .trajectory import Motion, TrajectoryConfig

MOVEMENTS = ("approaching", "receding", "crossing", "stable", "unknown")
CAMERAS = ("fixed", "moving", "unknown")
REASONS = ("insufficient_history", "no_track", "camera_not_fixed",
           "nonincreasing_capture_time", "confirming_motion", "unstable_boxes",
           "mixed_scale_and_lateral", "vertical_motion", "apparent_scale_change",
           "apparent_lateral_motion", "below_motion_thresholds")


def _label(value, *, human):
    expected = {"movement", "lateral_direction"} | (
        {"reference_id", "segment_id"} if human else {"reason"})
    fields(value, expected, "motion_label_fields")
    require(isinstance(value["movement"], str) and value["movement"] in MOVEMENTS,
            "motion_label")
    lateral = value["lateral_direction"]
    require(lateral in (None, "left_to_right", "right_to_left")
            and (value["movement"] == "crossing" or lateral is None), "lateral_label")
    if human:
        require(token(value["reference_id"]) and token(value["segment_id"]), "human_identity")
    else:
        require(isinstance(value["reason"], str) and value["reason"] in REASONS, "motion_reason")


def validate_motion(snapshot, sidecar):
    clips = validate_input(snapshot)
    fields(sidecar, {"schema_version", "snapshot_sha256", "trajectory_config", "frames"},
           "motion_input_fields")
    require(type(sidecar["schema_version"]) is int and sidecar["schema_version"] == 1,
            "motion_version")
    digest = hashlib.sha256(canonical(snapshot)).hexdigest()
    require(sidecar["snapshot_sha256"] == digest, "snapshot_mismatch")
    fields(sidecar["trajectory_config"], set(asdict(TrajectoryConfig())), "trajectory_config_fields")
    TrajectoryConfig(**sidecar["trajectory_config"])
    frames = sidecar["frames"]
    require(isinstance(frames, list) and len(frames) == len(snapshot["frames"]), "motion_frame_count")
    last_time, segment_labels = {}, {}
    for base, frame in zip(snapshot["frames"], frames):
        fields(frame, {"clip_id", "frame_index", "captured_at_ms", "camera_motion",
                       "references", "predictions"}, "motion_frame_fields")
        require(token(frame["clip_id"]) and frame["clip_id"] == base["clip_id"]
                and integer(frame["frame_index"]) and frame["frame_index"] == base["frame_index"],
                "motion_frame_alignment")
        require(integer(frame["captured_at_ms"])
                and frame["captured_at_ms"] > last_time.get(frame["clip_id"], -1), "capture_time")
        last_time[frame["clip_id"]] = frame["captured_at_ms"]
        require(isinstance(frame["camera_motion"], str) and frame["camera_motion"] in CAMERAS,
                "camera_context")
        require(isinstance(frame["references"], list)
                and len(frame["references"]) == len(base["ground_truth"]), "motion_reference_count")
        require(isinstance(frame["predictions"], list)
                and len(frame["predictions"]) == len(base["predictions"]), "motion_prediction_count")
        for ref, label in zip(base["ground_truth"], frame["references"]):
            _label(label, human=True)
            require(label["reference_id"] == ref["reference_id"], "motion_reference_alignment")
            key = (frame["clip_id"], label["reference_id"], label["segment_id"])
            truth = (label["movement"], label["lateral_direction"])
            require(segment_labels.get(key, truth) == truth, "segment_label_changed")
            segment_labels[key] = truth
        for pred, label in zip(base["predictions"], frame["predictions"]):
            _label(label, human=False)
            require(pred["track_id"] is not None or
                    (label["movement"] == "unknown" and label["reason"] == "no_track"),
                    "unassigned_motion")
    return clips


def motion_frame_from_result(base_frame, result, *, camera_motion, references):
    """Pair an existing #33 frame with Result; caller aligns original capture/labels.

    No inference, human labels, camera context or timestamps are invented here.
    Pending raw lateral candidates are omitted until movement is crossing.
    """
    require(isinstance(result, Result), "vision_result")
    expected = frame_from_result(base_frame["clip_id"], base_frame["frame_index"], result,
                                 base_frame["ground_truth"], latency_ms=base_frame["latency_ms"])
    require(base_frame == expected, "result_frame_mismatch")
    require(isinstance(camera_motion, str) and camera_motion in CAMERAS, "camera_context")
    require(isinstance(references, list) and len(references) == len(base_frame["ground_truth"]),
            "motion_reference_count")
    for ref, label in zip(base_frame["ground_truth"], references):
        _label(label, human=True)
        require(ref["reference_id"] == label["reference_id"], "motion_reference_alignment")
    predictions = []
    for detection in result.detections:
        if detection.track_id is None:
            motion = Motion(reason="no_track")
        else:
            require(detection.track_id in result.motions, "missing_result_motion")
            motion = result.motions[detection.track_id]
        value = {"movement": motion.movement, "reason": motion.reason,
                 "lateral_direction": motion.lateral_direction if motion.movement == "crossing" else None}
        _label(value, human=False)
        predictions.append(value)
    return {"clip_id": base_frame["clip_id"], "frame_index": base_frame["frame_index"],
            "captured_at_ms": result.captured_at_ms, "camera_motion": camera_motion,
            "references": deepcopy(references), "predictions": predictions}


def _bucket():
    return {truth: {observed: 0 for observed in (*MOVEMENTS, "missed")} for truth in MOVEMENTS}


def _finish(matrix, lateral):
    known = sum(sum(matrix[t].values()) for t in MOVEMENTS if t != "unknown")
    answered = sum(matrix[t][p] for t in MOVEMENTS if t != "unknown"
                   for p in MOVEMENTS if p != "unknown")
    correct = sum(matrix[t][t] for t in MOVEMENTS if t != "unknown")
    return {"matrix": matrix, "visible_references": sum(sum(r.values()) for r in matrix.values()),
            "known_truth": known, "unknown_truth": sum(matrix["unknown"].values()),
            "answered": answered, "correct": correct,
            "abstentions": sum(matrix[t]["unknown"] for t in MOVEMENTS if t != "unknown"),
            "missed": sum(matrix[t]["missed"] for t in MOVEMENTS if t != "unknown"),
            "accuracy_all_known": ratio(correct, known),
            "answer_coverage_all_known": ratio(answered, known),
            "accuracy_when_answered": ratio(correct, answered),
            "lateral_evaluable": lateral["evaluable"], "lateral_correct": lateral["correct"],
            "lateral_accuracy_all_labeled_crossings": ratio(lateral["correct"], lateral["evaluable"])}


def evaluate(snapshot, sidecar):
    clips = validate_motion(snapshot, sidecar)
    detection, _ = evaluate_detection(snapshot)
    matrix, lateral = _bucket(), Counter()
    groups, segments, review = {}, {}, []
    reasons = Counter()
    ignored = warmup = guard_violations = 0
    threshold = snapshot["run"]["protocol"]["iou_threshold"]
    cutoff = snapshot["run"]["configuration"]["detector_confidence"]
    for base, frame in zip(snapshot["frames"], sidecar["frames"]):
        if base["status"] == "warmup":
            warmup += 1
            continue
        clip = clips[base["clip_id"]]
        visible = [(ref, label) for ref, label in zip(base["ground_truth"], frame["references"])
                   if ref["visible"]]
        ignored += len(base["ground_truth"]) - len(visible)
        eligible = [(pred, label) for pred, label in zip(base["predictions"], frame["predictions"])
                    if pred["confidence"] >= cutoff]
        guard_violations += sum(label["movement"] != "unknown" for _, label in eligible
                                if frame["camera_motion"] != "fixed")
        pairs = match([r for r, _ in visible], [p for p, _ in eligible], threshold)
        assigned = {r: p for r, p in pairs}
        for index, (ref, human) in enumerate(visible):
            prediction = eligible[assigned[index]][1] if index in assigned else None
            observed = prediction["movement"] if prediction else "missed"
            truth = human["movement"]
            reason = prediction["reason"] if prediction else "missed"
            key = (ref["class_name"], clip["lighting"], clip["scenario"], frame["camera_motion"])
            cell, cell_lateral = groups.setdefault(key, (_bucket(), Counter()))
            matrix[truth][observed] += 1
            cell[truth][observed] += 1
            labeled_crossing = truth == "crossing" and human["lateral_direction"] is not None
            lateral_correct = bool(labeled_crossing and prediction and observed == "crossing"
                                   and prediction["lateral_direction"] == human["lateral_direction"])
            if labeled_crossing:
                lateral["evaluable"] += 1
                cell_lateral["evaluable"] += 1
                lateral["correct"] += lateral_correct
                cell_lateral["correct"] += lateral_correct
            if observed == "unknown":
                reasons[reason] += 1
            segment = segments.setdefault((base["clip_id"], human["reference_id"], human["segment_id"]),
                                          {"truth": truth, "missed": False, "abstention": False,
                                           "wrong_movement": False, "wrong_lateral": False})
            segment["missed"] |= observed == "missed"
            segment["abstention"] |= observed == "unknown"
            segment["wrong_movement"] |= truth != "unknown" and observed not in (truth, "unknown", "missed")
            segment["wrong_lateral"] |= labeled_crossing and not lateral_correct
            review.append({"clip_id": base["clip_id"], "frame_index": base["frame_index"],
                           "captured_at_ms": frame["captured_at_ms"], "reference_id": ref["reference_id"],
                           "segment_id": human["segment_id"], "truth": truth, "observed": observed,
                           "reason": reason, "lateral_evaluable": labeled_crossing,
                           "lateral_correct": lateral_correct,
                           "track_id": eligible[assigned[index]][0]["track_id"] if prediction else None})
    known_segments = [s for s in segments.values() if s["truth"] != "unknown"]
    report = {"schema_version": 1, "snapshot_sha256": sidecar["snapshot_sha256"],
              "motion_input_sha256": hashlib.sha256(canonical(sidecar)).hexdigest(),
              "evidence": {k: next(iter(clips.values()))[k] for k in ("kind", "stage", "split")},
              "acceptance_evaluated": False, "overall": _finish(matrix, lateral),
              "by_condition": [{"class_name": key[0], "lighting": key[1], "scenario": key[2],
                                "camera_motion": key[3], **_finish(*value)}
                               for key, value in sorted(groups.items())],
              "segments": {"total": len(segments), "known_truth": len(known_segments),
                           **{"with_" + name: sum(s[name] for s in known_segments)
                              for name in ("missed", "abstention", "wrong_movement", "wrong_lateral")}},
              "abstention_reasons": dict(sorted(reasons.items())),
              "camera_guard_violations": guard_violations,
              "warmup_frames": warmup, "ignored_references": ignored,
              "tracking": detection["tracking"],
              "detection": {k: detection["overall"][k] for k in ("tp", "fp", "fn")},
              "limitations": ["Apparent image motion only; no distance, TTC, risk or physical safety",
                              "Synthetic fixtures do not measure real model or tracking quality",
                              "Camera context, timing, segmentation and human labels require independent review",
                              "Samples are object/frame observations; segments are not independent sources",
                              "Frame-weighted rates are not segment-level or dataset acceptance",
                              "Known motion accuracy ignores lateral direction; inspect its separate metric",
                              "No final acceptance thresholds, camera compensation or participant validation"]}
    return report, review


def _private_output(path):
    workspace = Path.cwd().resolve()
    base = (workspace / "results").resolve()
    target = Path(path).resolve()
    require(base.is_relative_to(workspace) and target.is_relative_to(base), "private_output_location")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--motion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    args = parser.parse_args(argv)
    try:
        report, review = evaluate(load_input(args.snapshot), load_input(args.motion))
        outputs = {_private_output(args.output): report}
        if args.review:
            path = _private_output(args.review)
            require(path not in outputs, "duplicate_output")
            outputs[path] = {"schema_version": 1, "events": review}
        require(all(not p.exists() for p in outputs), "output_exists")
        for path, data in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                           "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("motion evaluation failed; inspect local inputs and output locations", file=sys.stderr)
        return 2
    print(json.dumps({"known_truth": report["overall"]["known_truth"],
                      "correct": report["overall"]["correct"], "acceptance_evaluated": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
