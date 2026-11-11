"""#24 real HTTPS: the client validates the server certificate (requires .[api,api-dev])."""

from importlib.util import find_spec
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import threading
import time
import unittest

from api_helpers import jpeg, metadata, multipart

AVAILABLE = all(find_spec(n) for n in ("fastapi", "uvicorn", "httpx2", "trustme", "python_multipart"))
TOKEN = "tls-test-token-not-a-secret"


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to exercise HTTPS")
class HttpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import uvicorn
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.dev_tls import create
        from sonar_vision_api.service import InferenceService, header_only_decoder

        cls.directory = TemporaryDirectory()
        cls.paths = create(Path(cls.directory.name) / "tls")
        cls.other = create(Path(cls.directory.name) / "other")  # unrelated CA
        cls.service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                       timeout_ms=1500)
        app = create_app(cls.service, TokenStore({"glasses-01": token_hash(TOKEN)}),
                         backend="simulated", max_body_bytes=4096, max_pixels=640 * 480)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            cls.port = probe.getsockname()[1]
        config = uvicorn.Config(app, host="127.0.0.1", port=cls.port, log_level="warning",
                                ssl_certfile=str(cls.paths["cert"]),
                                ssl_keyfile=str(cls.paths["key"]))
        cls.server = uvicorn.Server(config)
        cls.thread = threading.Thread(target=cls.server.run, daemon=True)
        cls.thread.start()
        deadline = time.monotonic() + 10
        while not cls.server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        if not cls.server.started:
            raise RuntimeError("HTTPS test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(10)
        cls.service.close()
        cls.directory.cleanup()

    def post(self, verify):
        import httpx2 as httpx

        body, ctype = multipart(metadata(frame_id=str(time.monotonic_ns())), jpeg())
        with httpx.Client(verify=verify, timeout=2.0) as client:
            return client.post(f"https://127.0.0.1:{self.port}/v1/inference", content=body,
                               headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": ctype})

    def test_trusted_ca_succeeds(self):
        import ssl

        context = ssl.create_default_context(cafile=str(self.paths["ca"]))
        response = self.post(context)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["audio"])

    def test_untrusted_ca_is_refused_by_client(self):
        import ssl

        import httpx2 as httpx

        context = ssl.create_default_context(cafile=str(self.other["ca"]))
        with self.assertRaises(httpx.ConnectError):
            self.post(context)

    def test_plain_http_is_not_served(self):
        import httpx2 as httpx

        with httpx.Client(timeout=2.0) as client, self.assertRaises(httpx.HTTPError):
            client.get(f"http://127.0.0.1:{self.port}/healthz")


if __name__ == "__main__":
    unittest.main()
