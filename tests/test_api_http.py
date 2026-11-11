"""#24 HTTP adapter through FastAPI's TestClient (requires .[api,api-dev])."""

from importlib.util import find_spec
import json
import logging
import unittest

from api_helpers import jpeg, metadata, multipart

AVAILABLE = all(find_spec(name) for name in ("fastapi", "httpx2", "python_multipart"))
TOKEN = "test-token-not-a-secret"


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to exercise the HTTP adapter")
class InferenceHttpTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.app import create_app
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.service import InferenceService, header_only_decoder

        self.service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                        timeout_ms=1500)
        self.addCleanup(self.service.close)
        app = create_app(self.service, TokenStore({"glasses-01": token_hash(TOKEN)}),
                         backend="simulated", max_body_bytes=4096, max_pixels=640 * 480)
        self.client = TestClient(app, raise_server_exceptions=False)

    def post(self, body=None, content_type=None, token=TOKEN, **headers):
        if body is None:
            body, content_type = multipart(metadata(), jpeg())
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = content_type or "application/json"
        return self.client.post("/v1/inference", content=body, headers=headers)

    def assertError(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json(), {"error": {"code": code}})

    def test_success_matches_contract_envelope(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "application/json")
        body = response.json()
        self.assertEqual(set(body), {"observation", "audio"})
        self.assertIsNone(body["audio"])
        self.assertEqual(body["observation"]["type"], "visual_observation")
        self.assertLessEqual(len(response.content), 16384)

    def test_authentication_happens_before_reading_upload(self):
        response = self.post(token=None)
        self.assertError(response, 401, "unauthorized")
        self.assertEqual(response.headers["www-authenticate"], "Bearer")
        self.assertError(self.post(token="wrong"), 401, "unauthorized")

    def test_media_type_size_and_format_errors(self):
        self.assertError(self.post(b"{}", "application/json"), 415, "unsupported_media_type")
        big, ctype = multipart(metadata(), jpeg() + b"\x00" * 5000)
        self.assertError(self.post(big, ctype), 413, "payload_too_large")
        huge, ctype = multipart(metadata(), jpeg(481, 640))
        self.assertError(self.post(huge, ctype), 413, "payload_too_large")
        png, ctype = multipart(metadata(), b"\x89PNG\r\n\x1a\n")
        self.assertError(self.post(png, ctype), 415, "unsupported_media_type")
        typed, ctype = multipart(metadata(), jpeg(), image_type="image/png")
        self.assertError(self.post(typed, ctype), 415, "unsupported_media_type")

    def test_malformed_multipart_and_metadata(self):
        broken, ctype = multipart(metadata(), jpeg())
        self.assertError(self.post(broken[:-20], ctype), 400, "invalid_request")
        extra = (b"--sonarboundary\r\nContent-Disposition: form-data; name=\"image\"\r\n"
                 b"Content-Type: image/jpeg\r\n\r\nx\r\n")
        duplicate, ctype = multipart(metadata(), jpeg(), extra=extra)
        self.assertError(self.post(duplicate, ctype), 400, "invalid_request")
        bad_meta, ctype = multipart(metadata(extra=1), jpeg())
        self.assertError(self.post(bad_meta, ctype), 400, "invalid_request")
        no_boundary = self.post(broken, "multipart/form-data")
        self.assertError(no_boundary, 415, "unsupported_media_type")

    def test_replay_and_busy_codes(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertError(self.post(), 400, "invalid_request")
        self.service._busy = True
        try:
            body, ctype = multipart(metadata(frame_id="2", captured_at_ms=2000), jpeg())
            self.assertError(self.post(body, ctype), 429, "busy")
        finally:
            self.service._busy = False

    def test_health_declares_simulated_backend_and_unknown_routes_are_structured(self):
        self.assertEqual(self.client.get("/healthz").json()["backend"], "simulated")
        self.assertError(self.client.get("/v1/inference"), 405, "method_not_allowed")
        self.assertError(self.client.get("/docs"), 404, "not_found")

    def test_logs_have_timings_but_no_token_or_image(self):
        with self.assertLogs("sonar_vision_api", logging.INFO) as logs:
            self.post()
        lines = [json.loads(r.getMessage()) for r in logs.records
                 if r.getMessage().startswith("{")]
        request = [line for line in lines if line["event"] == "inference_request"][-1]
        self.assertEqual(request["status"], 200)
        self.assertEqual(request["device_id"], "glasses-01")
        for key in ("read_ms", "decode_ms", "inference_ms", "encode_ms", "total_ms"):
            self.assertIn(key, request)
        output = "\n".join(r.getMessage() for r in logs.records)
        self.assertNotIn(TOKEN, output)
        self.assertNotIn("JFIF", output)


if __name__ == "__main__":
    unittest.main()
