"""#23 available capture never overlaps after timeout or exceeds start ceiling."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sonar_vision_integration.cadence import run_available_load
from sonar_vision_integration.client import Discarded


class AvailableCadenceTests(unittest.TestCase):
    def run_case(self, timeout=False, duration=0.5):
        clock = [0.0]
        starts = []

        class Client:
            timeout_s = 0.2
            busy_until = 0

            @property
            def busy(self):
                return clock[0] < self.busy_until

            def restart(self):
                pass

            def capture(self, jpeg):
                assert not self.busy
                starts.append(clock[0])
                return SimpleNamespace(
                    session_id="synthetic", frame_id=str(len(starts)), jpeg=jpeg
                )

            def send(self, capture):
                clock[0] += 0.15
                if timeout and len(starts) == 1:
                    self.busy_until = clock[0] + 0.1
                    raise Discarded("timeout")
                return {"observation": {"objects": []}}

        with (
            patch(
                "sonar_vision_integration.cadence.perf_counter",
                side_effect=lambda: clock[0],
            ),
            patch(
                "sonar_vision_integration.cadence.sleep",
                side_effect=lambda n: clock.__setitem__(0, clock[0] + n),
            ),
        ):
            report = run_available_load(
                Client(),
                [
                    {
                        "clip_id": "synthetic",
                        "jpeg": b"fixture",
                        "source_timestamp_ms": 0,
                    }
                ],
                fps=10,
                duration_s=duration,
            )
        return starts, report

    def test_no_overlap_and_rate_ceiling(self):
        starts, r = self.run_case()
        self.assertEqual(starts, [0, 0.15, 0.3, 0.44999999999999996])
        self.assertEqual(r["admitted_within_offering_window"], 3)
        self.assertEqual(r["attempt_outcomes"], {"admitted": 4})
        self.assertTrue(r["rate_is_capture_start_ceiling"])
        self.assertIsNone(r["offered_opportunities"])

    def test_timeout_transport_still_busy_waits_before_fresh_capture(self):
        starts, r = self.run_case(timeout=True)
        self.assertGreaterEqual(starts[1], 0.25)
        self.assertEqual(r["attempt_outcomes"]["timeout"], 1)
        self.assertGreater(r["transport_busy_poll_count"], 0)

    def test_report_drains_late_transport_without_new_capture_after_window(self):
        starts, r = self.run_case(timeout=True, duration=0.2)
        self.assertEqual(len(starts), 1)
        self.assertGreaterEqual(r["wall_s_including_drain"], 0.25)
        self.assertEqual(r["attempt_outcomes"], {"timeout": 1})


class AvailableHttpsTests(unittest.TestCase):
    def test_opt_in_real_https_report_marks_rate_ceiling_and_preserves_default(self):
        import importlib.util

        if not all(
            importlib.util.find_spec(x)
            for x in ("fastapi", "uvicorn", "httpx2", "trustme")
        ):
            self.skipTest("install .[api,api-dev] for available-cadence HTTPS test")
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from sonar_vision_integration.server import Harness
        from sonar_vision_integration.remote_load import run
        from sonar_vision_integration.bench import synthetic_jpeg

        with (
            TemporaryDirectory() as temp,
            Harness(Path(temp), devices=("glasses-01",)) as server,
        ):
            for mode in ("periodic", "when_available"):
                r = run(
                    endpoint=server.url,
                    credentials=list(server.tokens.items()),
                    ca_file=server.tls["ca"],
                    fps=10,
                    duration_s=0.4,
                    frames=[
                        {
                            "clip_id": "generated",
                            "jpeg": synthetic_jpeg(False),
                            "source_timestamp_ms": 0,
                        }
                    ],
                    source_id="synthetic",
                    scheduling=mode,
                )
                self.assertEqual(r["configuration"]["scheduling"], mode)
                self.assertEqual(
                    r["configuration"]["offered_rate_is_start_ceiling"],
                    mode == "when_available",
                )
                self.assertGreater(r["attempt_outcomes"].get("admitted", 0), 0)
                self.assertFalse(r["configuration"]["queue"])
                self.assertTrue(
                    all(x["outcome"] == "admitted" for x in r["devices"][0]["rows"])
                )
