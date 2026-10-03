"""Offline annotated detection/latency evaluation for #33; no safety inference."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from .benchmark import summarize
from .core import CLASSES, Result
from .evaluation_manifest import validate_manifest

MAX_INPUT = 32 * 1024 * 1024
MAX_FRAMES = 10000
MAX_OBJECTS = 100
TOKEN = re.compile(r"[A-Za-z0-9_.-]{1,128}")
STATUSES = ("ok", "timeout", "discarded", "decode_error", "warmup")
SCOPES = ("processing", "capture_to_response", "capture_to_audio", "sensor_to_tactile")
GT_FIELDS = {"reference_id", "class_name", "box", "visible", "stair_direction"}
PRED_FIELDS = {"track_id", "class_name", "box", "confidence", "stair_direction"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def fields(value, expected, reason):
    require(isinstance(value, dict) and set(value) == expected, reason)


def token(value):
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def number(value, low=0, high=float("inf")):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def integer(value, low=0, high=2**53 - 1):
    return type(value) is int and low <= value <= high


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def load_input(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_INPUT + 1)
    require(len(data) <= MAX_INPUT, "input_too_large")
    try:
        return json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid_json") from exc


def validate_input(data):
    fields(data, {"schema_version", "run", "dataset_manifest", "frames"}, "input_fields")
    require(type(data["schema_version"]) is int and data["schema_version"] == 1, "input_version")
    validate_manifest(data["dataset_manifest"])
    clips = data["dataset_manifest"]["clips"]
    require(1 <= len(clips) <= 256, "clip_count")
    require(len({(c["kind"], c["stage"], c["split"]) for c in clips}) == 1, "mixed_evidence")
    clip_map = {c["clip_id"]: c for c in clips}
    run = data["run"]
    fields(run, {"run_id", "code_version", "model", "configuration", "protocol", "latency_scope",
                 "latency_clock", "warmup_excluded", "model_load_included", "elapsed_ms"}, "run_fields")
    require(token(run["run_id"]) and token(run["code_version"]), "run_version")
    fields(run["model"], {"name", "version", "sha256"}, "model_fields")
    require(token(run["model"]["name"]) and token(run["model"]["version"]), "model_version")
    model_hash = run["model"]["sha256"]
    require(model_hash is None or (isinstance(model_hash, str) and
                                  re.fullmatch(r"[a-f0-9]{64}", model_hash)), "model_hash")
    if clips[0]["kind"] == "recorded":
        require(model_hash is not None, "recorded_model_hash")
        require(all(token(c["annotation_reference"]) for c in clips), "annotation_required")
    config = run["configuration"]
    fields(config, {"detector_confidence", "image_size", "device", "tracker_version"}, "configuration_fields")
    require(number(config["detector_confidence"], 0, 1) and integer(config["image_size"], 1, 4096)
            and config["device"] in ("cpu", "cuda", "mps") and token(config["tracker_version"]), "configuration")
    protocol = run["protocol"]
    fields(protocol, {"iou_threshold", "association", "ignore_policy", "max_gap_frames",
                      "minimum_sources_per_group", "approval_reference"}, "protocol_fields")
    require(number(protocol["iou_threshold"], 0, 1) and protocol["iou_threshold"] > 0
            and protocol["association"] == "max_cardinality_then_iou"
            and protocol["ignore_policy"] == "exclude_invisible_overlap"
            and integer(protocol["max_gap_frames"], 0, 10000)
            and integer(protocol["minimum_sources_per_group"], 1, 10000)
            and (protocol["approval_reference"] is None or token(protocol["approval_reference"])), "protocol")
    require(run["latency_scope"] in SCOPES and run["latency_clock"] == "single_monotonic_intervals"
            and run["warmup_excluded"] is True and type(run["model_load_included"]) is bool, "latency_contract")
    require(run["elapsed_ms"] is None or (number(run["elapsed_ms"]) and run["elapsed_ms"] > 0), "elapsed_ms")
    frames = data["frames"]
    require(isinstance(frames, list) and 1 <= len(frames) <= MAX_FRAMES, "frame_count")
    last, classes_by_id = {}, {}
    for frame in frames:
        fields(frame, {"clip_id", "frame_index", "tracker_epoch", "status", "latency_ms",
                       "ground_truth", "predictions"}, "frame_fields")
        require(token(frame["clip_id"]) and frame["clip_id"] in clip_map
                and integer(frame["frame_index"]) and token(frame["tracker_epoch"])
                and frame["status"] in STATUSES, "frame_metadata")
        clip = clip_map[frame["clip_id"]]
        require(frame["frame_index"] > last.get(frame["clip_id"], -1), "frame_order")
        last[frame["clip_id"]] = frame["frame_index"]
        require(frame["latency_ms"] is None or number(frame["latency_ms"]), "latency_sample")
        if frame["status"] in ("ok", "timeout", "discarded"):
            require(frame["latency_ms"] is not None, "missing_latency")
        for name, expected in (("ground_truth", GT_FIELDS), ("predictions", PRED_FIELDS)):
            objects = frame[name]
            require(isinstance(objects, list) and len(objects) <= MAX_OBJECTS, "object_count")
            ids = set()
            for obj in objects:
                fields(obj, expected, "object_fields")
                require(isinstance(obj["class_name"], str) and obj["class_name"] in CLASSES, "class_name")
                box = obj["box"]
                require(isinstance(box, list) and len(box) == 4 and all(number(v, 0, 1) for v in box)
                        and box[0] < box[2] and box[1] < box[3]
                        and (box[2] - box[0]) * (box[3] - box[1]) > 0, "normalized_box")
                if obj["class_name"] == "stairs":
                    require(obj["stair_direction"] in ("up", "down", "unknown"), "stairs_direction")
                else:
                    require(obj["stair_direction"] is None, "nonstairs_direction")
                ident = obj["reference_id"] if name == "ground_truth" else obj["track_id"]
                require(token(ident) or (name == "predictions" and ident is None), "identity")
                if ident is not None:
                    require(ident not in ids, "duplicate_identity")
                    ids.add(ident)
                if name == "ground_truth":
                    require(type(obj["visible"]) is bool and obj["class_name"] in clip["classes"], "reference_metadata")
                    key = (clip["clip_id"], ident)
                    require(classes_by_id.get(key, obj["class_name"]) == obj["class_name"], "reference_class_changed")
                    classes_by_id[key] = obj["class_name"]
                else:
                    require(number(obj["confidence"], 0, 1), "confidence")
        if frame["status"] in ("timeout", "discarded", "decode_error"):
            require(not frame["predictions"], "failure_predictions")
    return clip_map


def iou(a, b):
    overlap = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - overlap
    return overlap / union


def optimal_pairs(weights):
    """Rectangular Hungarian assignment with dummy columns; O(rows^2*columns).

    Weight >=0 is eligible; -1 is forbidden. Maximize cardinality first, then
    sum of IoUs. Input order resolves exact equal-cost ties deterministically.
    """
    rows = len(weights)
    if not rows or not weights[0]:
        return []
    cols = len(weights[0])
    require(all(len(row) == cols for row in weights), "ragged_assignment")
    bonus = min(rows, cols) + 1
    costs = [[-(bonus + value) if value >= 0 else 1 for value in row] + [0] * rows
             for row in weights]
    width = cols + rows
    u, v, owner, way = [0.0] * (rows + 1), [0.0] * (width + 1), [0] * (width + 1), [0] * (width + 1)
    for row in range(1, rows + 1):
        owner[0] = row
        column = 0
        best, used = [float("inf")] * (width + 1), [False] * (width + 1)
        while True:
            used[column] = True
            current = owner[column]
            delta, following = float("inf"), 0
            for j in range(1, width + 1):
                if not used[j]:
                    candidate = costs[current - 1][j - 1] - u[current] - v[j]
                    if candidate < best[j]:
                        best[j], way[j] = candidate, column
                    if best[j] < delta:
                        delta, following = best[j], j
            for j in range(width + 1):
                if used[j]:
                    u[owner[j]] += delta
                    v[j] -= delta
                else:
                    best[j] -= delta
            column = following
            if owner[column] == 0:
                break
        while True:
            previous = way[column]
            owner[column] = owner[previous]
            column = previous
            if column == 0:
                break
    return sorted((owner[j] - 1, j - 1) for j in range(1, cols + 1)
                  if owner[j] and weights[owner[j] - 1][j - 1] >= 0)


def match(references, predictions, threshold, *, class_aware=True):
    matrix = []
    for ref in references:
        row = []
        for pred in predictions:
            overlap = iou(ref["box"], pred["box"])
            valid = overlap >= threshold and (not class_aware or ref["class_name"] == pred["class_name"])
            row.append(overlap if valid else -1)
        matrix.append(row)
    return optimal_pairs(matrix)


def ratio(a, b):
    if not b:
        return None
    value = a / b
    require(math.isfinite(value), "nonfinite_metric")
    return value


def bucket():
    return {"tp": 0, "fp": 0, "fn": 0, "ignored_references": 0, "ignored_predictions": 0,
            "filtered_predictions": 0, "sources": set(), "frames": set(), "tracking": Counter()}


def finish(value, minimum):
    result = {k: v for k, v in value.items() if k not in ("sources", "frames", "tracking")}
    result.update(precision=ratio(value["tp"], value["tp"] + value["fp"]),
                  recall=ratio(value["tp"], value["tp"] + value["fn"]),
                  f1=ratio(2 * value["tp"], 2 * value["tp"] + value["fp"] + value["fn"]),
                  evaluated_frames=len(value["frames"]), independent_sources=len(value["sources"]),
                  insufficient_sample=len(value["sources"]) < minimum,
                  tracking=dict(sorted(value["tracking"].items())))
    return result


def evaluate(data):
    clips = validate_input(data)
    run, protocol = data["run"], data["run"]["protocol"]
    overall, by_class, groups = bucket(), {cls: bucket() for cls in sorted(CLASSES)}, {}
    latencies, statuses, group_latency = [], Counter(), {}
    review, tracking = [], Counter()
    histories, owners, epochs = {}, {}, {}
    confusion = Counter()
    stairs = {truth: {response: 0 for response in ("up", "down", "unknown", "missed")}
              for truth in ("up", "down")}
    unknown_stair_truth = 0

    def group_key(clip, cls):
        return (cls, clip["lighting"], clip["scenario"])

    def targets(clip, cls):
        key = group_key(clip, cls)
        return (overall, by_class[cls], groups.setdefault(key, bucket()))

    def record(clip, frame, cls, metric):
        for value in targets(clip, cls):
            value[metric] += 1
            value["sources"].add(clip["source_group_id"])
            value["frames"].add((clip["clip_id"], frame["frame_index"]))

    def event(clip, frame, kind, ref=None, previous=None, current=None, previous_reference=None):
        tracking[kind] += 1
        if ref:
            for value in targets(clip, ref["class_name"]):
                value["tracking"][kind] += 1
        review.append({"clip_id": clip["clip_id"], "frame_index": frame["frame_index"],
                       "event": kind, "reference_id": ref["reference_id"] if ref else None,
                       "previous_track": previous, "current_track": current,
                       "previous_reference_id": previous_reference})

    for frame in data["frames"]:
        clip = clips[frame["clip_id"]]
        clip_id, index, epoch = clip["clip_id"], frame["frame_index"], frame["tracker_epoch"]
        statuses[frame["status"]] += 1
        if frame["status"] == "warmup":
            histories = {k: v for k, v in histories.items() if k[0] != clip_id}
            owners = {k: v for k, v in owners.items() if k[0] != clip_id}
            epochs.pop(clip_id, None)
            continue
        if clip_id in epochs and epochs[clip_id] != epoch:
            event(clip, frame, "epoch_reset")
            histories = {k: v for k, v in histories.items() if k[0] != clip_id}
            owners = {k: v for k, v in owners.items() if k[0] != clip_id}
        epochs[clip_id] = epoch
        # Declared class/condition cells include negative frames, not only detections.
        for cls in set(clip["classes"]) | {p["class_name"] for p in frame["predictions"]}:
            for value in targets(clip, cls):
                value["sources"].add(clip["source_group_id"])
                value["frames"].add((clip_id, index))
        overall["sources"].add(clip["source_group_id"])
        overall["frames"].add((clip_id, index))
        latency_key = (clip["lighting"], clip["scenario"])
        latency_cell = group_latency.setdefault(latency_key, {"samples": [], "statuses": Counter()})
        latency_cell["statuses"][frame["status"]] += 1
        if frame["latency_ms"] is not None:
            latencies.append(frame["latency_ms"])
            latency_cell["samples"].append(frame["latency_ms"])
        references = [r for r in frame["ground_truth"] if r["visible"]]
        ignored = [r for r in frame["ground_truth"] if not r["visible"]]
        for ref in ignored:
            record(clip, frame, ref["class_name"], "ignored_references")
            histories.pop((clip_id, ref["reference_id"]), None)
        predictions = []
        for pred in frame["predictions"]:
            if pred["confidence"] < run["configuration"]["detector_confidence"]:
                record(clip, frame, pred["class_name"], "filtered_predictions")
            else:
                predictions.append(pred)
        pairs = match(references, predictions, protocol["iou_threshold"])
        matched_ref, matched_pred = {r for r, _ in pairs}, {p for _, p in pairs}
        ignored_pred = set()
        for p, pred in enumerate(predictions):
            if p not in matched_pred and any(r["class_name"] == pred["class_name"]
                    and iou(r["box"], pred["box"]) >= protocol["iou_threshold"] for r in ignored):
                ignored_pred.add(p)
                record(clip, frame, pred["class_name"], "ignored_predictions")
        for r, ref in enumerate(references):
            record(clip, frame, ref["class_name"], "tp" if r in matched_ref else "fn")
        for p, pred in enumerate(predictions):
            if p not in matched_pred and p not in ignored_pred:
                record(clip, frame, pred["class_name"], "fp")
        unmatched_refs = [references[r] for r in range(len(references)) if r not in matched_ref]
        unmatched_preds = [predictions[p] for p in range(len(predictions))
                           if p not in matched_pred and p not in ignored_pred]
        for r, p in match(unmatched_refs, unmatched_preds, protocol["iou_threshold"], class_aware=False):
            confusion[(unmatched_refs[r]["class_name"], unmatched_preds[p]["class_name"])] += 1
        assigned = {r: predictions[p] for r, p in pairs}
        present_ids = {r["reference_id"] for r in references}
        histories = {k: v for k, v in histories.items()
                     if k[0] != clip_id or k[1] in present_ids}
        owners = {k: v for k, v in owners.items() if k[0] != clip_id or v[0] in present_ids}
        for r, ref in enumerate(references):
            pred = assigned.get(r)
            if ref["class_name"] == "stairs":
                if ref["stair_direction"] == "unknown":
                    unknown_stair_truth += 1
                else:
                    response = pred["stair_direction"] if pred else "missed"
                    stairs[ref["stair_direction"]][response] += 1
            key = (clip_id, ref["reference_id"])
            previous = histories.get(key)
            if previous and index - previous["last_match_frame"] > protocol["max_gap_frames"] + 1:
                event(clip, frame, "continuity_break", ref)
                previous = None
                histories.pop(key, None)
            current = pred["track_id"] if pred else None
            if current is None:
                event(clip, frame, "detection_loss" if pred is None else "unassigned", ref,
                      previous["track"] if previous else None)
                if previous:
                    previous["lost"] = True
                continue
            if previous:
                if previous["track"] != current:
                    event(clip, frame, "id_switch", ref, previous["track"], current)
                if previous["lost"]:
                    event(clip, frame, "fragmentation", ref, previous["track"], current)
            owner_key = (clip_id, epoch, current)
            owner = owners.get(owner_key)
            if owner and index - owner[1] <= protocol["max_gap_frames"] + 1 and owner[0] != ref["reference_id"]:
                event(clip, frame, "identity_transfer", ref, current=current, previous_reference=owner[0])
            owners[owner_key] = (ref["reference_id"], index)
            histories[key] = {"track": current, "last_match_frame": index, "lost": False}
        owners = {k: v for k, v in owners.items()
                  if k[0] != clip_id or index - v[1] <= protocol["max_gap_frames"] + 1}

    minimum = protocol["minimum_sources_per_group"]
    known = sum(sum(row.values()) for row in stairs.values())
    detected = sum(row[k] for row in stairs.values() for k in ("up", "down", "unknown"))
    correct = stairs["up"]["up"] + stairs["down"]["down"]
    answered = sum(row[k] for row in stairs.values() for k in ("up", "down"))
    report = {
        "schema_version": 1, "input_sha256": hashlib.sha256(canonical(data)).hexdigest(),
        "run": deepcopy(run), "evidence": {k: clips[next(iter(clips))][k] for k in ("kind", "stage", "split")},
        "acceptance_evaluated": False, "registered_clips": len(clips),
        "clips_without_frames": len(set(clips) - {f["clip_id"] for f in data["frames"]}),
        "overall": finish(overall, minimum),
        "by_class": {cls: finish(value, minimum) for cls, value in by_class.items()},
        "by_condition": [{"class_name": key[0], "lighting": key[1], "scenario": key[2],
                          **finish(value, minimum)} for key, value in sorted(groups.items())],
        "latency": summarize(latencies) if latencies else None,
        "latency_by_condition": [{"lighting": key[0], "scenario": key[1],
                                 "latency": summarize(value["samples"]) if value["samples"] else None,
                                 "statuses": dict(sorted(value["statuses"].items()))}
                                for key, value in sorted(group_latency.items())],
        "statuses": dict(sorted(statuses.items())),
        "latency_by_status": {status: summarize([f["latency_ms"] for f in data["frames"]
                             if f["status"] == status and f["latency_ms"] is not None])
                             if any(f["status"] == status and f["latency_ms"] is not None for f in data["frames"])
                             else None for status in STATUSES if status != "warmup"},
        "effective_fps": ratio(statuses["ok"] * 1000, run["elapsed_ms"]) if run["elapsed_ms"] else None,
        "tracking": dict(sorted(tracking.items())),
        "class_confusions": [{"truth": key[0], "prediction": key[1], "count": value}
                            for key, value in sorted(confusion.items())],
        "stairs": {"matrix": stairs, "unknown_truth": unknown_stair_truth, "known_truth": known,
                   "detected": detected, "answered": answered,
                   "abstentions": sum(row["unknown"] for row in stairs.values()),
                   "correct": correct, "accuracy_all_known": ratio(correct, known),
                   "answer_coverage_all_known": ratio(answered, known),
                   "accuracy_when_answered": ratio(correct, answered)},
        "limitations": ["Synthetic data is not model performance or physical validation",
                        "No AP/mAP, IDF1/HOTA, true person count, risk, distance or safety metric",
                        "Matching/ignore/continuity rules require protocol review before final evaluation",
                        "Source counts do not prove independent sampling, permissions or annotation quality",
                        "Confidence is a detector score, not measured accuracy or safety probability",
                        "Latency pools statuses; inspect failures and per-condition results"],
    }
    return report, review


def frame_from_result(clip_id, frame_index, result, ground_truth, *, latency_ms):
    """Internal #21 snapshot, not new wire fields; caller aligns annotations."""
    require(isinstance(result, Result), "vision_result")
    return {"clip_id": clip_id, "frame_index": frame_index,
            "tracker_epoch": result.tracker_epoch, "status": "ok",
            "latency_ms": latency_ms, "ground_truth": deepcopy(ground_truth),
            "predictions": [{"track_id": detection.track_id, "class_name": detection.class_name,
                             "box": list(detection.box), "confidence": detection.confidence,
                             "stair_direction": "unknown" if detection.class_name == "stairs" else None}
                            for detection in result.detections]}


def comparison(current_data, baseline_data):
    """Compare only matching annotated captures and measurement conventions."""
    current, _ = evaluate(current_data)
    baseline, _ = evaluate(baseline_data)

    def signature(data):
        return { "manifest": data["dataset_manifest"],
                 "references": [{k: f[k] for k in ("clip_id", "frame_index", "ground_truth")}
                                for f in data["frames"] if f["status"] != "warmup"],
                 "protocol": data["run"]["protocol"],
                 "measurement": {k: data["run"][k] for k in ("latency_scope", "latency_clock",
                                  "warmup_excluded", "model_load_included")}}
    compatible = signature(current_data) == signature(baseline_data)
    return {"comparable": compatible, "baseline_sha256": baseline["input_sha256"],
            "overall_delta": {k: current["overall"][k] - baseline["overall"][k] for k in ("tp", "fp", "fn")}
                             if compatible else None,
            "latency_mean_delta_ms": (current["latency"]["mean_ms"] - baseline["latency"]["mean_ms"]
                                     if compatible and current["latency"] and baseline["latency"] else None),
            "reason": "same_annotated_captures_and_protocol" if compatible else "different_references_or_protocol"}


def markdown_summary(report):
    """Aggregates only: no clip IDs, boxes, identities, config secrets or free text."""
    lines = ["# Avaliação visual e latência — #33", "",
             "Síntese agregada; não valida segurança, licença ou qualidade das anotações.", "",
             f"Evidência: {report['evidence']['kind']} / {report['evidence']['stage']} / {report['evidence']['split']}.",
             f"Clips registrados: {report['registered_clips']}; sem frames: {report['clips_without_frames']}.",
             "Confiança do detector não é qualidade medida. Aceitação experimental não avaliada.", "",
             "| Classe | TP | FP | FN | Precision | Recall | Fontes | Amostra insuficiente |",
             "|---|---:|---:|---:|---:|---:|---:|---|"]
    def display(value):
        return "N/A" if value is None else f"{value:.4f}"
    for cls, value in report["by_class"].items():
        lines.append(f"| {cls} | {value['tp']} | {value['fp']} | {value['fn']} | "
                     f"{display(value['precision'])} | {display(value['recall'])} | "
                     f"{value['independent_sources']} | {'sim' if value['insufficient_sample'] else 'não'} |")
    lines += ["", "| Classe | Iluminação | Cenário | TP | FP | FN | Fontes |",
              "|---|---|---|---:|---:|---:|---:|"]
    for row in report["by_condition"]:
        lines.append(f"| {row['class_name']} | {row['lighting']} | {row['scenario']} | "
                     f"{row['tp']} | {row['fp']} | {row['fn']} | {row['independent_sources']} |")
    lines += ["", f"Escopo de latência: {report['run']['latency_scope']}; intervalos monotônicos únicos.",
              "| Iluminação | Cenário | N | Média ms | P50 ms | P95 ms |",
              "|---|---|---:|---:|---:|---:|"]
    for row in report["latency_by_condition"]:
        value = row["latency"]
        lines.append(f"| {row['lighting']} | {row['scenario']} | {value['samples'] if value else 0} | "
                     f"{display(value['mean_ms'] if value else None)} | "
                     f"{display(value['p50_ms'] if value else None)} | {display(value['p95_ms'] if value else None)} |")
    lines += ["", "Estados: " + json.dumps(report["statuses"], sort_keys=True),
              "Diagnósticos de tracking: " + json.dumps(report["tracking"], sort_keys=True), "",
              "| Escada: verdade | Resposta up | Resposta down | Abstenção | Não detectada |",
              "|---|---:|---:|---:|---:|"]
    for truth, row in report["stairs"]["matrix"].items():
        lines.append(f"| {truth} | {row['up']} | {row['down']} | {row['unknown']} | {row['missed']} |")
    lines += ["", "Confusões de classe: " + json.dumps(report["class_confusions"], sort_keys=True),
              "", "Parâmetros de associação/continuidade e mínimos de amostra são propostas a revisar na #7.",
              "Resultados brutos e eventos por frame permanecem em armazenamento local restrito.",
              "Nenhuma conclusão de caminho livre, contagem real de pessoas ou segurança física."]
    return "\n".join(lines) + "\n"


def private_output(path):
    target = Path(path).resolve()
    require(target.is_relative_to((Path.cwd() / "results").resolve()), "private_output_location")
    return target


def write_outputs(report, review, output, *, review_path=None, summary_path=None):
    outputs = {private_output(output): (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")}
    if review_path:
        target = private_output(review_path)
        require(target not in outputs, "duplicate_output")
        outputs[target] = json.dumps({"schema_version": 1, "events": review},
                                    ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if summary_path:
        target = Path(summary_path).resolve()
        require(target.is_relative_to((Path.cwd() / "docs" / "experiments").resolve()), "summary_output_location")
        require(target not in outputs, "duplicate_output")
        outputs[target] = markdown_summary(report)
    require(all(not target.exists() for target in outputs), "output_exists")
    for target, content in outputs.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_input(args.input)
        report, review = evaluate(data)
        if args.baseline:
            report["comparison"] = comparison(data, load_input(args.baseline))
        write_outputs(report, review, args.output, review_path=args.review, summary_path=args.summary)
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        parser.exit(2, "Evaluation invalid or output unavailable; inspect inputs and permissions locally.\n")
    print(json.dumps({"evaluated": True, "frames": report["overall"]["evaluated_frames"],
                      "tp": report["overall"]["tp"], "fp": report["overall"]["fp"],
                      "fn": report["overall"]["fn"], "acceptance_evaluated": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
