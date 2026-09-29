"""Run a frozen image-level comparison on the reserved next30 local scenes.

Outputs diagnostic counts only. It does not establish localization quality,
field validity, safety, or issue #7 acceptance criteria.
"""

import argparse
import json
from pathlib import Path

import cv2
from ultralytics import YOLO

from issue16_blind30_probe import normalized_boxes
from issue16_direction_probe import file_hash
from issue16_two_class_probe import iou


def predict_direct(result):
    classes = {box["label"].removeprefix("stairs_") for box in result}
    if not classes:
        return "none"
    if len(classes) > 1:
        return "unknown"
    return classes.pop()


def predict_reference(presence, direction, association_iou):
    stairs = [box for box in presence if box["label"] == "Stairs"]
    if not stairs:
        return "none"
    matched = {box["label"].removeprefix("stairs_") for box in direction
               if box["label"] in ("stairs_up", "stairs_down") and
               iou(stairs[0]["box"], box["box"]) >= association_iou}
    return matched.pop() if len(matched) == 1 else "unknown"


def summarize(rows, key):
    positives = [row for row in rows if row["expected"] in ("up", "down")]
    negatives = [row for row in rows if row["expected"] == "none"]
    return {"positive_count": len(positives), "negative_count": len(negatives),
            "correct_direction": sum(row[key] == row["expected"] for row in positives),
            "wrong_direction": sum(row[key] in ("up", "down") and
                                   row[key] != row["expected"] for row in positives),
            "unknown": sum(row[key] == "unknown" for row in positives),
            "missed_stairs": sum(row[key] == "none" for row in positives),
            "false_positive_scenes": sum(row[key] != "none" for row in negatives)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("first-pass result exists; refusing overwrite")
    catalog = json.loads(args.manifest.read_text())
    protocol = json.loads(args.protocol.read_text())
    if (catalog["status"] != "reserved_origin_confirmed_by_user_no_pixel_inspection_no_inference"
            or protocol["status"] != "frozen_before_inference"):
        raise ValueError("the set must be reserved and the protocol frozen")
    rows = catalog["rows"]
    if len(rows) != 30 or len({row["sha256"] for row in rows}) != 30:
        raise ValueError("expected 30 unique catalogued images")
    if {label: sum(row["expected"] == label for row in rows)
            for label in ("up", "down", "none")} != {"up": 10, "down": 10, "none": 10}:
        raise ValueError("unexpected label balance")

    weights = {}
    models = {}
    for key in ("candidate", "reference_presence", "reference_direction"):
        path = Path(protocol["weights"][key]["path"])
        digest = protocol["weights"][key]["sha256"]
        if file_hash(path) != digest:
            raise ValueError(f"frozen weight mismatch: {key}")
        weights[key] = digest
        models[key] = YOLO(str(path))
    if set(models["candidate"].names.values()) != {"stairs_up", "stairs_down"}:
        raise ValueError("candidate has unexpected classes")
    if set(models["reference_direction"].names.values()) != {"stairs_up", "stairs_down"}:
        raise ValueError("reference direction has unexpected classes")
    if len(models["reference_presence"].names) != 601:
        raise ValueError("reference presence must be OIV7")

    output = []
    settings = {"conf": protocol["confidence"], "imgsz": protocol["image_size"],
                "device": protocol["device"], "verbose": False, "save": False}
    for row in rows:
        path = Path(row["path"])
        if file_hash(path) != row["sha256"]:
            raise ValueError(f"reserved image changed: {row['id']}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"cannot decode image: {row['id']}")
        boxes = {key: normalized_boxes(model.predict(image, **settings)[0], image.shape)
                 for key, model in models.items()}
        output.append({"id": row["id"], "expected": row["expected"],
                       "candidate": predict_direct(boxes["candidate"]),
                       "reference": predict_reference(boxes["reference_presence"],
                                                      boxes["reference_direction"],
                                                      protocol["association_iou"]),
                       "candidate_boxes": boxes["candidate"],
                       "reference_presence_stairs": [box for box in
                                                      boxes["reference_presence"]
                                                      if box["label"] == "Stairs"],
                       "reference_direction_boxes": boxes["reference_direction"]})
    report = {"status": "first-pass diagnostic; no tuning on reserved scenes",
              "provenance": catalog["provenance"],
              "protocol": protocol, "summary": {
                  "candidate": summarize(output, "candidate"),
                  "reference": summarize(output, "reference")}, "rows": output}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
