"""#52 opt-in CPU container smoke; trusted weights mounted, never downloaded.

Requires .[vision,api,api-dev], Docker; generates only blank synthetic pixels.
Temporary TLS/token/diagnostics are removed; optional aggregate report is private.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from smoke import ROOT, free_port, request
from sonar_vision_api.auth import new_token, token_hash
from sonar_vision_api.dev_tls import create
from sonar_vision_api.healthcheck import probe
from sonar_vision_api.runtime_options import file_hash
from api_helpers import metadata, multipart


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--stair-weights", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.weights.is_file() or not args.stair_weights.is_file():
        parser.error("trusted local weights required")
    if args.report and args.report.exists():
        parser.error("report must be new")
    import cv2
    import numpy as np

    checks = {}

    def check(name, ok):
        checks[name] = bool(ok)
        print(("OK " if ok else "FAIL ") + name, flush=True)
        if not ok:
            raise RuntimeError(name)

    (ROOT / ".local").mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="sonar52-", dir=ROOT / ".local") as temporary:
        work = Path(temporary)
        tls = create(work / "tls")
        for path in tls.values():
            path.chmod(0o644)
        token = new_token()
        tokens = work / "tokens"
        tokens.write_text("smoke-device " + token_hash(token) + "\n")
        tokens.chmod(0o644)
        models = work / "models"
        models.mkdir()
        # Explicit copies only inside an ephemeral directory excluded from build.
        shutil.copyfile(args.weights, models / "general.pt")
        shutil.copyfile(args.stair_weights, models / "stairs.pt")
        evaluation = work / "evaluation"
        evaluation.mkdir()
        audio = dict(
            confidence_min=0.5,
            track_cooldown_ms=2000,
            semantic_cooldown_ms=10000,
            memory_ttl_ms=30000,
            max_tracks=32,
            max_semantics=32,
            class_order=[
                "person",
                "car",
                "motorcycle",
                "bus",
                "bicycle",
                "chair",
                "dining_table",
                "dog",
                "stairs",
            ],
        )
        (evaluation / "audio.json").write_text(json.dumps(audio))
        diagnostics = work / "diagnostics"
        diagnostics.mkdir(mode=0o777)
        diagnostics.chmod(
            0o777
        )  # Ephemeral synthetic results only; portable Docker UID.
        port = free_port()
        env = {
            **{k: v for k, v in os.environ.items() if not k.startswith("SONAR_")},
            "SONAR_HOST_TLS_DIR": str(work / "tls"),
            "SONAR_HOST_TOKENS_FILE": str(tokens),
            "SONAR_HOST_MODELS_DIR": str(models),
            "SONAR_HOST_EVALUATION_DIR": str(evaluation),
            "SONAR_HOST_DIAGNOSTICS_DIR": str(diagnostics),
            "SONAR_API_PORT": str(port),
            "SONAR_API_BACKEND": "ultralytics",
            "SONAR_BUILD_EXTRAS": "api,vision",
            "SONAR_IMAGE_TAG": "smoke-vision-52",
            "SONAR_API_WEIGHTS_IN_CONTAINER": "/models/general.pt",
            "SONAR_API_STAIR_WEIGHTS_IN_CONTAINER": "/models/stairs.pt",
            "SONAR_API_WEIGHTS_SHA256": file_hash(args.weights),
            "SONAR_API_STAIR_WEIGHTS_SHA256": file_hash(args.stair_weights),
        }
        if sys.platform.startswith("linux") and os.getuid() != 0:
            env["SONAR_UID"], env["SONAR_GID"] = str(os.getuid()), str(os.getgid())
            diagnostics.chmod(0o700)
        project = "sonar-vision-52-" + os.urandom(4).hex()

        def compose(*parts, check=True):
            return subprocess.run(
                [
                    "docker",
                    "compose",
                    "-p",
                    project,
                    "-f",
                    "compose.yaml",
                    "-f",
                    "compose.evaluation.yaml",
                    *parts,
                ],
                cwd=ROOT,
                env=env,
                check=check,
                capture_output=True,
                text=True,
            )

        def post(frame, session="smoke-boot"):
            body, ctype = multipart(metadata(session, str(frame), 1000 + frame), jpeg)
            return request(port, tls["ca"], "POST", "/v1/inference", token, body, ctype)

        ok, jpeg = cv2.imencode(".jpg", np.zeros((480, 640, 3), dtype=np.uint8))
        assert ok
        jpeg = jpeg.tobytes()
        try:
            print("Building CPU vision image and starting both models...", flush=True)
            compose("up", "-d", "--build", "--wait", "--wait-timeout", "180")
            check(
                "health_tls",
                probe(f"https://localhost:{port}/healthz", str(tls["ca"])) is None,
            )
            check(
                "unknown_ca_refused",
                probe(
                    f"https://localhost:{port}/healthz",
                    str(create(work / "other")["ca"]),
                )
                is not None,
            )
            check(
                "unauthorized_401",
                request(port, tls["ca"], "POST", "/v1/inference")[0] == 401,
            )
            status, body = post(1)
            check("real_inference_200", status == 200)
            value = json.loads(body)
            check(
                "wire_without_boxes",
                all("box" not in x for x in value["observation"]["objects"]),
            )
            check("blank_no_audio", value["audio"] is None)
            epoch = value["observation"]["tracker_epoch"]
            check("replay_400", post(1)[0] == 400)
            with ThreadPoolExecutor(max_workers=12) as pool:
                statuses = list(
                    pool.map(lambda i: post(1, "parallel-" + str(i))[0], range(12))
                )
            check("busy_without_queue", 429 in statuses)
            compose("stop", "api")
            first = list(diagnostics.glob("*.jsonl"))
            check(
                "private_journal_created",
                len(first) == 1 and bool(first[0].stat().st_mode & 0o600),
            )
            header = json.loads(first[0].read_text().splitlines()[0])["configuration"]
            check(
                "both_hashes_recorded",
                header["weights_sha256"] == env["SONAR_API_WEIGHTS_SHA256"]
                and header["stair_weights_sha256"]
                == env["SONAR_API_STAIR_WEIGHTS_SHA256"],
            )
            check(
                "policy_config_recorded",
                header["audio_config_sha256"] == file_hash(evaluation / "audio.json"),
            )
            env["SONAR_API_TIMEOUT_MS"] = "1"
            compose("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180")
            check("deadline_503", post(1)[0] == 503)
            compose("stop", "api")
            env["SONAR_API_TIMEOUT_MS"] = "1500"
            compose("up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180")
            status, body = post(1)
            check(
                "restart_new_epoch",
                status == 200
                and json.loads(body)["observation"]["tracker_epoch"] != epoch,
            )
            compose("stop", "api")
            check("restart_new_journals", len(list(diagnostics.glob("*.jsonl"))) == 3)
            check(
                "nonroot",
                compose(
                    "run", "--rm", "--no-deps", "--entrypoint", "id", "api", "-u"
                ).stdout.strip()
                == env.get("SONAR_UID", "10001"),
            )
        except subprocess.CalledProcessError as exc:
            # Compose output does not print the bearer token; no arbitrary request body.
            print(exc.stderr[-4000:], file=sys.stderr)
            print(
                compose("logs", "--tail", "50", "api", check=False).stdout,
                file=sys.stderr,
            )
            return 1
        finally:
            compose("down", "--remove-orphans", check=False)
            if args.report:
                report = {
                    "kind": "cpu_container_smoke",
                    "checks": checks,
                    "general_sha256": env["SONAR_API_WEIGHTS_SHA256"],
                    "stairs_sha256": env["SONAR_API_STAIR_WEIGHTS_SHA256"],
                    "inputs": "blank synthetic; not visual accuracy",
                    "created_at_unix": int(time.time()),
                }
                with os.fdopen(
                    os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                    "w",
                ) as out:
                    json.dump(report, out, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
