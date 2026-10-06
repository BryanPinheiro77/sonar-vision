"""Smoke test da imagem Docker (#28): `python scripts/smoke.py`.

Gera CA, certificado e token temporários em .local/smoke (ignorado pelo Git),
constrói a imagem, sobe o serviço com backend simulado, confere healthcheck,
autenticação e uma inferência sintética, e sempre derruba tudo ao final.
Requer Docker Compose v2 e `python -m pip install -e '.[api,api-dev]'`.
Não usa imagens reais, pesos nem rede externa.
"""

import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from api_helpers import jpeg, metadata, multipart  # noqa: E402
from sonar_vision_api.auth import new_token, token_hash  # noqa: E402
from sonar_vision_api.dev_tls import create  # noqa: E402
from sonar_vision_api.healthcheck import probe  # noqa: E402

PROJECT = "sonar-vision-smoke"
WORK = ROOT / ".local" / "smoke"


def free_port() -> int:
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        return probe_socket.getsockname()[1]


def compose(env, *args, check=True):
    return subprocess.run(["docker", "compose", "-p", PROJECT, *args], cwd=ROOT, env=env,
                          check=check, capture_output=False)


def request(port, ca, method, path, token=None, body=None, content_type=None):
    context = ssl.create_default_context(cafile=str(ca))
    connection = http.client.HTTPSConnection("localhost", port, context=context, timeout=5)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def main() -> int:
    if shutil.which("docker") is None:
        print("docker nao encontrado no PATH", file=sys.stderr)
        return 2
    shutil.rmtree(WORK, ignore_errors=True)
    tls = create(WORK / "tls")
    # O usuario do contêiner precisa ler a chave; pasta efêmera e ignorada pelo Git.
    for path in tls.values():
        path.chmod(0o644)
    token = new_token()
    tokens = WORK / "tokens"
    tokens.write_text(f"glasses-01 {token_hash(token)}\n", encoding="utf-8")
    tokens.chmod(0o644)
    port = free_port()
    env = {**os.environ, "SONAR_HOST_TLS_DIR": str(WORK / "tls"),
           "SONAR_HOST_TOKENS_FILE": str(tokens), "SONAR_API_PORT": str(port),
           "SONAR_API_BACKEND": "simulated", "SONAR_IMAGE_TAG": "smoke"}
    failures = []

    def check(name, ok):
        print(f"{'OK  ' if ok else 'FALHA'} {name}")
        if not ok:
            failures.append(name)

    try:
        compose(env, "up", "-d", "--build", "--wait", "--wait-timeout", "120")
        check("healthcheck HTTPS com CA local", probe(f"https://localhost:{port}/healthz",
                                                      str(tls["ca"])) is None)
        status, _ = request(port, tls["ca"], "POST", "/v1/inference")
        check("inferencia sem token e recusada (401)", status == 401)
        body, content_type = multipart(metadata(), jpeg())
        status, raw = request(port, tls["ca"], "POST", "/v1/inference", token, body, content_type)
        data = json.loads(raw) if status == 200 else {}
        check("inferencia sintetica autenticada (200)",
              status == 200 and data.get("observation", {}).get("frame_id") == "1")
        user = subprocess.run(["docker", "compose", "-p", PROJECT, "exec", "-T", "api", "id", "-u"],
                              cwd=ROOT, env=env, capture_output=True, text=True)
        check("processo nao roda como root", user.returncode == 0 and user.stdout.strip() != "0")
        compose(env, "stop", "-t", "15")
        state = subprocess.run(["docker", "compose", "-p", PROJECT, "ps", "-a", "--format", "json"],
                               cwd=ROOT, env=env, capture_output=True, text=True)
        exit_codes = [json.loads(line).get("ExitCode") for line in state.stdout.splitlines() if line]
        # uvicorn encerra graciosamente e relança SIGTERM: 143 e esperado; 137 seria SIGKILL.
        check("parada graciosa por SIGTERM (exit 0 ou 143)", exit_codes in ([0], [143]))
    except subprocess.CalledProcessError as error:
        print(f"FALHA comando: {error.cmd}", file=sys.stderr)
        compose(env, "logs", "--no-color", "--tail", "50", check=False)
        failures.append("comando docker")
    finally:
        compose(env, "down", "-v", "--remove-orphans", check=False)
        shutil.rmtree(WORK, ignore_errors=True)
    print("smoke:", "FALHOU" if failures else "OK")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
