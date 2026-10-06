"""Add the exposed 30-scene diagnostic set to exploratory local training.

The separately catalogued next30 set is never opened here. Every old positive
box is a provisional agent-reviewed annotation. Capture origin was corrected
by Bryan but cannot be independently verified from the supplied files.
"""

import argparse
import json
from pathlib import Path
import shutil

from issue16_direction_probe import file_hash
from issue16_prepare_full70 import yolo_box


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; do not overwrite an annotated training set")

    catalog = json.loads(args.manifest.read_text())
    rows = catalog["rows"]
    proposals = {item["id"]: item for item in json.loads(args.proposals.read_text())}
    if len(rows) != 30 or len(proposals) != 20:
        raise ValueError("expected 30 catalogued scenes and 20 stair proposals")
    if {item["sha256"] for item in rows} & {
            item["sha256"] for item in json.loads(
                (args.source / "provenance.json").read_text())["old_test_annotations"]}:
        raise ValueError("image overlaps older training data")

    # Visual review of the contact sheet corrected narrow/missing OIV7 boxes.
    overrides = {
        2: [0.17, 0.18, 0.95, 1.0],
        4: [0.14, 0.19, 0.98, 1.0],
        10: [0.0, 0.29, 1.0, 1.0],
        12: [0.22, 0.42, 0.98, 1.0],
        15: [0.02, 0.38, 0.93, 1.0],
        17: [0.18, 0.25, 0.88, 1.0],
    }

    for split in ("train", "val"):
        for kind in ("images", "labels"):
            (args.output / kind / split).mkdir(parents=True)
        for image in (args.source / "images" / split).iterdir():
            (args.output / "images" / split / image.name).symlink_to(image.resolve())
        for label in (args.source / "labels" / split).iterdir():
            shutil.copy2(label, args.output / "labels" / split / label.name)

    annotations = []
    for row in rows:
        image = Path(row["path"])
        if file_hash(image) != row["sha256"]:
            raise ValueError(f"old diagnostic image changed: {row['id']}")
        direction = row["expected_from_csv"]
        if direction == "none":
            box = None
            source = "negative_empty_label"
        elif row["id"] in overrides:
            box = overrides[row["id"]]
            source = "agent_visual_manual_or_corrected"
        else:
            item = proposals[row["id"]]["top"]
            if item is None:
                raise ValueError(f"positive without proposal or manual box: {row['id']}")
            box = item["box"]
            source = "oiv7_low_conf_proposal_agent_visual_review"
        target = args.output / "images" / "train" / image.name
        if target.exists() or target.is_symlink():
            raise ValueError(f"duplicate image name: {image.name}")
        target.symlink_to(image)
        label = args.output / "labels" / "train" / (image.stem + ".txt")
        label.write_text("" if direction == "none" else yolo_box(
            box, {"up": 0, "down": 1}[direction]))
        annotations.append({"id": row["id"], "direction": direction,
                            "box": box, "box_source": source, "sha256": row["sha256"]})

    (args.output / "dataset.yaml").write_text(
        f"path: {args.output.resolve()}\ntrain: images/train\nval: images/val\n"
        "names:\n  0: stairs_up\n  1: stairs_down\n")
    (args.output / "provenance.json").write_text(json.dumps({
        "status": "exploratory_100_training; next30 reserved",
        "source_dataset": str(args.source),
        "old_diagnostic_promoted_to_training": True,
        "permission": "Bryan explicitly authorized local training after the first pass",
        "origin_note": catalog["provenance_conflict"],
        "train_images": len(list((args.output / "images" / "train").iterdir())),
        "val_images": len(list((args.output / "images" / "val").iterdir())),
        "added_annotations": annotations,
        "annotation_limit": "agent-reviewed boxes; no independent human ground truth",
    }, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"train": 90, "val": 10, "positive_added": 20,
                      "negative_added": 10, "output": str(args.output)}))


if __name__ == "__main__":
    main()
