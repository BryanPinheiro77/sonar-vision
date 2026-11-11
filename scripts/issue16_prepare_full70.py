"""Prepare an exploratory 70-scene local training set without reserved test images.

The 17 old test scenes were exposed in prior pilots and can now be used for
training. Their boxes are provisional agent-reviewed annotations, not approved
human ground truth. The next 30-scene evaluation set is deliberately excluded.
"""

import argparse
import json
from pathlib import Path
import shutil

from issue16_direction_probe import file_hash


def yolo_box(box, class_id):
    left, top, right, bottom = box
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"invalid normalized box: {box}")
    return f"{class_id} {(left + right) / 2:.6f} {(top + bottom) / 2:.6f} {right - left:.6f} {bottom - top:.6f}\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; do not overwrite an annotated training set")

    records = json.loads(args.manifest.read_text())["rows"]
    predictions = {row["id"]: row for row in json.loads(args.baseline.read_text())["rows"]}
    if len(records) != 50 or len(predictions) != 50:
        raise ValueError("expected 50 original scenes and predictions")
    old_test = [row for row in records if row["split"] == "test"]
    if len(old_test) != 17:
        raise ValueError("expected 17 exposed old test scenes")

    # The original detector missed this visible descending stone staircase.
    # The rough box was drawn by visual inspection, not inferred from a model.
    manual_boxes = {14: [0.0, 0.28, 1.0, 1.0]}
    boxes = []
    for row in old_test:
        previous = predictions[row["id"]]
        if row["sha256"] != previous["sha256"] or file_hash(Path(row["path"])) != row["sha256"]:
            raise ValueError(f"original image mismatch: {row['id']}")
        direction = row["human_view_from_filename"]
        if direction == "none":
            box = None
            source = "negative_empty_label"
        elif row["id"] in manual_boxes:
            box = manual_boxes[row["id"]]
            source = "agent_visual_manual"
        else:
            candidates = previous["models"]["original"]
            if not candidates:
                raise ValueError(f"positive image without box: {row['id']}")
            box = candidates[0]["xyxy_normalized"]
            source = "oiv7_proposal_agent_visual_review"
        boxes.append({"id": row["id"], "direction": direction, "box": box,
                      "box_source": source, "sha256": row["sha256"]})

    for split in ("train", "val"):
        for kind in ("images", "labels"):
            (args.output / kind / split).mkdir(parents=True)
        for image in (args.source / "images" / split).iterdir():
            (args.output / "images" / split / image.name).symlink_to(image.resolve())
        for label in (args.source / "labels" / split).iterdir():
            shutil.copy2(label, args.output / "labels" / split / label.name)

    for row, annotation in zip(old_test, boxes):
        image = Path(row["path"])
        (args.output / "images" / "train" / image.name).symlink_to(image)
        label = args.output / "labels" / "train" / (image.stem + ".txt")
        direction = annotation["direction"]
        label.write_text("" if direction == "none" else yolo_box(
            annotation["box"], {"up": 0, "down": 1}[direction]))

    (args.output / "dataset.yaml").write_text(
        f"path: {args.output.resolve()}\ntrain: images/train\nval: images/val\n"
        "names:\n  0: stairs_up\n  1: stairs_down\n")
    (args.output / "provenance.json").write_text(json.dumps({
        "status": "exploratory_70_training; no independent test scenes included",
        "source_dataset": str(args.source),
        "old_test_promoted_to_training": True,
        "reason": "17 old test scenes were exposed in prior pilots; next30 stays reserved",
        "original_scene_count": 50,
        "additional_scene_count": 20,
        "train_images": len(list((args.output / "images" / "train").iterdir())),
        "val_images": len(list((args.output / "images" / "val").iterdir())),
        "old_test_annotations": boxes,
        "annotation_limit": "agent-reviewed boxes; no independent human ground truth",
    }, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"train": 60, "val": 10, "positive_added": 12,
                      "negative_added": 5, "output": str(args.output)}))


if __name__ == "__main__":
    main()
