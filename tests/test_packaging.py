"""#28 empacotamento: arquivos de contêiner sem segredos e probe de saúde.

Os testes estáticos rodam sem extras. Os de probe e falha de configuração
exigem .[api,api-dev]. Nenhum deles constrói imagem nem usa Docker; o build
real é exercitado por `python scripts/smoke.py` (veja docs/packaging.md).
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.util import find_spec
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = all(find_spec(n) for n in ("fastapi", "uvicorn", "httpx2", "trustme", "python_multipart"))


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


class ContainerFilesTests(unittest.TestCase):
    def test_dockerfile_runs_unprivileged_with_healthcheck(self):
        text = read("Dockerfile")
        self.assertRegex(text, r"(?m)^USER sonar$")
        self.assertIn("HEALTHCHECK", text)
        self.assertNotRegex(text, r"(?mi)^\s*(COPY|ADD)\s+.*(\.env|\.pem|\.key|\.pt|\.local|models)")
        self.assertNotRegex(text, r"(?mi)^\s*(ENV|ARG)\s+\S*(TOKEN|SECRET|PASSWORD|KEY)\S*=")
        self.assertNotIn("verify=False", text)
        self.assertNotRegex(text, r"(?i)curl\s+.*(-k|--insecure)")

    def test_dockerignore_keeps_secrets_weights_and_media_out(self):
        entries = {line.strip() for line in read(".dockerignore").splitlines()}
        for required in (".env", ".local/", "models/", "*.pt", "*.pem", "*.key", "videos/",
                         "results/", ".git/"):
            self.assertIn(required, entries)

    def test_compose_is_single_service_loopback_and_read_only_volumes(self):
        text = read("compose.yaml")
        self.assertEqual(re.findall(r"(?m)^  (\w+):$", text), ["api"])
        for forbidden in ("privileged", "network_mode", "depends_on", "mysql", "postgres",
                          "mosquitto", "redis"):
            self.assertNotIn(forbidden, text)
        ports = re.findall(r'(?m)^\s+- "([^"]*:\d+)"$', text)
        self.assertEqual(len(ports), 1)
        self.assertTrue(ports[0].startswith("127.0.0.1:"), ports)
        volumes = re.findall(r"(?m)^\s+- (\S+:/\S+)$", text)
        self.assertEqual(len(volumes), 3)
        for volume in volumes:
            self.assertTrue(volume.endswith(":ro"), volume)
        for hardening in ("read_only: true", "cap_drop:", "no-new-privileges:true",
                          "restart: unless-stopped", "max-size"):
            self.assertIn(hardening, text)

    def test_catalog_override_adds_only_a_read_only_volume(self):
        text = read("compose.catalog.yaml")
        self.assertIn("SONAR_API_CATALOG_DIR: /run/sonar/catalog", text)
        self.assertRegex(text, r"/run/sonar/catalog:ro")
        self.assertNotIn("ports:", text)

    def test_env_example_has_only_placeholders_and_documents_compose_variables(self):
        text = read(".env.example")
        values = dict(line.split("=", 1) for line in text.splitlines()
                      if line and not line.startswith("#") and "=" in line)
        self.assertEqual(values["SONAR_API_BACKEND"], "simulated")
        for key in values:
            self.assertFalse(re.search(r"SECRET|PASSWORD|_TOKEN$", key), key)
        for variable in ("SONAR_HOST_TLS_DIR", "SONAR_HOST_TOKENS_FILE", "SONAR_API_PORT"):
            self.assertIn(variable, text)
        self.assertNotRegex(text, r"[0-9a-f]{64}")

    def test_secrets_and_weights_stay_ignored_by_git(self):
        lines = read(".gitignore").splitlines()
        for pattern in (".env", "*.pem", ".local/", "*.pt"):
            self.assertIn(pattern, lines)


class _Handler(BaseHTTPRequestHandler):
    reply = (200, b'{"status": "ok"}')

    def do_GET(self):
        status, body = self.reply
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to exercise the health probe")
class HealthProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sonar_vision_api.dev_tls import create

        cls.directory = TemporaryDirectory()
        base = Path(cls.directory.name)
        cls.tls, cls.other = create(base / "tls"), create(base / "other")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def serve(self, reply):
        return self.serve_with(type("Handler", (_Handler,), {"reply": reply}))

    def serve_with(self, handler):
        server = HTTPServer(("127.0.0.1", 0), handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.tls["cert"], self.tls["key"])
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop():
            server.shutdown()
            server.server_close()
            thread.join(5)

        self.addCleanup(stop)
        return f"https://localhost:{server.server_port}/healthz"

    def probe(self, url, ca=None):
        from sonar_vision_api.healthcheck import probe

        return probe(url, str(ca or self.tls["ca"]), timeout_s=2)

    def test_healthy_server_validates_certificate(self):
        self.assertIsNone(self.probe(self.serve((200, b'{"status": "ok", "backend": "simulated"}'))))

    def test_unknown_ca_is_rejected(self):
        reason = self.probe(self.serve((200, b'{"status": "ok"}')), ca=self.other["ca"])
        self.assertIn("unreachable", reason)

    def test_wrong_hostname_is_rejected(self):
        url = self.serve((200, b'{"status": "ok"}')).replace("localhost", "127.0.0.2")
        self.assertIsNotNone(self.probe(url))

    def test_bad_status_json_and_oversized_body_are_unhealthy(self):
        for reply in ((500, b'{"status": "ok"}'), (200, b"nao e json"), (200, b'{"status": "down"}'),
                      (200, b"[1]"), (200, b" " * 5000 + b'{"status": "ok"}')):
            with self.subTest(status=reply[0], body=reply[1][:12]):
                self.assertIsNotNone(self.probe(self.serve(reply)))

    def test_redirect_to_plain_http_is_unhealthy_and_not_followed(self):
        hits = []

        class PlainHandler(_Handler):
            def do_GET(self):
                hits.append(self.path)
                super().do_GET()

        plain = HTTPServer(("127.0.0.1", 0), PlainHandler)
        thread = Thread(target=plain.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (plain.shutdown(), plain.server_close(), thread.join(5)))
        target = f"http://127.0.0.1:{plain.server_port}/healthz"

        class RedirectHandler(_Handler):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", target)
                self.send_header("Content-Length", "0")
                self.end_headers()

        self.assertEqual(self.probe(self.serve_with(RedirectHandler)), "status 302")
        self.assertEqual(hits, [])

    def test_probe_refuses_plain_http_without_connecting(self):
        self.assertEqual(self.probe("http://localhost:1/healthz"), "only https:// URLs are accepted")

    def test_connection_refused_and_missing_ca_file(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.assertIn("unreachable", self.probe(f"https://localhost:{port}/healthz"))
        missing = Path(self.directory.name) / "ausente.pem"
        self.assertEqual(self.probe("https://localhost:1/healthz", ca=missing),
                         "cafile unreadable or invalid")

    def test_cli_refuses_plain_http_and_reports_exit_codes(self):
        from sonar_vision_api import healthcheck

        ca = str(self.tls["ca"])
        with self.assertRaises(SystemExit) as raised:
            healthcheck.main(["--cafile", ca, "--url", "http://localhost:8443/healthz"])
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(healthcheck.main(["--cafile", ca, "--url", "https://localhost:1/healthz"]), 1)
        url = self.serve((200, b'{"status": "ok"}'))
        self.assertEqual(healthcheck.main(["--cafile", ca, "--url", url]), 0)

    def test_real_api_health_endpoint_passes_the_probe(self):
        from sonar_vision_integration.server import Harness

        with TemporaryDirectory() as directory, Harness(Path(directory)) as harness:
            url = f"https://localhost:{harness.port}/healthz"
            self.assertIsNone(self.probe(url, ca=harness.tls["ca"]))


@unittest.skipUnless(AVAILABLE, "install .[api,api-dev] to start the entrypoint")
class StartupFailureTests(unittest.TestCase):
    """O contêiner deve falhar cedo, com mensagem clara, em configuração inválida."""

    def run_api(self, **env):
        base = {k: v for k, v in os.environ.items() if not k.startswith("SONAR_API_")}
        base["PYTHONPATH"] = str(ROOT / "src")
        with TemporaryDirectory() as directory:
            cert = Path(directory) / "x.pem"
            cert.write_text("placeholder", encoding="utf-8")
            command = [sys.executable, "-m", "sonar_vision_api",
                       "--certfile", str(cert), "--keyfile", str(cert)]
            return subprocess.run(command, env={**base, **env}, capture_output=True,
                                  text=True, timeout=60)

    def test_missing_configuration_stops_the_process(self):
        result = self.run_api()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SONAR_API_BACKEND and SONAR_API_TOKENS_FILE are required", result.stderr)

    def test_invalid_values_stop_the_process(self):
        with TemporaryDirectory() as directory:
            tokens = Path(directory) / "tokens"
            tokens.write_text("", encoding="utf-8")
            good = {"SONAR_API_BACKEND": "simulated", "SONAR_API_TOKENS_FILE": str(tokens)}
            cases = {
                "backend": {**good, "SONAR_API_BACKEND": "outro"},
                "tokens": {**good, "SONAR_API_TOKENS_FILE": str(Path(directory) / "ausente")},
                "weights": {**good, "SONAR_API_BACKEND": "ultralytics"},
                "timeout": {**good, "SONAR_API_TIMEOUT_MS": "2000"},
                "integer": {**good, "SONAR_API_MAX_PIXELS": "muitos"},
            }
            for name, env in cases.items():
                with self.subTest(name):
                    result = self.run_api(**env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("SONAR_API_", result.stderr)


if __name__ == "__main__":
    unittest.main()
