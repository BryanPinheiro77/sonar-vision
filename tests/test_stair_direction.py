"""Stair semantics and optional second-model integration; no trained weights."""

from importlib.util import find_spec
import math
from types import SimpleNamespace
import unittest

from sonar_vision.core import Detection, Frame, VisionService
from sonar_vision.ultralytics_backend import StairAugmentedBackend, _merge_stairs


def stair(direction, box=(0.1, 0.2, 0.7, 0.9), score=0.8):
    return Detection("stairs", score, box, stair_direction=direction)


class StairMergeTests(unittest.TestCase):
    def test_stair_direction_and_apparent_motion_survive_combined_serialization(self):
        class Echo:
            def infer(self, image):
                return image

            def close(self):
                pass

        vision = VisionService(Echo)
        vision.open("device", "session")
        try:
            for index in range(13):
                size = 0.15 * math.exp(0.3 * index / 10 / 2)
                box = (0.5-size/2, 0.5-size/2, 0.5+size/2, 0.5+size/2)
                result = vision.process(Frame("device", "session", str(index), index*100,
                                              [Detection("stairs", .9, box, "1", "down")],
                                              camera_motion="fixed"))
            obj = result.observation()["objects"][0]
            self.assertEqual(obj["movement"], "approaching")
            self.assertEqual(obj["stair_direction"], "down")
            self.assertEqual(obj["direction"], "unknown")
            self.assertNotIn("risk", obj)
        finally:
            vision.close("device", "session")

    def test_match_preserves_primary_classes_and_tracking(self):
        person = Detection("person", 0.9, (0.75, 0.1, 0.95, 0.8), "1")
        primary_stair = Detection("stairs", 0.75, (0.1, 0.2, 0.7, 0.9), "2")
        merged = _merge_stairs([person, primary_stair], [stair("down")])
        self.assertEqual(merged[0], person)
        self.assertEqual(merged[1].track_id, "2")
        self.assertEqual(merged[1].stair_direction, "down")
        self.assertEqual(len(merged), 2)

    def test_unmatched_specialist_adds_stair_and_conflict_abstains(self):
        person = Detection("person", 0.9, (0.75, 0.1, 0.95, 0.8), "1")
        merged = _merge_stairs([person], [stair("up"), stair("down", score=0.7)])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0], person)
        self.assertEqual(merged[1].stair_direction, "unknown")
        self.assertIsNone(merged[1].track_id)

    def test_distinct_stairs_keep_distinct_directions(self):
        merged = _merge_stairs([], [stair("up", (0.1, 0.1, 0.4, 0.8)),
                                    stair("down", (0.6, 0.1, 0.9, 0.8))])
        self.assertEqual([item.stair_direction for item in merged], ["up", "down"])

    def test_primary_stair_without_second_match_is_unknown(self):
        base = Detection("stairs", 0.75, (0.1, 0.2, 0.7, 0.9), "2")
        merged = _merge_stairs([base], [])
        self.assertEqual(merged, [base])
        self.assertEqual(merged[0].stair_direction, "unknown")

    def test_bridge_between_clusters_reunites_conflicting_directions(self):
        first = stair("up", (0.0, 0.1, 0.5, 0.9), score=0.9)
        second = stair("down", (0.3, 0.1, 0.8, 0.9), score=0.8)
        bridge = stair("up", (0.15, 0.1, 0.65, 0.9), score=0.7)
        for candidates in ([first, second, bridge], [bridge, second, first]):
            merged = _merge_stairs([], candidates)
            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0].stair_direction, "unknown")
            self.assertEqual(merged[0].box, first.box)


AVAILABLE = all(find_spec(name) for name in ("ultralytics", "numpy", "lap"))


@unittest.skipUnless(AVAILABLE, "install .[vision] to exercise the optional adapter")
class StairAdapterTests(unittest.TestCase):
    def test_second_model_reaches_wire_contract_without_losing_person(self):
        import numpy as np
        from ultralytics.engine.results import Boxes

        image = np.zeros((200, 300, 3), dtype=np.uint8)
        box = Boxes(np.array([[30, 40, 210, 180, 0.85, 0]], dtype=np.float32),
                    image.shape[:2])

        class Primary:
            def infer(self, _image):
                return [Detection("person", 0.9, (0.75, 0.1, 0.95, 0.8), "1")]

            def close(self):
                pass

        service = VisionService(lambda: StairAugmentedBackend(
            Primary(), lambda _image: SimpleNamespace(boxes=box,
                                                      names={0: "stairs_down", 1: "stairs_up"})))
        service.open("device", "session")
        result = service.process(Frame("device", "session", "1", 100, image))
        objects = result.observation()["objects"]
        self.assertEqual({item["class_name"] for item in objects}, {"person", "stairs"})
        stairs = next(item for item in objects if item["class_name"] == "stairs")
        self.assertEqual(stairs["stair_direction"], "down")
        self.assertIsNone(stairs["track_id"])
        service.close("device", "session")


if __name__ == "__main__":
    unittest.main()
