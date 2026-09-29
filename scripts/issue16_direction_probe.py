"""Offline issue #16 probe; local photos and trusted weights only.

The original OIV7 detector stays unchanged. A two-class centroid probe reads
its frozen features on stair crops. This is research code, not a safety alert.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


def file_hash(path):
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path):
    data = json.loads(path.read_text())
    rows = [row for row in data["images"] if row["split"] != "exclude_privacy"]
    train_scenes = {row["scene_id"] for row in rows if row["split"] == "train"}
    test_scenes = {row["scene_id"] for row in rows if row["split"] == "test"}
    if train_scenes & test_scenes:
        raise ValueError("train/test share a staircase scene")
    for row in rows:
        image_path = Path(row["path"])
        if not image_path.is_file() or file_hash(image_path) != row["sha256"]:
            raise ValueError(f"missing/changed local image: {row['id']}")
        box = row["box_xyxy_normalized"]
        if row["split"] in ("train", "test"):
            if row["human_direction"] not in ("up", "down") or not box:
                raise ValueError(f"positive image needs label and box: {row['id']}")
            if not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
                raise ValueError(f"invalid box: {row['id']}")
        elif row["split"] == "test_negative" and (box or row["human_direction"] != "none"):
            raise ValueError(f"negative image has a stair label: {row['id']}")
    return rows


def read_image(row):
    image = cv2.imread(row["path"], cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cannot decode image: {row['id']}")
    return image


def crop(image, box):
    height, width = image.shape[:2]
    x1, y1, x2, y2 = (int(box[0] * width), int(box[1] * height),
                      int(box[2] * width), int(box[3] * height))
    if x2 <= x1 or y2 <= y1:
        raise ValueError("empty crop")
    return image[y1:y2, x1:x2]


def embedding(model, image):
    """Mean-pool the three feature maps entering YOLOv8's Detect head."""
    vectors = []

    def capture(_head, inputs):
        maps = inputs[0]
        vectors.append(np.concatenate([
            item.detach().float().mean((2, 3)).cpu().numpy()[0] for item in maps
        ]))

    hook = model.model.model[-1].register_forward_pre_hook(capture)
    try:
        model.predict(image, conf=0.1, imgsz=640, device="cpu", verbose=False,
                      save=False)
    finally:
        hook.remove()
    if len(vectors) != 1:
        raise RuntimeError("expected one feature vector per crop")
    return vectors[0]


def normalized(vector):
    return vector / max(float(np.linalg.norm(vector)), 1e-12)


def fit_centroids(features):
    centroids = {}
    for label in ("up", "down"):
        group = [normalized(vector) for direction, vector in features
                 if direction == label]
        if not group:
            raise ValueError(f"no {label} training examples")
        centroids[label] = normalized(np.mean(group, axis=0))
    return centroids


def classify(vector, centroids):
    feature = normalized(vector)
    up = float(feature @ centroids["up"])
    down = float(feature @ centroids["down"])
    # Similarity difference, not a calibrated probability.
    return ("up" if up > down else "down"), round(up - down, 6)


def stair_boxes(result):
    return sorted((box for box in result.boxes
                   if result.names[int(box.cls.item())].lower() == "stairs"),
                  key=lambda box: float(box.conf.item()), reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--specialist", type=Path,
                        help="optional one-class local pilot for fallback comparison")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.original, args.pilot, args.specialist):
        if path is None:
            continue
        if not path.is_file() or path.suffix != ".pt":
            parser.error("use existing trusted local .pt weights")
    rows = load_rows(args.annotations)
    original, pilot = YOLO(str(args.original)), YOLO(str(args.pilot))
    specialist = YOLO(str(args.specialist)) if args.specialist else None
    if len(original.names) != 601 or "Stairs" not in original.names.values():
        raise ValueError("original weight is not the expected 601-class OIV7 detector")
    if set(pilot.names.values()) != {"stairs_up", "stairs_down"}:
        raise ValueError("pilot weight is not the expected two-class detector")
    if specialist and set(specialist.names.values()) != {"stairs"}:
        raise ValueError("specialist must be a one-class stairs detector")

    train = []
    for row in rows:
        if row["split"] == "train":
            image = read_image(row)
            train.append((row["human_direction"],
                          embedding(original, crop(image, row["box_xyxy_normalized"]))))
    centroids = fit_centroids(train)

    evaluations = []
    for row in rows:
        if row["split"] not in ("test", "test_negative"):
            continue
        image = read_image(row)
        baseline = original.predict(image, conf=0.35, imgsz=640, device="cpu",
                                    verbose=False, save=False)[0]
        pilot_result = pilot.predict(image, conf=0.35, imgsz=640, device="cpu",
                                     verbose=False, save=False)[0]
        found = stair_boxes(baseline)
        extra = stair_boxes(specialist.predict(
            image, conf=0.35, imgsz=640, device="cpu", verbose=False,
            save=False)[0]) if specialist else []
        entry = {"id": row["id"], "scene_id": row["scene_id"],
                 "expected": row["human_direction"],
                 "original_stairs_count": len(found),
                 "original_other_classes_count": len(baseline.boxes) - len(found),
                 "original_best_stairs_score": round(float(found[0].conf.item()), 4)
                                               if found else None,
                 "pilot_detections": len(pilot_result.boxes),
                 "cascade_direction": None, "oracle_crop_direction": None}
        if specialist:
            entry["specialist_stairs_count"] = len(extra)
            entry["hybrid_direction"] = None
            entry["hybrid_source"] = None
        if found:
            coords = tuple(float(v) for v in found[0].xyxy[0].tolist())
            h, w = image.shape[:2]
            detected_box = (coords[0] / w, coords[1] / h,
                            coords[2] / w, coords[3] / h)
            entry["cascade_direction"], entry["cascade_margin"] = classify(
                embedding(original, crop(image, detected_box)), centroids)
        if specialist and (found or extra):
            selected = found[0] if found else extra[0]
            coords = tuple(float(v) for v in selected.xyxy[0].tolist())
            h, w = image.shape[:2]
            selected_box = (coords[0] / w, coords[1] / h,
                            coords[2] / w, coords[3] / h)
            entry["hybrid_source"] = "original" if found else "specialist"
            if found:
                entry["hybrid_direction"] = entry["cascade_direction"]
            else:
                entry["hybrid_direction"], entry["hybrid_margin"] = classify(
                    embedding(original, crop(image, selected_box)), centroids)
        if row["split"] == "test":
            entry["oracle_crop_direction"], entry["oracle_margin"] = classify(
                embedding(original, crop(image, row["box_xyxy_normalized"])), centroids)
        evaluations.append(entry)

    output = {"method": "original OIV7 detector unchanged plus frozen OIV7 features "
                        "and two class centroids on stair crops",
              "status": "exploratory; uncalibrated, no unknown threshold, not for integration",
              "configuration": {"confidence": 0.35, "image_size": 640, "device": "cpu"},
              "weights_sha256": {"original": file_hash(args.original),
                                 "pilot": file_hash(args.pilot)},
              "train_count": len(train), "train_labels": {label: sum(x[0] == label for x in train)
                                                        for label in ("up", "down")},
              "evaluations": evaluations}
    if specialist:
        output["method"] += "; optional one-class stair detector as fallback"
        output["weights_sha256"]["specialist"] = file_hash(args.specialist)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
