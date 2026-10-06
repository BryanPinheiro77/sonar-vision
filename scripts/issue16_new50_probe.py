"""Offline direction probe on Bryan's 50 local scenes, split by location.

Uses the unchanged OIV7 detector's precomputed boxes and frozen features.
This research script does not change the visual service or safety behavior.
"""

import argparse
import json
from pathlib import Path

from ultralytics import YOLO

from issue16_direction_probe import (classify, crop, embedding, file_hash,
                                     fit_centroids, read_image)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--specialist", type=Path,
                        help="optional one-class local pilot for fallback comparison")
    parser.add_argument("--additional-training-manifest", type=Path,
                        help="optional local manifest of extra, site-independent stair crops")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.original.is_file() or args.original.suffix != ".pt":
        parser.error("provide trusted local OIV7 .pt weights")
    if args.specialist and (not args.specialist.is_file() or args.specialist.suffix != ".pt"):
        parser.error("provide trusted local specialist .pt weights")
    manifest = json.loads(args.manifest.read_text())
    baseline = json.loads(args.baseline.read_text())
    rows = manifest["rows"]
    baseline_by_id = {row["id"]: row for row in baseline["rows"]}
    if len(rows) != 50 or len(baseline_by_id) != 50:
        raise ValueError("expected exactly 50 catalogued scenes")
    if {row["scene_id"] for row in rows if row["split"] == "train"} & {
            row["scene_id"] for row in rows if row["split"] == "test"}:
        raise ValueError("train/test location overlap")
    model = YOLO(str(args.original))
    specialist = YOLO(str(args.specialist)) if args.specialist else None
    if len(model.names) != 601 or "Stairs" not in model.names.values():
        raise ValueError("expected OIV7 original with 601 classes")
    if specialist and set(specialist.names.values()) != {"stairs"}:
        raise ValueError("specialist must detect one class named stairs")

    train = []
    for row in rows:
        previous = baseline_by_id[row["id"]]
        if row["sha256"] != previous["sha256"] or file_hash(Path(row["path"])) != row["sha256"]:
            raise ValueError(f"image changed: {row['id']}")
        if row["split"] != "train" or row["human_view_from_filename"] == "none":
            continue
        detected = [box for box in previous["models"]["original"] if box["score"] >= 0.35]
        if detected:
            image = read_image(row)
            vector = embedding(model, crop(image, detected[0]["xyxy_normalized"]))
            train.append((row["human_view_from_filename"], vector))
    extra_train_ids = []
    if args.additional_training_manifest:
        extra_rows = json.loads(args.additional_training_manifest.read_text())["rows"]
        original_sites = {row["scene_id"] for row in rows}
        if {row["scene_id"] for row in extra_rows} & original_sites:
            raise ValueError("additional training overlaps original locations")
        for row in extra_rows:
            if row["split"] != "train" or row["direction"] not in ("up", "down"):
                continue
            if file_hash(Path(row["path"])) != row["sha256"]:
                raise ValueError(f"additional training image changed: {row['id']}")
            box = row["bbox_xyxy_normalized"]
            if not box or not (0 <= box[0] < box[2] <= 1 and
                               0 <= box[1] < box[3] <= 1):
                raise ValueError(f"invalid additional training box: {row['id']}")
            train.append((row["direction"], embedding(model, crop(read_image(row), box))))
            extra_train_ids.append(row["id"])
    centroids = fit_centroids(train)

    evaluations = []
    for row in rows:
        if row["split"] != "test":
            continue
        previous = baseline_by_id[row["id"]]
        detected = [box for box in previous["models"]["original"] if box["score"] >= 0.35]
        entry = {"id": row["id"], "expected": row["human_view_from_filename"],
                 "detected": bool(detected), "predicted_direction": None,
                 "score": detected[0]["score"] if detected else None}
        image = None
        if detected:
            image = read_image(row)
            entry["predicted_direction"], entry["direction_margin"] = classify(
                embedding(model, crop(image, detected[0]["xyxy_normalized"])), centroids)
        if specialist:
            if image is None:
                image = read_image(row)
            specialist_result = specialist.predict(
                image, conf=0.35, imgsz=640, device="cpu", verbose=False,
                save=False)[0]
            extra = sorted(specialist_result.boxes,
                           key=lambda box: float(box.conf.item()), reverse=True)
            entry["specialist_detected"] = bool(extra)
            entry["hybrid_direction"] = entry["predicted_direction"]
            entry["hybrid_source"] = "original" if detected else None
            if not detected and extra:
                h, w = image.shape[:2]
                coords = [float(value) for value in extra[0].xyxy[0].tolist()]
                box = [value / scale for value, scale in zip(coords, (w, h, w, h))]
                entry["hybrid_direction"], entry["hybrid_margin"] = classify(
                    embedding(model, crop(image, box)), centroids)
                entry["hybrid_source"] = "specialist"
        evaluations.append(entry)

    output = {"status": "exploratory, no calibrated unknown threshold",
              "method": "unchanged OIV7 detector plus fixed cosine centroids on its frozen features",
              "model_sha256": file_hash(args.original),
              "configuration": {"confidence": 0.35, "image_size": 640, "device": "cpu"},
              "train_detected_crops": {label: sum(direction == label for direction, _ in train)
                                       for label in ("up", "down")},
              "additional_training_ids": extra_train_ids,
              "evaluations": evaluations}
    if specialist:
        output["method"] += "; optional one-class stair detector as fallback"
        output["specialist_sha256"] = file_hash(args.specialist)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
