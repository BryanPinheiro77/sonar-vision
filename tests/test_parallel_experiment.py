"""#22 operator concurrency: preserve ownership and tracker state on failures."""
import importlib.util
from pathlib import Path
from threading import Event, Lock, Thread
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sonar_vision.core import Busy


@unittest.skipUnless(importlib.util.find_spec("numpy"), "install vision for CPU experiment")
class ParallelFailureTests(unittest.TestCase):
    def setUp(self):
        import numpy as np

        spec = importlib.util.spec_from_file_location(
            "parallel_experiment", Path(__file__).resolve().parents[1]
            / "scripts/benchmark_parallel_api.py",
        )
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.image = np.zeros((2, 2, 3), dtype=np.uint8)

    def primary_stub(self):
        class Primary:
            def __init__(self, predict, config):
                self.predict, self._shape, self.updates = predict, None, 0

            def infer(self, image):
                self.predict(image)
                self.updates += 1
                return []

            def close(self):
                pass

        return Primary

    def test_general_failure_keeps_global_ownership_until_stair_worker_stops(self):
        started, release, finished = Event(), Event(), Event()
        errors = []

        def predict(model, image):
            if model == "general":
                raise ValueError("injected general failure")
            started.set()
            if not release.wait(5):
                raise RuntimeError("test worker not released")
            return object()

        with ThreadPoolExecutor(max_workers=2) as pool:
            owner = SimpleNamespace(frame_lock=Lock(), pool=pool, config=None,
                                    _model="general", _direction_model="stairs",
                                    predict_model=predict)
            with patch.object(self.module, "UltralyticsBackend", self.primary_stub()):
                backend = self.module.ParallelBackend(owner)
                other_session = self.module.ParallelBackend(owner)

            def run():
                try:
                    backend.infer(self.image)
                except ValueError as error:
                    errors.append(str(error))
                finally:
                    finished.set()

            worker = Thread(target=run)
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                self.assertFalse(finished.wait(.05))
                with self.assertRaises(Busy):
                    other_session.infer(self.image)
            finally:
                release.set()
                worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, ["injected general failure"])
            self.assertFalse(owner.frame_lock.locked())
            self.assertIsNone(backend.general_result)
            self.assertEqual(backend.primary.updates, 0)

    def test_stair_failure_keeps_primary_tracker_update_and_releases_ownership(self):
        def predict(model, image):
            if model == "stairs":
                raise ValueError("injected stair failure")
            return object()

        with ThreadPoolExecutor(max_workers=2) as pool:
            owner = SimpleNamespace(frame_lock=Lock(), pool=pool, config=None,
                                    _model="general", _direction_model="stairs",
                                    predict_model=predict)
            with patch.object(self.module, "UltralyticsBackend", self.primary_stub()):
                backend = self.module.ParallelBackend(owner)
            with self.assertRaisesRegex(ValueError, "injected stair failure"):
                backend.infer(self.image)
            self.assertEqual(backend.primary.updates, 1)
            self.assertFalse(owner.frame_lock.locked())
            backend.close()
            with self.assertRaisesRegex(RuntimeError, "backend closed"):
                backend.infer(self.image)


if __name__ == "__main__":
    unittest.main()
