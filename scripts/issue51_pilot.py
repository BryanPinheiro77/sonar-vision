"""Approved #51 offline pilot. Private manifest/data/output; no production changes."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
from time import perf_counter, process_time
from unittest.mock import patch

BASELINE_SHA = "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36"
ROLES = {
    "development-office-original": "train",
    "cena-a-local-informado-pelo-autor": "val",
    "cena-b-local-informado-pelo-autor": "evaluation",
}
PARAMETERS = dict(
    epochs=20,
    imgsz=640,
    batch=4,
    seed=42,
    device="cpu",
    workers=0,
    optimizer="AdamW",
    lr0=0.001,
    patience=20,
)


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def xywh(box):
    if (
        not isinstance(box, list)
        or len(box) != 4
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
    ):
        raise ValueError("invalid_box")
    x1, y1, x2, y2 = box
    if not 0 <= x1 < x2 <= 1 or not 0 <= y1 < y2 <= 1:
        raise ValueError("invalid_box")
    return (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def validated_records(manifest):
    """Validate before creating any output. Approval structure is not authentication."""
    root = manifest.parent.resolve()
    data = json.loads(manifest.read_text())
    for source, expected in data["source_annotation_hashes"].items():
        if digest(source) != expected:
            raise ValueError("reference_changed")
    frozen = data["frozen_development_reference"]
    if digest(root / frozen["path"]) != frozen["sha256"]:
        raise ValueError("reference_changed")
    expected_labels = {}

    def signature(labels):
        return [
            (x["physical_class"], x.get("box", x.get("box_xyxy_normalized")))
            for x in labels
        ]

    for entry in json.loads((root / frozen["path"]).read_text())["records"]:
        expected_labels[entry["sample_id"]] = signature(entry["labels"])
    for source in data["source_annotation_hashes"]:
        reference = json.loads(Path(source).read_text())
        for clip in reference.get("clips", []):
            for frame in clip["frame_selection"]:
                name = f"{clip['clip_id']}-{frame['requested_timestamp_s']:02d}s"
                expected_labels[name] = signature(frame["annotations"])
    rows, names, groups, images, counts = [], set(), {}, {}, Counter()
    for entry in data["records"]:
        name = entry["sample_id"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]+", name)
            or name in names
        ):
            raise ValueError("invalid_sample_id")
        names.add(name)
        group = entry["group"]
        if group not in ROLES:
            raise ValueError("unexpected_group")
        role = ROLES[group]
        path = (root / entry["image"]).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() not in (
            ".png",
            ".jpg",
            ".jpeg",
        ):
            raise ValueError("invalid_image_path")
        if digest(path) != entry["image_sha256"]:
            raise ValueError("image_changed")
        groups.setdefault(group, set()).add(role)
        images.setdefault(entry["image_sha256"], set()).add(role)
        labels = []
        for label in entry["labels"]:
            if label.get("approval") != "approved by Bryan":
                raise ValueError("unapproved_label")
            physical = label["physical_class"]
            if physical not in ("chair", "table"):
                raise ValueError("unexpected_class")
            box = label.get("box", label.get("box_xyxy_normalized"))
            labels.append({"class_name": physical, "box": box})
            xywh(box)
        if not labels:
            raise ValueError("empty_labels_in_positive_pilot")
        if signature(entry["labels"]) != expected_labels.get(name):
            raise ValueError("labels_differ_from_frozen_reference")
        counts[(role, "captures")] += 1
        counts[(role, "labels")] += len(labels)
        rows.append(
            {
                "id": name,
                "group": group,
                "role": role,
                "source": path,
                "image_sha256": entry["image_sha256"],
                "labels": labels,
            }
        )
    if any(len(roles) != 1 for roles in (*groups.values(), *images.values())):
        raise ValueError("split_leakage")
    if counts != Counter(
        {
            ("train", "captures"): 9,
            ("train", "labels"): 32,
            ("val", "captures"): 4,
            ("val", "labels"): 8,
            ("evaluation", "captures"): 4,
            ("evaluation", "labels"): 8,
        }
    ):
        raise ValueError("unexpected_pilot_counts")
    return rows


def export(manifest, output):
    rows = validated_records(manifest)
    if output.exists():
        raise ValueError("output_exists")
    output.mkdir(parents=True)
    for row in rows:
        role, name = row["role"], row["id"]
        image = output / "images" / role / (name + row["source"].suffix.lower())
        label = output / "labels" / role / (name + ".txt")
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row["source"], image)
        lines = []
        for target in row["labels"]:
            values = xywh(target["box"])
            cls = 0 if target["class_name"] == "chair" else 1
            lines.append(str(cls) + " " + " ".join(f"{v:.10f}" for v in values))
        label.write_text("\n".join(lines) + "\n")
        row["image"] = str(image.relative_to(output))
        del row["source"]
    # Evaluation B deliberately absent from trainer configuration.
    config = {
        "path": str(output.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {0: "chair", 1: "table"},
    }
    (output / "data.yaml").write_text(json.dumps(config, indent=2) + "\n")
    (output / "export.json").write_text(
        json.dumps(
            {"reference_manifest_sha256": digest(manifest), "records": rows}, indent=2
        )
        + "\n"
    )
    return rows


def evaluate(weights, rows, dataset):
    import cv2
    from sonar_vision.ultralytics_backend import UltralyticsFactory
    from sonar_vision.benchmark import summarize
    from sonar_vision.evaluation import match, iou

    factory = UltralyticsFactory(weights)
    for _ in range(5):
        factory.warmup()
    timings, records, totals = [], [], Counter()
    for row in rows:
        if row["role"] != "evaluation":
            continue
        image = cv2.imread(str(dataset / row["image"]))
        if image is None or image.shape[:2] != (480, 270):
            raise ValueError("evaluation_decode_or_shape")
        start = perf_counter()
        result = factory._predict(image)
        elapsed = (perf_counter() - start) * 1000
        timings.append(elapsed)
        predictions, other = [], []
        for box in result.boxes.data.cpu().numpy():
            x1, y1, x2, y2, conf, cls = map(float, box)
            raw = result.names[int(cls)]
            physical = raw.lower().replace("_", " ")
            pred = {
                "raw_class": raw,
                "confidence": conf,
                "box": [
                    x1 / image.shape[1],
                    y1 / image.shape[0],
                    x2 / image.shape[1],
                    y2 / image.shape[0],
                ],
            }
            if physical in ("chair", "table", "dining table"):
                pred["class_name"] = "chair" if physical == "chair" else "table"
                predictions.append(pred)
            else:
                other.append(pred)
        pairs = match(row["labels"], predictions, 0.5)
        counts = Counter(
            {
                "chair_tp": sum(
                    row["labels"][r]["class_name"] == "chair" for r, p in pairs
                ),
                "table_tp": sum(
                    row["labels"][r]["class_name"] == "table" for r, p in pairs
                ),
                "unmatched_furniture_predictions": len(predictions) - len(pairs),
            }
        )
        totals.update(counts)
        records.append(
            {
                "id": row["id"],
                "input_pixels_sha256": sha256(image.tobytes()).hexdigest(),
                "counts": dict(counts),
                "predictions": predictions,
                "other_predictions": other,
                "pairs": [
                    [r, p, iou(row["labels"][r]["box"], predictions[p]["box"])]
                    for r, p in pairs
                ],
                "inference_ms": elapsed,
            }
        )
    return {
        "weights_sha256": digest(weights),
        "model": factory.metadata,
        "counts": dict(totals),
        "frames": records,
        "timing": summarize(timings),
        "warmup_frames_excluded": 5,
        "latency_scope": "detector only, four samples; no network or tracking",
        "prediction_input": "frozen JPEG 270x480",
    }


def run(manifest, weights, output):
    os.environ["YOLO_AUTOINSTALL"] = "false"
    os.environ["YOLO_OFFLINE"] = "true"
    if version("ultralytics") != "8.4.137" or digest(weights) != BASELINE_SHA:
        raise ValueError("unexpected_package_or_baseline")
    rows = export(manifest, output / "dataset")
    import cv2
    import torch
    from ultralytics import YOLO
    from sonar_vision.benchmark import resource

    for row in rows:
        if cv2.imread(str(output / "dataset" / row["image"])) is None:
            raise ValueError("image_decode")
    record = {
        "status": "running",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": digest(manifest),
        "baseline_sha256": digest(weights),
        "parameters_requested": PARAMETERS,
        "hardware": {
            "system": platform.system(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
        },
        "packages": {
            p: version(p)
            for p in ("ultralytics", "torch", "torchvision", "numpy", "opencv-python")
        },
        "production_changed": False,
        "failures": [],
    }
    report = output / "pilot.json"
    report.write_text(json.dumps(record, indent=2) + "\n")
    started, cpu_started = perf_counter(), process_time()
    try:
        model = YOLO(str(weights))
        best_epochs = []

        def selected_epoch(trainer):
            if trainer.fitness is not None and trainer.fitness == trainer.best_fitness:
                best_epochs.append(
                    {"epoch": trainer.epoch + 1, "fitness": float(trainer.fitness)}
                )

        model.add_callback("on_model_save", selected_epoch)
        # plots=False: font rendering is unused. Avoid the unconditional font download.
        with patch("ultralytics.data.utils.check_font", return_value=None):
            model.train(
                data=str(output / "dataset" / "data.yaml"),
                project=str(output),
                name="train",
                exist_ok=False,
                plots=False,
                **PARAMETERS,
            )
        best = output / "train" / "weights" / "best.pt"
        if not best.is_file() or not best_epochs:
            raise ValueError("missing_best_checkpoint")
        selection = {
            **best_epochs[-1],
            "weights_sha256": digest(best),
            "selected_by": "trainer fitness on validation A only",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "results_csv_sha256": digest(output / "train" / "results.csv"),
        }
        (output / "checkpoint-frozen.json").write_text(
            json.dumps(selection, indent=2) + "\n"
        )
        record["checkpoint"] = selection
        # This file exists before any candidate prediction on B.
        record["training_wall_s"] = perf_counter() - started
        record["training_process_cpu_s"] = process_time() - cpu_started
        record["baseline"] = evaluate(weights, rows, output / "dataset")
        record["candidate"] = evaluate(best, rows, output / "dataset")
        if digest(best) != selection["weights_sha256"]:
            raise ValueError("checkpoint_changed")
        counts = record["candidate"]["counts"]
        record.update(counts)
        record["target_achieved"] = (
            counts["chair_tp"] >= 3
            and counts["table_tp"] >= 2
            and counts["unmatched_furniture_predictions"] <= 1
        )
        record["status"] = "completed"
    except Exception as error:
        record["status"] = "failed"
        record["failures"].append(type(error).__name__)
        record["target_achieved"] = None
        raise
    finally:
        record["wall_s"] = perf_counter() - started
        record["process_cpu_s"] = process_time() - cpu_started
        record["mean_cpu_percent_one_core"] = (
            record["process_cpu_s"] / record["wall_s"] * 100
        )
        record["cpu_capacity_denominator"] = os.cpu_count() or 1
        record["mean_cpu_percent_capacity"] = (
            record["mean_cpu_percent_one_core"] / record["cpu_capacity_denominator"]
        )
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None
        record["peak_rss_bytes_since_process_start"] = (
            None
            if peak is None
            else peak
            if platform.system() == "Darwin"
            else peak * 1024
        )
        record["peak_includes_training_and_model_initialization"] = True
        record["torch_threads"] = {
            "intraop": torch.get_num_threads(),
            "interop": torch.get_num_interop_threads(),
        }
        report.write_text(json.dumps(record, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": record["status"],
                "counts": record["candidate"]["counts"],
                "target_achieved": record["target_achieved"],
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; one new directory for the approved pilot")
    run(args.manifest, args.weights, args.output.resolve())


if __name__ == "__main__":
    main()
