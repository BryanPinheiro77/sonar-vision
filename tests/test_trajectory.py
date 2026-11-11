"""Issue #11: deterministic apparent motion, not real-world collision labels."""

import math
import unittest
from unittest.mock import patch

from sonar_vision.core import Detection, Frame, VisionService
from sonar_vision.trajectory import Motion, TrajectoryConfig, TrajectoryEstimator


def target(t, vx=0, vy=0, growth=0, track="1", cls="person"):
    size = 0.15 * math.exp(growth * t / 2)
    x, y = 0.4 + vx * t, 0.5 + vy * t
    return Detection(cls, 0.9, (x-size/2, y-size/2, x+size/2, y+size/2), track)


class TrajectoryTests(unittest.TestCase):
    def classify(self, times=None, camera="fixed", **motion):
        estimator = TrajectoryEstimator()
        for t in (times if times is not None else [i / 10 for i in range(13)]):
            result = estimator.update(target(t, **motion), round(t * 1000), camera)
        return result

    def test_states_and_both_lateral_directions(self):
        for motion, expected in [({}, "stable"), ({"growth": .3}, "approaching"),
                                 ({"growth": -.3}, "receding"), ({"vx": .2}, "crossing"),
                                 ({"vx": -.2}, "crossing")]:
            with self.subTest(motion=motion):
                self.assertEqual(self.classify(**motion).movement, expected)
        self.assertEqual(self.classify(vx=.2).lateral_direction, "left_to_right")
        self.assertEqual(self.classify(vx=-.2).lateral_direction, "right_to_left")

    def test_capture_time_not_frame_rate(self):
        for fps in (8, 13, 30):
            result = self.classify(times=[i/fps for i in range(round(1.5*fps))], vx=.13)
            self.assertEqual(result.movement, "crossing")
            self.assertAlmostEqual(result.center_velocity_x, .13, places=3)
        result = self.classify(times=[0, .06, .18, .29, .44, .61, .8, 1.01, 1.21], growth=.27)
        self.assertEqual(result.movement, "approaching")

    def test_sparse_history_abstains(self):
        self.assertEqual(self.classify(times=[0, .3, .6, .9], vx=.2).movement, "unknown")

    def test_two_fps_cannot_satisfy_current_window_even_with_perfect_tracks(self):
        result = self.classify(times=[i / 2 for i in range(7)], growth=.3)
        self.assertEqual(result.samples, 3)
        self.assertEqual(result.movement, "unknown")
        self.assertEqual(result.reason, "insufficient_history")
        faster = self.classify(times=[i / 10 for i in range(31)], growth=.3)
        self.assertEqual(faster.movement, "approaching")

    def test_mixed_vertical_and_jitter_abstain(self):
        for kwargs in ({"vx": .2, "growth": .3}, {"vy": .2}):
            self.assertEqual(self.classify(**kwargs).movement, "unknown")
        estimator = TrajectoryEstimator()
        for i in range(13):
            result = estimator.update(target(1, vx=.07 if i % 2 else -.07), i*100, "fixed")
        self.assertEqual(result.movement, "unknown")
        self.assertEqual(result.reason, "unstable_boxes")

    def test_confirmation_delay_is_time_based(self):
        estimator = TrajectoryEstimator()
        first_candidate = first_confirmed = None
        for i in range(20):
            result = estimator.update(target(i/13, growth=.3), round(i*1000/13), "fixed")
            if result.raw_movement == "approaching" and first_candidate is None:
                first_candidate = round(i*1000/13)
            if result.movement == "approaching":
                first_confirmed = round(i*1000/13)
                break
        self.assertIsNotNone(first_confirmed)
        self.assertGreaterEqual(first_confirmed-first_candidate, 400)
        self.assertLessEqual(first_confirmed-first_candidate, 478)

    def test_gap_duplicate_time_and_identity_reset(self):
        for next_time, track, cls in [(2000, "1", "person"), (1200, "1", "person"),
                                       (1300, "2", "person"), (1300, "1", "car")]:
            estimator = TrajectoryEstimator()
            for i in range(13):
                estimator.update(target(i/10, growth=.3), i*100, "fixed")
            result = estimator.update(target(1.3, growth=.3, track=track, cls=cls), next_time, "fixed")
            self.assertEqual(result.movement, "unknown")

    def test_unknown_or_moving_camera_never_declares_target_motion(self):
        for camera in ("unknown", "moving"):
            result = self.classify(camera=camera, growth=.3)
            self.assertEqual(result.movement, "unknown")
            self.assertEqual(result.reason, "camera_not_fixed")
        # An identical zoom pattern is indistinguishable from object growth.
        self.assertEqual(self.classify(camera="fixed", growth=.3).movement, "approaching")

    def test_camera_change_clears_confirmation(self):
        estimator = TrajectoryEstimator()
        for i in range(13):
            estimator.update(target(i/10, growth=.3), i*100, "fixed")
        self.assertEqual(estimator.update(target(1.3), 1300, "moving").movement, "unknown")
        result = estimator.update(target(1.4), 1400, "fixed")
        self.assertEqual(result.samples, 1)
        self.assertEqual(result.movement, "unknown")

    def test_untracked_target_and_config_validation(self):
        self.assertEqual(self.classify(track=None).reason, "no_track")
        for config in ({"min_samples": 1}, {"min_samples": 2.5}, {"max_samples": 3},
                       {"window_seconds": .2}, {"confirmation_seconds": float("nan")},
                       {"lateral_threshold": True}):
            with self.assertRaises(ValueError):
                TrajectoryConfig(**config)

    def test_uncertainty_or_direction_change_restarts_confirmation(self):
        for interruption in (Motion(), Motion(movement="receding"),
                             Motion(movement="crossing", lateral_direction="right_to_left")):
            estimator = TrajectoryEstimator()
            crossing = Motion(movement="crossing", lateral_direction="left_to_right")
            with patch.object(estimator, "_estimate", side_effect=[crossing, interruption, crossing]):
                estimator.update(target(0), 0, "fixed")
                estimator.update(target(.3), 300, "fixed")
                result = estimator.update(target(.4), 400, "fixed")
            self.assertEqual(result.movement, "unknown")
            self.assertEqual(result.confirmation_elapsed_seconds, 0)


class EchoBackend:
    def infer(self, image):
        return image

    def close(self):
        pass


class MotionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.vision = VisionService(EchoBackend)
        self.vision.open("a", "s")

    def frame(self, i, objects=None, device="a", camera="fixed"):
        return self.vision.process(Frame(device, "s", str(i), i*100,
            objects if objects is not None else [target(i/10, growth=.3)], camera_motion=camera))

    def test_multiple_targets_and_contract(self):
        for i in range(13):
            result = self.frame(i, [target(i/10, growth=.3), target(i/10, vx=-.2, track="2")])
        objects = result.observation()["objects"]
        self.assertEqual([o["movement"] for o in objects], ["approaching", "crossing"])
        self.assertTrue(all(o["direction"] == "unknown" for o in objects))
        self.assertEqual(result.motions["2"].lateral_direction, "right_to_left")
        self.assertNotIn("risk", objects[0])
        self.assertNotIn("camera_motion", result.observation())

    def test_loss_reentry_reset_and_session_isolation(self):
        for i in range(13):
            self.frame(i)
        self.vision.open("b", "s")
        self.assertEqual(self.frame(0, device="b").motions["1"].movement, "unknown")
        self.assertEqual(self.frame(13).motions["1"].movement, "approaching")
        self.frame(14, [])
        self.assertEqual(self.frame(15).motions["1"].movement, "unknown")
        self.vision.reset("a", "s")
        self.assertEqual(self.frame(16).motions["1"].movement, "unknown")

    def test_unknown_camera_is_default_for_network_callers(self):
        for i in range(13):
            result = self.vision.process(Frame("a", "s", str(i), i*100, [target(i/10, growth=.3)]))
        self.assertEqual(result.observation()["objects"][0]["movement"], "unknown")
        self.assertEqual(result.motions["1"].reason, "camera_not_fixed")

    def test_gap_and_class_change_clear_history(self):
        self.frame(0)
        self.assertEqual(len(self.frame(10).history["1"]), 1)
        result = self.frame(11, [target(1.1, cls="car")])
        self.assertEqual(len(result.history["1"]), 1)
        self.assertEqual(result.motions["1"].movement, "unknown")


if __name__ == "__main__":
    unittest.main()
