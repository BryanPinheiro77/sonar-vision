"""#22 real external TLS, private report and operator log correlation."""

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sonar_vision_integration.remote_load import (
    attach_server_log, measurement_continuity, run, validate,
)

AVAILABLE = all(
    importlib.util.find_spec(x) for x in ("fastapi", "uvicorn", "httpx2", "trustme")
)


class RemoteConfigurationTests(unittest.TestCase):
    def test_suspended_client_is_not_a_continuous_capacity_measurement(self):
        first = {"sampled_at_utc": "2026-10-07T12:00:00+00:00", "elapsed_s": 0}
        resumed = {"sampled_at_utc": "2026-10-07T12:02:01+00:00", "elapsed_s": 1}
        result = measurement_continuity({"samples": [first, resumed]})
        self.assertFalse(result["continuous"])
        self.assertEqual(result["maximum_sample_clock_difference_s"], 120)
        normal = {**resumed, "elapsed_s": 121}
        self.assertTrue(measurement_continuity({"samples": [first, normal]})["continuous"])
        self.assertIsNone(measurement_continuity({"samples": []})["continuous"])

    def test_bad_destination_credentials_and_load_fail_before_network(self):
        for endpoint in (
            "http://host",
            "https://user:secret@host",
            "https://host/v1/inference",
            "https://host/?secret=token",
            "https://host/#token",
        ):
            with self.assertRaises(ValueError):
                validate(endpoint, [("device", "private-token")], 10, 1, 0, "aligned")
        for credentials in ([], [("a", "x"), ("b", "x")], [("a", "x"), ("a", "y")]):
            with self.assertRaises(ValueError):
                validate("https://host", credentials, 10, 1, 0, "aligned")
        with self.assertRaises(ValueError):
            validate("https://host", [("a", "x")], float("nan"), 1, 0, "aligned")

    def test_log_association_excludes_other_runs_and_marks_missing(self):
        report = {
            "devices": [
                {
                    "device": "d",
                    "rows": [
                        {"session_id": "s", "frame_id": "1"},
                        {"session_id": "s", "frame_id": "2"},
                    ],
                }
            ]
        }
        with TemporaryDirectory() as temp:
            path = Path(temp) / "server.log"
            event = {
                "event": "inference_request",
                "device_id": "d",
                "session_id": "s",
                "frame_id": "1",
                "status": 200,
                "inference_ms": 25,
            }
            other = {**event, "session_id": "other"}
            path.write_text(
                "uvicorn startup\n"
                + json.dumps(event)
                + "\n"
                + json.dumps(other)
                + "\n"
            )
            attach_server_log(report, path)
            self.assertEqual(report["server_observations"]["matched"], 1)
            self.assertEqual(report["server_observations"]["missing"], 1)
            self.assertEqual(
                report["server_observations"]["stages"]["inference_ms"]["p95_ms"], 25
            )
            path.write_text(json.dumps(event) + "\n" + json.dumps(event) + "\n")
            with self.assertRaisesRegex(ValueError, "duplicate_server_request"):
                attach_server_log(report, path)


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] for remote HTTPS benchmark")
class RemoteHttpsTests(unittest.TestCase):
    def test_external_endpoint_reports_each_client_without_secrets_or_server_rss(self):
        from sonar_vision_integration.bench import synthetic_jpeg
        from sonar_vision_integration.server import Harness

        with TemporaryDirectory() as temp, Harness(Path(temp)) as server:
            report = run(
                endpoint=server.url,
                credentials=list(server.tokens.items()),
                ca_file=server.tls["ca"],
                frames=[
                    {
                        "clip_id": "synthetic",
                        "jpeg": synthetic_jpeg(False),
                        "source_timestamp_ms": 0,
                    }
                ],
                source_id="generated-synthetic",
                fps=10,
                duration_s=0.3,
                warmup_s=0.1,
                phase="staggered",
            )
            self.assertEqual(report["kind"], "external_https_offered_load")
            self.assertEqual(len(report["devices"]), 2)
            self.assertGreater(report["attempt_outcomes"].get("admitted", 0), 0)
            self.assertIn("client_process_resources", report)
            self.assertIsNone(report["server_observations"])
            self.assertFalse(report["acceptance_evaluated"])
            text = json.dumps(report)
            for token in server.tokens.values():
                self.assertNotIn(token, text)
            self.assertNotIn(server.url, text)
            self.assertNotIn(str(temp), text)

    def test_public_ca_store_is_used_when_no_local_ca_is_supplied(self):
        from sonar_vision_integration.client import DeviceClient
        import ssl

        with patch(
            "sonar_vision_integration.client.ssl.create_default_context",
            wraps=ssl.create_default_context,
        ) as context:
            client = DeviceClient("https://example.com", "fixture-token", None)
            client.close()
        context.assert_called_once_with(cafile=None)


if __name__ == "__main__":
    unittest.main()
