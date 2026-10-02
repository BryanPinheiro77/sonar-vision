"""Synthetic laboratory tests; no claims about physical audio or safety."""
from copy import deepcopy
from itertools import product
import unittest

from sonar_vision.audio import AudioConfig, AudioPolicy, NAMES


def config(**changes):
    values = dict(confidence_min=0.5, track_cooldown_ms=2000,
                  semantic_cooldown_ms=10000, memory_ttl_ms=30000,
                  max_tracks=32, max_semantics=32, class_order=tuple(NAMES))
    values.update(changes)
    return AudioConfig(**values)


def obj(track="1", cls="person", direction="left", movement="unknown", score=0.8, stair=None):
    return dict(track_id=track, class_name=cls, confidence=score,
                direction=direction, movement=movement, stair_direction=stair)


def observation(frame, objects, epoch="e"):
    return dict(version="0.1", type="visual_observation", session_id="s",
                message_id=f"obs-{frame}", frame_id=str(frame),
                captured_at_ms=frame * 100, valid_for_ms=1000,
                tracker_epoch=epoch, objects=objects)


class AudioPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.policy = AudioPolicy("s", config(), clock=lambda: self.now)
        self.frame = 0

    def select(self, objects, *, age=0, epoch="e", policy=None):
        self.frame += 1
        return (policy or self.policy).select(
            observation(self.frame, objects, epoch), capture_age_lower_bound_ms=age)

    def test_contract_references_text_and_no_remote_commands(self):
        source = observation(1, [obj()])
        result = self.policy.select(source, capture_age_lower_bound_ms=400)
        self.assertEqual(result["text"], "Pessoa à esquerda")
        self.assertEqual(result["observation_id"], source["message_id"])
        for key in ("session_id", "frame_id", "captured_at_ms", "valid_for_ms"):
            self.assertEqual(result[key], source[key])
        self.assertEqual(set(result), {"version", "type", "session_id", "message_id",
                                      "frame_id", "captured_at_ms", "valid_for_ms",
                                      "observation_id", "text", "directional"})
        self.assertTrue(result["directional"])
        self.assertEqual(source, observation(1, [obj()]))

    def test_all_phrase_combinations_fit_and_unknowns_are_not_invented(self):
        for cls, direction, movement in product(NAMES, ("left", "center", "right", "unknown"),
                                               ("approaching", "receding", "crossing", "stable", "unknown")):
            for stair in (("up", "down", "unknown") if cls == "stairs" else (None,)):
                with self.subTest(cls=cls, direction=direction, movement=movement, stair=stair):
                    result = self.select([obj(cls=cls, direction=direction, movement=movement, stair=stair)],
                                         policy=AudioPolicy("s", config()))
                    self.assertLessEqual(len(result["text"]), 120)
                    self.assertEqual(result["directional"], direction != "unknown" or movement in
                                     {"approaching", "receding", "crossing"})
                    self.assertNotIn("colisão", result["text"])
                    self.assertNotIn("Pare", result["text"])
        result = self.select([obj(direction="unknown")], policy=AudioPolicy("s", config()))
        self.assertEqual(result["text"], "Pessoa")

    def test_empty_unknown_and_traffic_light_do_not_authorize_movement(self):
        for objects in ([], [obj(cls="unknown")], [obj(cls="traffic_light")], [obj(score=0.49)]):
            self.assertIsNone(self.select(objects))
        self.assertIsNotNone(self.select([obj(score=0.5)]))

    def test_stable_track_is_not_narrated_each_frame_or_after_cooldown(self):
        self.assertIsNotNone(self.select([obj()]))
        for self.now in (1, 10, 20, 30, 40):
            self.assertIsNone(self.select([obj()]))
        self.assertIsNone(self.select([obj(movement="stable")]))

    def test_state_change_waits_track_cooldown_and_wins_over_new_track(self):
        self.select([obj()])
        self.now = 1.999
        self.assertIsNone(self.select([obj(direction="right")]))
        self.now = 2
        result = self.select([obj(track="2", cls="car", score=0.99), obj(direction="right", score=0.5)])
        self.assertEqual(result["text"], "Pessoa à direita")

    def test_id_or_epoch_change_does_not_repeat_equivalent_content(self):
        self.select([obj()])
        self.now = 9.999
        self.assertIsNone(self.select([obj(track="2")]))
        self.assertIsNone(self.select([obj()], epoch="new"))
        self.now = 10
        self.assertIsNotNone(self.select([obj(track="2")], epoch="new"))

    def test_untracked_objects_have_semantic_suppression(self):
        self.assertIsNotNone(self.select([obj(track=None)]))
        self.assertIsNone(self.select([obj(track=None)]))

    def test_known_expiration_boundary_and_source_validity(self):
        self.assertIsNotNone(self.select([obj()], age=999))
        self.assertIsNone(self.select([obj(direction="right")], age=1000))
        other = AudioPolicy("s", config())
        source = observation(1, [obj()])
        source["valid_for_ms"] = 250
        self.assertIsNone(other.select(source, capture_age_lower_bound_ms=250))
        source = observation(2, [obj()])
        source["valid_for_ms"] = 2000
        self.assertEqual(other.select(source, capture_age_lower_bound_ms=999)["valid_for_ms"], 1000)

    def test_invalid_envelope_is_rejected_before_state_changes(self):
        base = observation(1, [obj()])
        variants = []
        for key, value in (("session_id", "old"), ("frame_id", "01"), ("captured_at_ms", True),
                           ("valid_for_ms", 0), ("objects", [obj()] * 21), ("version", "0.2")):
            bad = deepcopy(base)
            bad[key] = value
            variants.append(bad)
        bad = deepcopy(base)
        bad["vibration"] = "urgent"
        variants.append(bad)
        for key, value in (("confidence", float("nan")), ("confidence", True),
                           ("direction", []), ("movement", "collision"),
                           ("stair_direction", "up"), ("track_id", "")):
            bad = deepcopy(base)
            bad["objects"][0][key] = value
            variants.append(bad)
        bad = deepcopy(base)
        bad["objects"].append(obj())
        variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.policy.select(bad, capture_age_lower_bound_ms=0)
        self.assertIsNotNone(self.policy.select(base, capture_age_lower_bound_ms=0))

    def test_replay_capture_regression_and_invalid_age(self):
        source = observation(2, [obj()])
        for age in (-1, True, 0.5):
            with self.assertRaises(ValueError):
                self.policy.select(source, capture_age_lower_bound_ms=age)
        self.policy.select(source, capture_age_lower_bound_ms=0)
        for bad in (source, observation(1, [obj()])):
            with self.assertRaises(ValueError):
                self.policy.select(bad, capture_age_lower_bound_ms=0)
        bad = observation(3, [obj()])
        bad["captured_at_ms"] = 199
        with self.assertRaises(ValueError):
            self.policy.select(bad, capture_age_lower_bound_ms=0)

    def test_multiple_candidates_configured_class_order_and_confidence_ties(self):
        result = self.select([obj(track="2", cls="car", score=0.99), obj(score=0.6)])
        self.assertEqual(result["text"], "Pessoa à esquerda")
        other = AudioPolicy("s", config())
        result = self.select([obj(track="1", direction="right", score=0.9),
                              obj(track="2", direction="left", score=0.8)], policy=other)
        self.assertEqual(result["text"], "Pessoa à direita")
        other = AudioPolicy("s", config())
        result = self.select([obj(track="1", direction="right"), obj(track="2")], policy=other)
        self.assertEqual(result["text"], "Pessoa à direita")

    def test_bounded_state_saturation_and_ttl_release(self):
        other = AudioPolicy("s", config(max_tracks=1, max_semantics=1), clock=lambda: self.now)
        self.assertIsNotNone(self.select([obj()], policy=other))
        self.assertIsNone(self.select([obj(track="2", cls="car")], policy=other))
        self.now = 30
        self.assertIsNotNone(self.select([obj(track="2", cls="car")], policy=other))
        self.assertEqual(len(other._tracks), 1)
        self.assertEqual(len(other._semantics), 1)

    def test_existing_vision_result_connects_without_fabricating_direction(self):
        from sonar_vision.core import Detection, Frame, VisionService

        class Backend:
            def infer(self, image):
                return [Detection("person", 0.9, (0.1, 0.1, 0.5, 0.8), "1")]
            def close(self):
                pass

        vision = VisionService(Backend)
        vision.open("device", "s")
        result = vision.process(Frame("device", "s", "0", 100, None))
        audio = self.policy.select(result.observation(), capture_age_lower_bound_ms=50)
        self.assertEqual(audio["text"], "Pessoa")
        self.assertFalse(audio["directional"])
        self.assertEqual(audio["observation_id"], result.message_id)
        vision.close("device", "s")

    def test_suggestions_have_distinct_ids_and_current_references(self):
        first = self.select([obj()])
        self.now = 2
        second = self.select([obj(direction="right")])
        self.assertNotEqual(first["message_id"], second["message_id"])
        self.assertEqual(second["frame_id"], "2")
        self.assertEqual(second["observation_id"], "obs-2")

    def test_sessions_have_independent_cooldown(self):
        self.select([obj()])
        other = AudioPolicy("s", config())
        self.assertIsNotNone(self.select([obj()], policy=other))

    def test_invalid_configuration_and_clock(self):
        for changes in (dict(confidence_min=True), dict(confidence_min=1.1),
                        dict(track_cooldown_ms=0), dict(max_tracks=False),
                        dict(memory_ttl_ms=100), dict(class_order=("person",))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                config(**changes)
        self.select([obj()])
        self.now = -1
        with self.assertRaises(ValueError):
            self.select([obj(direction="right")])
        self.now = 1
        self.assertIsNotNone(self.select([obj(track="2", cls="car")]))


if __name__ == "__main__":
    unittest.main()
