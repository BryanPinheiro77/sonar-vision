"""#51 export gates: approved geometry, frozen sources and physical-group split."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

SPEC = importlib.util.spec_from_file_location(
    "issue51", Path(__file__).resolve().parents[1] / "scripts/issue51_pilot.py"
)
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class PilotExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rows = []
        for group, count in (
            ("development-office-original", 9),
            ("cena-a-local-informado-pelo-autor", 4),
            ("cena-b-local-informado-pelo-autor", 4),
        ):
            for i in range(count):
                name = (
                    f"office-{i}"
                    if count == 9
                    else f"cena-{'a' if 'cena-a' in group else 'b'}-{i:02d}s"
                )
                path = self.root / f"{name}.png"
                path.write_bytes(
                    name.encode()
                )  # export validates bytes/hash; run validates decoding
                n = (4 if i < 5 else 3) if count == 9 else 2
                labels = [
                    {
                        "physical_class": "chair" if j == 0 else "table",
                        "box": [0.0, 0.1, 0.8, 1.0],
                        "approval": "approved by Bryan",
                    }
                    for j in range(n)
                ]
                rows.append(
                    {
                        "sample_id": name,
                        "group": group,
                        "image": path.name,
                        "image_sha256": pilot.digest(path),
                        "labels": labels,
                    }
                )
        frozen = self.root / "frozen.json"
        frozen.write_text(json.dumps({"records": rows[:9]}))
        reference = self.root / "new.json"
        reference.write_text(
            json.dumps(
                {
                    "clips": [
                        {
                            "clip_id": f"cena-{letter}",
                            "frame_selection": [
                                {
                                    "requested_timestamp_s": i,
                                    "annotations": rows[offset + i]["labels"],
                                }
                                for i in range(4)
                            ],
                        }
                        for letter, offset in (("a", 9), ("b", 13))
                    ]
                }
            )
        )
        self.data = {
            "records": rows,
            "frozen_development_reference": {
                "path": frozen.name,
                "sha256": pilot.digest(frozen),
            },
            "source_annotation_hashes": {str(reference): pilot.digest(reference)},
        }
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps(self.data))

    def write(self, data):
        self.manifest.write_text(json.dumps(data))

    def test_export_does_not_expose_evaluation_to_trainer_and_roundtrips_geometry(self):
        rows = pilot.export(self.manifest, self.root / "dataset")
        config = json.loads((self.root / "dataset/data.yaml").read_text())
        self.assertEqual(set(config), {"path", "train", "val", "names"})
        self.assertEqual(sum(r["role"] == "evaluation" for r in rows), 4)
        for row in rows:
            path = self.root / "dataset/labels" / row["role"] / f"{row['id']}.txt"
            for line, target in zip(path.read_text().splitlines(), row["labels"]):
                c, cx, cy, w, h = map(float, line.split())
                for a, b in zip(
                    (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), target["box"]
                ):
                    self.assertAlmostEqual(a, b, places=7)
        with self.assertRaisesRegex(ValueError, "output_exists"):
            pilot.export(self.manifest, self.root / "dataset")

    def test_modified_reference_or_image_is_rejected_before_output(self):
        for key in ("reference", "image"):
            with self.subTest(key=key):
                original = deepcopy(self.data)
                if key == "reference":
                    original["frozen_development_reference"]["sha256"] = "0" * 64
                else:
                    original["records"][0]["image_sha256"] = "0" * 64
                self.write(original)
                with self.assertRaises(ValueError):
                    pilot.export(self.manifest, self.root / "blocked")
                self.assertFalse((self.root / "blocked").exists())

    def test_unapproved_modified_and_invalid_boxes_are_rejected(self):
        for change in (
            {"approval": "pending"},
            {"box": [0.0, 0.0, 0.4, 0.8]},
            {"box": [0.0, 0.0, float("nan"), 1.0]},
            {"physical_class": "person"},
        ):
            with self.subTest(change=change):
                data = deepcopy(self.data)
                data["records"][0]["labels"][0].update(change)
                self.write(data)
                with self.assertRaises(ValueError):
                    pilot.validated_records(self.manifest)

    def test_same_image_in_two_physical_groups_is_rejected(self):
        data = deepcopy(self.data)
        data["records"][9]["image"] = data["records"][0]["image"]
        data["records"][9]["image_sha256"] = data["records"][0]["image_sha256"]
        self.write(data)
        with self.assertRaisesRegex(ValueError, "split_leakage"):
            pilot.validated_records(self.manifest)

    def test_escape_path_is_rejected(self):
        data = deepcopy(self.data)
        data["records"][0]["image"] = "../escape.png"
        self.write(data)
        with self.assertRaisesRegex(ValueError, "invalid_image_path"):
            pilot.validated_records(self.manifest)
