"""Viewer access is separate from device writes; fixtures are synthetic."""
import base64
from importlib.util import find_spec
import unittest
from unittest.mock import patch

from sonar_vision_api.demo import DemoSettings, DemoStore
from sonar_vision_api.viewer_auth import ViewerAuth, make_verifier

PASSWORD = "synthetic-viewer-password"
VERIFIER = make_verifier(PASSWORD)


def basic(password=PASSWORD, username="sonar"):
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


class ViewerCredentialTests(unittest.TestCase):
    def test_password_verifier_and_cache_never_contain_plaintext(self):
        auth = ViewerAuth(VERIFIER)
        self.assertNotIn(PASSWORD, VERIFIER)
        self.assertFalse(auth.cached(basic()))
        self.assertTrue(auth.authenticate(basic()))
        self.assertTrue(auth.cached(basic()))
        with patch("sonar_vision_api.viewer_auth.hashlib.pbkdf2_hmac", side_effect=AssertionError):
            self.assertTrue(auth.authenticate(basic()))
        self.assertNotIn(PASSWORD, repr(vars(auth)))

    def test_bad_password_username_and_malformed_auth_never_enter_cache(self):
        auth = ViewerAuth(VERIFIER)
        for header in (None, "", "Bearer device-token", "Basic !!!!", "Basic \u00e9",
                       "Basic " + "a" * 1100, basic("wrong"), basic(username="wrong")):
            with self.subTest(header=str(header)[:30]):
                self.assertFalse(auth.authenticate(header))
                self.assertFalse(auth.cached(header))

    def test_hash_format_fails_closed_and_salts_differ(self):
        self.assertNotEqual(VERIFIER, make_verifier(PASSWORD))
        for verifier in ("", "a" * 64, VERIFIER.replace("600000", "1"), None):
            with self.assertRaises(ValueError):
                ViewerAuth(verifier)
        for password in ("short", "a" * 257, None):
            with self.assertRaises(ValueError):
                make_verifier(password)

    def test_session_signature_expiry_restart_and_unicode_fail_closed(self):
        auth = ViewerAuth(VERIFIER)
        with patch("sonar_vision_api.viewer_auth.time.time", return_value=1000):
            cookie = auth.issue_session()
            self.assertTrue(auth.valid_session(cookie))
            for bad in (None, "", "é", "a"*161, cookie+"x", "é"+cookie[1:], cookie[:-1]+"é"):
                self.assertFalse(auth.valid_session(bad))
            self.assertFalse(ViewerAuth(VERIFIER).valid_session(cookie))
        with patch("sonar_vision_api.viewer_auth.time.time", return_value=1000+28800):
            self.assertFalse(auth.valid_session(cookie))
        with patch("sonar_vision_api.viewer_auth.time.time", return_value=999):
            self.assertFalse(auth.valid_session(cookie))

    def test_settings_opt_in_keeps_network_default_and_rejects_bad_verifier(self):
        env = {"SONAR_DEMO_ENABLED": "1", "SONAR_DEMO_DEVICE_ID": "glasses-01",
               "SONAR_DEMO_SESSION_ID": "boot-1", "SONAR_DEMO_SOURCE_KIND": "simulated"}
        self.assertIsNone(DemoSettings.from_env(env).viewer_password_verifier)
        settings = DemoSettings.from_env({**env, "SONAR_DEMO_VIEWER_PASSWORD_VERIFIER": VERIFIER})
        self.assertEqual(settings.viewer_password_verifier, VERIFIER)
        with self.assertRaises(ValueError):
            DemoSettings.from_env({**env, "SONAR_DEMO_VIEWER_PASSWORD_VERIFIER": "invalid"})


AVAILABLE = all(find_spec(name) for name in ("fastapi", "httpx2", "python_multipart"))


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] for HTTP tests")
class ViewerHttpTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from sonar_vision.benchmark import SyntheticBackend
        from sonar_vision.core import VisionService
        from sonar_vision_api.auth import TokenStore, token_hash
        from sonar_vision_api.app import create_app
        from sonar_vision_api.service import InferenceService, header_only_decoder
        self.now = 10
        self.store = DemoStore(DemoSettings("glasses-01", "boot-1", "simulated",
                                           viewer_password_verifier=VERIFIER), clock=lambda: self.now)
        service = InferenceService(VisionService(SyntheticBackend), header_only_decoder,
                                   timeout_ms=1500, demo=self.store)
        self.addCleanup(service.close)
        app = create_app(service, TokenStore({"glasses-01": token_hash("synthetic-device-token")}),
                         backend="simulated", max_body_bytes=4096, max_pixels=640 * 480)
        self.client = TestClient(app, client=("203.0.113.10", 40000))
        self.viewer = {"Cookie": "sonar_viewer=" + self.store.viewer_auth.issue_session()}
        self.device = {"Authorization": "Bearer synthetic-device-token"}

    def test_every_viewer_surface_requires_password_even_on_an_allowed_network(self):
        paths = ("/demo", "/demo/history", "/demo/assets/panel.js",
                 "/v1/demo/snapshot", "/v1/demo/image?frame_id=1&sha256=" + "a" * 64,
                 "/v1/demo/history", "/v1/demo/history/round/download",
                 "/v1/demo/history/round/frames/sample")
        for path in paths:
            self.now += 1
            response = self.client.get(path, follow_redirects=False)
            self.assertEqual(response.status_code, 303 if path in ("/demo", "/demo/history") else 401, path)
            self.assertNotIn("www-authenticate", response.headers)
            self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.client._transport.client = ("127.0.0.1", 40000)
        self.now += 1
        self.assertEqual(self.client.get("/demo", follow_redirects=False).status_code, 303)

    def test_viewer_from_another_network_can_read_without_device_token(self):
        for path in ("/demo", "/demo/history", "/demo/assets/panel.css", "/v1/demo/snapshot"):
            response = self.client.get(path, headers=self.viewer)
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn(PASSWORD, response.text)
            self.assertNotIn("synthetic-device-token", response.text)

    def test_device_token_is_not_viewer_access_and_viewer_cannot_write(self):
        self.assertEqual(self.client.get("/demo", headers=self.device, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post("/v1/demo/tof", headers=self.viewer, json={}).status_code, 401)
        self.assertEqual(self.client.delete("/v1/demo/session", headers=self.viewer).status_code, 401)
        self.assertEqual(self.client.post("/v1/inference", headers=self.viewer, content=b"bad").status_code, 401)

    def test_form_login_cookie_expiry_tampering_and_logout(self):
        self.client.base_url = "https://testserver"
        response = self.client.get("/demo", follow_redirects=False)
        self.assertEqual(response.headers["location"], "/demo/login")
        self.assertEqual(self.client.get("/demo/login").status_code, 200)
        for asset in ("login.css", "login.js", "logo.jpeg", "favicon.png"):
            self.assertEqual(self.client.get("/demo/assets/" + asset).status_code, 200)
        credentials = {"username": "sonar", "password": PASSWORD}
        self.assertEqual(self.client.post("/demo/login", json=credentials).status_code, 403)
        response = self.client.post("/demo/login", json=credentials, headers={"Origin": "https://testserver"})
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["set-cookie"]
        for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Max-Age=28800"):
            self.assertIn(attribute, cookie)
        token = self.client.cookies.get("sonar_viewer")
        self.assertTrue(self.store.viewer_auth.valid_session(token))
        self.assertFalse(self.store.viewer_auth.valid_session(token + "x"))
        with patch("sonar_vision_api.viewer_auth.time.time", return_value=10**12):
            self.assertFalse(self.store.viewer_auth.valid_session(token))
        for path in ("/demo", "/v1/demo/snapshot", "/demo/assets/panel.js"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.post("/v1/demo/tof", json={}).status_code, 401)
        self.assertEqual(self.client.post("/demo/logout", headers={"Origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.client.post("/demo/logout", headers={"Origin": "https://testserver"}).status_code, 204)
        self.assertEqual(self.client.get("/v1/demo/snapshot").status_code, 401)

    def test_public_device_ingestion_still_requires_bearer(self):
        tof = {"version": "demo-tof-1", "session_id": "boot-1", "sequence": "1",
               "captured_at_ms": 10, "distance_mm": 1250, "valid": True, "quality": "good",
               "sector": "all", "zone": None, "aggregation": "min_valid_8x8"}
        self.assertEqual(self.client.post("/v1/demo/tof", json=tof).status_code, 401)
        self.assertEqual(self.client.post("/v1/demo/tof", headers=self.device, json=tof).status_code, 204)

    def test_login_is_throttled_without_blocking_valid_cookie(self):
        origin = {"Origin": "http://testserver"}
        bad = {"username": "sonar", "password": "wrong"}
        for _ in range(2):
            self.assertEqual(self.client.post("/demo/login", headers=origin, json=bad).status_code, 401)
        response = self.client.post("/demo/login", headers=origin, json=bad)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "2")
        self.assertEqual(self.client.get("/demo/assets/panel.js", headers=self.viewer).status_code, 200)
        self.now += 1
        self.assertEqual(self.client.post("/demo/login", headers=origin, json=bad).status_code, 401)

    def test_rotating_verifier_rejects_existing_cookie(self):
        self.assertEqual(self.client.get("/demo", headers=self.viewer).status_code, 200)
        self.store.viewer_auth = ViewerAuth(make_verifier("new-synthetic-password"))
        self.assertEqual(self.client.get("/demo", headers=self.viewer, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post("/demo/login", headers={"Origin": "http://testserver"},
            json={"username": "sonar", "password": PASSWORD}).status_code, 401)

    def test_basic_does_not_bypass_form_or_logout(self):
        self.assertEqual(self.client.get("/demo", headers={"Authorization": basic()}, follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.get("/v1/demo/snapshot", headers={"Authorization": basic()}).status_code, 401)

    def test_login_rejects_invalid_wire_and_cross_origin(self):
        origin = {"Origin": "http://testserver", "Content-Type": "application/json"}
        bodies = [b"null", b"[]", b"{", b"{\"username\":1,\"password\":\"x\"}",
                  b'{"username":"sonar","password":"a","password":"b"}',
                  b'{"username":"sonar","password":NaN}',
                  b'{"username":"sonar","password":"x","extra":true}',
                  b'{"username":"","password":"x"}',
                  b'{"username":"sonar","password":"' + b'x'*257 + b'"}', b'\xff']
        for raw in bodies:
            self.now += 1
            with self.subTest(raw=raw[:40]):
                self.assertEqual(self.client.post("/demo/login", headers=origin, content=raw).status_code, 400)
        self.now += 1
        self.assertEqual(self.client.post("/demo/login", headers=origin, content=b"x"*2049).status_code, 413)
        self.now += 1
        self.assertEqual(self.client.post("/demo/login", headers={"Origin": "http://testserver"}, content=b"x").status_code, 415)
        self.assertEqual(self.client.post("/demo/login", headers={"Origin": "https://evil.example"}, json={}).status_code, 403)

    def test_head_and_malformed_cookies_cannot_read(self):
        for cookie in ("", "x", "1.abc.def", "x"*200, "1." + "a"*32 + "." + "b"*64):
            with self.subTest(cookie=cookie[:30]):
                self.assertEqual(self.client.get("/v1/demo/snapshot", headers={"Cookie": "sonar_viewer=" + cookie}).status_code, 401)
        self.assertIn(self.client.head("/v1/demo/snapshot").status_code, (401,))

    def test_legacy_cidr_mode_does_not_expose_login_or_write(self):
        self.store.viewer_auth = None
        self.assertEqual(self.client.get("/demo/login").status_code, 403)
        self.assertEqual(self.client.post("/demo/login", json={}).status_code, 404)
        self.client._transport.client = ("127.0.0.1", 40000)
        response = self.client.get("/demo")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="logout" hidden', response.text)
        self.assertEqual(self.client.get("/demo/login", follow_redirects=False).status_code, 303)


if __name__ == "__main__":
    unittest.main()
