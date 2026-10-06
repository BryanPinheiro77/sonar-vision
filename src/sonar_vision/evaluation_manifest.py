"""Read-only metadata checks for issue #7; never reads or publishes videos."""
import argparse
from datetime import date
import json
import math
from pathlib import Path
import re

CLASSES = {"person", "car", "motorcycle", "bus", "bicycle", "chair",
           "dining_table", "dog", "stairs"}
SCENARIOS = {"approach", "recede", "lateral_crossing", "occlusion",
             "multiple_targets", "stairs_up", "stairs_down", "negative"}
LIGHTING = {"good", "low", "public_night"}
FIELDS = {"clip_id", "source_group_id", "kind", "stage", "split", "recorded_on",
          "camera", "width", "height", "fps", "duration_s", "scenario", "classes",
          "lighting", "lux", "distance_start_m", "distance_end_m",
          "measurement_method", "procedure_id", "sha256", "permission_reference",
          "ethics_reference", "annotation_reference"}


def _require(condition, location):
    if not condition:
        # Only structural location is reported, never values/personal paths.
        raise ValueError("invalid metadata: " + location)


def _number(value, *, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _token(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None


def _reference(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 256


def validate_manifest(manifest):
    _require(isinstance(manifest, dict) and set(manifest) == {
        "schema_version", "approval", "clips"}, "manifest")
    _require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
             "schema_version")
    approval = manifest["approval"]
    _require(isinstance(approval, dict) and set(approval) == {
        "status", "reference", "parameters_reference"}, "approval")
    _require(approval["status"] in ("pending", "approved"), "approval.status")
    for key in ("reference", "parameters_reference"):
        _require(approval[key] is None or _reference(approval[key]), "approval." + key)
        if approval["status"] == "approved":
            _require(_reference(approval[key]), "approval." + key)
    clips = manifest["clips"]
    _require(isinstance(clips, list), "clips")
    seen_ids, group_splits, hash_splits = set(), {}, {}
    recorded_classes, recorded_scenarios, recorded_lighting = set(), set(), set()
    counts = {"recorded": 0, "synthetic": 0}
    for index, clip in enumerate(clips):
        loc = f"clips[{index}]"
        _require(isinstance(clip, dict) and set(clip) == FIELDS, loc)
        for key in ("clip_id", "source_group_id", "procedure_id"):
            _require(_token(clip[key]), loc + "." + key)
        _require(clip["clip_id"] not in seen_ids, loc + ".clip_id")
        seen_ids.add(clip["clip_id"])
        _require(clip["kind"] in ("recorded", "synthetic"), loc + ".kind")
        _require(clip["stage"] in ("exploratory", "controlled", "integrated"), loc + ".stage")
        _require(clip["split"] in ("exploration", "tuning", "test", "demo", "synthetic"), loc + ".split")
        if clip["stage"] == "exploratory":
            _require(clip["split"] in ("exploration", "synthetic"), loc + ".split")
        if clip["stage"] == "integrated":
            _require(clip["split"] in ("demo", "test"), loc + ".split")
        for key in ("width", "height"):
            _require(type(clip[key]) is int and clip[key] > 0, loc + "." + key)
        for key in ("fps", "duration_s"):
            _require(_number(clip[key], positive=True), loc + "." + key)
        for key in ("lux", "distance_start_m", "distance_end_m"):
            _require(clip[key] is None or _number(clip[key]), loc + "." + key)
        _require(_reference(clip["measurement_method"]), loc + ".measurement_method")
        _require(isinstance(clip["scenario"], str) and clip["scenario"] in SCENARIOS, loc + ".scenario")
        _require(isinstance(clip["lighting"], str) and clip["lighting"] in LIGHTING, loc + ".lighting")
        classes = clip["classes"]
        _require(isinstance(classes, list) and all(isinstance(c, str) and c in CLASSES for c in classes),
                 loc + ".classes")
        _require(len(classes) == len(set(classes)), loc + ".classes")
        _require(bool(classes) or clip["scenario"] == "negative", loc + ".classes")
        if clip["scenario"] in ("stairs_up", "stairs_down"):
            _require("stairs" in classes, loc + ".classes")
        for key in ("permission_reference", "ethics_reference", "annotation_reference"):
            _require(clip[key] is None or _reference(clip[key]), loc + "." + key)
        digest = clip["sha256"]
        _require(digest is None or (isinstance(digest, str) and
                                   re.fullmatch(r"[0-9a-f]{64}", digest) is not None),
                 loc + ".sha256")
        if clip["kind"] == "synthetic":
            _require(clip["split"] == "synthetic" and clip["stage"] == "controlled", loc + ".split")
            _require(clip["recorded_on"] is None and clip["camera"] is None and digest is None,
                     loc + ".synthetic")
        else:
            _require(clip["split"] != "synthetic", loc + ".split")
            _require(isinstance(clip["recorded_on"], str) and
                     re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", clip["recorded_on"]) is not None,
                     loc + ".recorded_on")
            try:
                date.fromisoformat(clip["recorded_on"])
            except ValueError:
                raise ValueError("invalid metadata: " + loc + ".recorded_on") from None
            _require(_reference(clip["camera"]) and digest is not None, loc + ".recording")
            for key in ("permission_reference", "ethics_reference"):
                _require(_reference(clip[key]), loc + "." + key)
            if clip["split"] == "test":
                _require(clip["stage"] != "exploratory" and
                         _reference(clip["annotation_reference"]), loc + ".test")
            recorded_classes.update(classes)
            recorded_scenarios.add(clip["scenario"])
            recorded_lighting.add(clip["lighting"])
        split = clip["split"]
        if split in ("exploration", "tuning", "test"):
            partition = "test" if split == "test" else "development"
            for mapping, key in ((group_splits, clip["source_group_id"]),
                                 (hash_splits, digest)):
                previous = mapping.get(key)
                _require(previous is None or previous == partition, loc + ".split_leakage")
                mapping[key] = partition
        counts[clip["kind"]] += 1
    return {"metadata_valid": True, "approval_status": approval["status"],
            "counts": counts,
            "missing_recorded_classes": sorted(CLASSES - recorded_classes),
            "missing_recorded_scenarios": sorted(SCENARIOS - recorded_scenarios),
            "missing_recorded_lighting": sorted(LIGHTING - recorded_lighting),
            "limitations": ["Structure only; approvals/references and media not verified",
                            "Marginal coverage only, not class/condition sample adequacy",
                            "Synthetic metadata is not collected video or accuracy evidence"]}


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def load_manifest(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        manifest = json.load(stream, object_pairs_hook=_unique_keys)
    return validate_manifest(manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        report = load_manifest(args.manifest)
    except (OSError, ValueError, TypeError):
        parser.exit(2, "Manifest invalid or unreadable; check structure and references locally.\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
