#!/usr/bin/env python3
"""Prepare one explicitly authorized collection round before Compose startup."""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from uuid import uuid4

BASE = Path("/home/ubuntu/sonar23")
FILES = (
    "compose.aws.yaml",
    "compose.aws.parallel.yaml",
    "compose.aws.audio.yaml",
    "compose.evaluation.yaml",
    "compose.demo.yaml",
    "compose.domain.yaml",
    "compose.collection.yaml",
)
LIMITS = {
    "max_duration_seconds": 600,
    "max_frames": 3000,
    "max_bytes": 104857600,
    "retention_seconds": 86400,
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}")


def validate_policy(policy):
    if not isinstance(policy, dict) or set(policy) != {
        "enabled",
        "source_id",
        "permission_ref",
        *LIMITS,
    }:
        raise ValueError("Explicit collection policy fields required")
    if type(policy["enabled"]) is not bool:
        raise ValueError("Collection opt-in must be boolean")
    for key in ("source_id", "permission_ref"):
        if not isinstance(policy[key], str) or not IDENTIFIER.fullmatch(policy[key]):
            raise ValueError("Opaque source and permission identifiers required")
    for key, ceiling in LIMITS.items():
        if type(policy[key]) is not int or not 0 < policy[key] <= ceiling:
            raise ValueError("Collection limit outside approved ceiling")
    return policy


def set_environment(text, key, value):
    lines = text.splitlines()
    found = [i for i, line in enumerate(lines) if line.startswith(key + "=")]
    if len(found) > 1:
        raise ValueError("Duplicate collection environment key")
    entry = key + "=" + value
    if found:
        lines[found[0]] = entry
    else:
        lines.append(entry)
    return "\n".join(lines) + "\n"


def main():
    policy = validate_policy(
        json.loads((BASE / "private/collection-policy.json").read_text())
    )
    env = BASE / "source/.env"
    if not policy["enabled"]:
        text = set_environment(
            env.read_text(), "SONAR_COLLECTION_CONFIG_IN_CONTAINER", ""
        )
    else:
        compose = [
            "docker",
            "compose",
            "--env-file",
            ".env",
            "-p",
            "sonar23-bancada20261104",
        ]
        for name in FILES:
            compose += ["-f", name]
        cfg = json.loads(
            subprocess.check_output(
                [*compose, "config", "--format", "json"], cwd=BASE / "source"
            )
        )
        user = cfg["services"]["api"]["user"]
        if not re.fullmatch(r"[0-9]+:[0-9]+", user):
            raise ValueError("Explicit numeric API UID/GID required")
        name = "round-" + uuid4().hex + ".json"
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--read-only",
                "--user",
                user,
                "--entrypoint",
                "python",
                "-v",
                str(BASE / "private/collection-config") + ":/config:rw",
                cfg["services"]["api"]["image"],
                "-m",
                "sonar_vision_api.collection",
                "configure",
                "--source-id",
                policy["source_id"],
                "--permission-ref",
                policy["permission_ref"],
                "--seconds",
                str(policy["max_duration_seconds"]),
                "--frames",
                str(policy["max_frames"]),
                "--bytes",
                str(policy["max_bytes"]),
                "--retention-seconds",
                str(policy["retention_seconds"]),
                "--output",
                "/config/" + name,
            ],
            check=True,
            capture_output=True,
        )
        text = set_environment(
            env.read_text(),
            "SONAR_COLLECTION_CONFIG_IN_CONTAINER",
            "/run/sonar/collection/" + name,
        )
    # Keep credential lines and the env file's owner/mode intact.
    old = env.stat()
    fd, name = tempfile.mkstemp(prefix=".env.collection-", dir=env.parent)
    temporary = Path(name)
    try:
        os.fchown(fd, old.st_uid, old.st_gid)
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, env)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(
        json.dumps(
            {
                "collection_enabled": policy["enabled"],
                "round_configured": policy["enabled"],
            }
        )
    )


if __name__ == "__main__":
    main()
