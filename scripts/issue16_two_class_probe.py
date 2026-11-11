"""Exploratory offline comparison of an up/down stair detector on held-out sites.

The input's test sites were exposed in earlier issue #16 pilots. Results from
this script are diagnostic and are not a final independent evaluation.
"""

import argparse
import json
from pathlib import Path

from ultralytics import YOLO

from issue16_direction_probe import file_hash


def iou(first, second):
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    overlap = max(0.0, right - left) * max(0.0, bottom - top)
    area_first = (first[2] - first[0]) * (first[3] - first[1])
    area_second = (second[2] - second[0]) * (second[3] - second[1])
    return overlap / (area_first + area_second - overlap)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--direction-weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.direction_weights.is_file() or args.direction_weights.suffix != ".pt":
        parser.error("provide existing trusted local .pt weights")

    rows = json.loads(args.manifest.read_text())["rows"]
    baseline = {row["id"]: row for row in json.loads(args.baseline.read_text())["rows"]}
    if len(rows) != 50 or len(baseline) != 50:
        raise ValueError("expected the 50-site catalog and corresponding baseline")
    model = YOLO(str(args.direction_weights))
    if set(model.names.values()) != {"stairs_up", "stairs_down"}:
        raise ValueError("expected a two-class stair-direction detector")

    evaluations = []
    for row in rows:
        if row["split"] != "test":
            continue
        previous = baseline[row["id"]]
        path = Path(row["path"])
        if (file_hash(path) != row["sha256"] or
                row["sha256"] != previous["sha256"]):
            raise ValueError(f"image changed: {row['id']}")
        result = model.predict(str(path), conf=0.35, imgsz=640,
                               device="cpu", verbose=False, save=False)[0]
        boxes = []
        for box in result.boxes:
            coordinates = [float(v) / scale for v, scale in
                           zip(box.xyxy[0].tolist(),
                               (row["width"], row["height"], row["width"], row["height"]))]
            boxes.append({"direction": model.names[int(box.cls.item())].removeprefix("stairs_"),
                          "score": round(float(box.conf.item()), 4),
                          "xyxy_normalized": [round(v, 4) for v in coordinates]})
        boxes.sort(key=lambda box: -box["score"])
        original = [box for box in previous["models"]["original"]
                    if box["score"] >= 0.35]
        matched = []
        if original:
            for box in boxes:
                overlap = iou(original[0]["xyxy_normalized"], box["xyxy_normalized"])
                matched.append({"direction": box["direction"], "score": box["score"],
                                "iou_with_original": round(overlap, 4)})
        evaluations.append({"id": row["id"], "expected": row["human_view_from_filename"],
                            "original_detected": bool(original),
                            "predictions": boxes, "overlap_with_original": matched})

    output = {"status": "exploratory; old test sites previously viewed in other pilots",
              "model_sha256": file_hash(args.direction_weights),
              "configuration": {"confidence": 0.35, "image_size": 640, "device": "cpu"},
              "evaluations": evaluations}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    positives = [r for r in evaluations if r["expected"] != "none"]
    negatives = [r for r in evaluations if r["expected"] == "none"]
    print(json.dumps({"detected": sum(bool(r["predictions"]) for r in positives),
                      "correct": sum(bool(r["predictions"]) and
                                     r["predictions"][0]["direction"] == r["expected"]
                                     for r in positives),
                      "false_positives": sum(bool(r["predictions"]) for r in negatives)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
