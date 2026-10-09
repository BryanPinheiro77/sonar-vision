import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

AVAILABLE = all(
    importlib.util.find_spec(name)
    for name in ["fastapi", "uvicorn", "httpx2", "trustme"]
)


class EndpointConfigurationTests(unittest.TestCase):
    def load(self):
        spec = importlib.util.spec_from_file_location(
            "endpoint",
            Path(__file__).resolve().parents[1] / "scripts/check_aws_endpoint.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_insecure_or_credential_bearing_url_rejected_before_network(self):
        module = self.load()
        for url in [
            "http://host",
            "https://user:secret@host",
            "https://host/?secret=token",
        ]:
            with self.assertRaises(ValueError):
                module.run_probe(url, "synthetic-token", "unused-ca")

    @unittest.skipUnless(
        AVAILABLE, "install .[api,api-dev] for external endpoint probe"
    )
    def test_peer_validation_authentication_and_public_report(self):
        from sonar_vision_integration.server import Harness
        from sonar_vision_integration.bench import synthetic_jpeg

        module = self.load()
        with (
            TemporaryDirectory() as temp,
            Harness(Path(temp), devices=("glasses-01",)) as server,
        ):
            token = server.tokens["glasses-01"]
            result = module.run_probe(
                server.url, token, server.tls["ca"], jpeg=synthetic_jpeg(False)
            )
            self.assertEqual(len(result["checks"]), 5)
            self.assertTrue(all(x["passed"] for x in result["checks"]))
            for private in [
                token,
                server.url,
                str(temp),
                "tracker_epoch",
                "session_id",
            ]:
                self.assertNotIn(private, json.dumps(result))
            self.assertFalse(result["accuracy_evaluated"])
