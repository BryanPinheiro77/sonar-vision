"""Run the frozen #16 two-stage protocol once on a separately catalogued set.

This is a local, diagnostic image-level evaluation. It is not a hardware,
video, localization-IoU, or field-safety evaluation.
"""

import argparse
import json
from pathlib import Path

import cv2
from ultralytics import YOLO

from issue16_direction_probe import file_hash
from issue16_two_class_probe import iou


def normalized_boxes(result, image_shape):
    height, width = image_shape[:2]
    items = []
    for box in result.boxes:
        label = result.names[int(box.cls.item())]
        coordinates = [float(value) / scale for value, scale in
                       zip(box.xyxy[0].tolist(), (width, height, width, height))]
        items.append({"label": label, "score": round(float(box.conf.item()), 4),
                      "box": coordinates})
    return sorted(items, key=lambda item: -item["score"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; first-pass result must not be overwritten")

    catalog = json.loads(args.manifest.read_text())
    protocol = json.loads(args.protocol.read_text())
    if catalog["status"] != "provenance_resolved" or protocol["status"] != "frozen_before_inference":
        raise ValueError("resolve provenance and freeze the protocol before inference")
    rows = catalog["rows"]
    if len(rows) != 30 or len({row["sha256"] for row in rows}) != 30:
        raise ValueError("expected 30 unique catalogued images")
    for label in ("up", "down", "none"):
        if sum(row["expected_from_csv"] == label for row in rows) != 10:
            raise ValueError(f"expected ten {label} images")
    detector_path = Path(protocol["detector_weights"])
    direction_path = Path(protocol["direction_weights"])
    if (file_hash(detector_path) != protocol["detector_sha256"] or
            file_hash(direction_path) != protocol["direction_sha256"]):
        raise ValueError("frozen model hash mismatch")
    detector = YOLO(str(detector_path))
    direction = YOLO(str(direction_path))
    if len(detector.names) != 601 or "Stairs" not in detector.names.values():
        raise ValueError("expected original OIV7 detector")
    if set(direction.names.values()) != {"stairs_up", "stairs_down"}:
        raise ValueError("expected up/down detector")

    evaluations = []
    for row in rows:
        path = Path(row["path"])
        if file_hash(path) != row["sha256"]:
            raise ValueError(f"test image changed: {row['id']}")
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"cannot decode test image: {row['id']}")
        settings = {"conf": protocol["confidence"], "imgsz": protocol["image_size"],
                    "device": protocol["device"], "verbose": False, "save": False}
        found = [box for box in normalized_boxes(detector.predict(image, **settings)[0], image.shape)
                 if box["label"] == "Stairs"]
        proposed = [box for box in normalized_boxes(direction.predict(image, **settings)[0], image.shape)
                    if box["label"] in ("stairs_up", "stairs_down")]
        predicted = "none"
        matched = []
        if found:
            for candidate in proposed:
                overlap = iou(found[0]["box"], candidate["box"])
                if overlap >= protocol["association_iou"]:
                    matched.append({"direction": candidate["label"].removeprefix("stairs_"),
                                    "score": candidate["score"], "iou": round(overlap, 4)})
            if len({item["direction"] for item in matched}) == 1:
                predicted = matched[0]["direction"]
            else:
                predicted = "unknown"
        evaluations.append({"id": row["id"], "expected": row["expected_from_csv"],
                            "predicted": predicted,
                            "oiv7_stairs_score": found[0]["score"] if found else None,
                            "direction_candidates": matched})

    positives = [row for row in evaluations if row["expected"] in ("up", "down")]
    negatives = [row for row in evaluations if row["expected"] == "none"]
    summary = {"positive_count": len(positives), "negative_count": len(negatives),
               "correct_direction": sum(row["predicted"] == row["expected"] for row in positives),
               "wrong_direction": sum(row["predicted"] in ("up", "down") and
                                      row["predicted"] != row["expected"] for row in positives),
               "unknown": sum(row["predicted"] == "unknown" for row in positives),
               "missed_stairs": sum(row["predicted"] == "none" for row in positives),
               "false_positive_scenes": sum(row["predicted"] != "none" for row in negatives)}
    report = {"status": "first-pass diagnostic; no threshold tuning on these images",
              "provenance": catalog["resolved_origin"],
              "protocol": {key: protocol[key] for key in
                           ("confidence", "image_size", "device", "association_iou",
                            "detector_sha256", "direction_sha256")},
              "summary": summary, "evaluations": evaluations}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
