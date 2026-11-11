"""#22 operator-side Docker resource samples; does not create/change containers."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
from time import monotonic, sleep


def size_bytes(value):
    match = re.fullmatch(
        r"([0-9.]+)\s*(B|kB|KB|MB|GB|TB|KiB|MiB|GiB|TiB)", value.strip()
    )
    if not match:
        raise ValueError("invalid Docker memory unit")
    units = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
    }
    result = float(match[1]) * units[match[2]]
    if not math.isfinite(result) or result < 0:
        raise ValueError("invalid Docker memory value")
    return round(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--interval", type=float, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", args.container)
        or not all(math.isfinite(x) and x > 0 for x in (args.duration, args.interval))
        or args.output.exists()
    ):
        parser.error("valid container, positive timing and new output required")
    metadata = json.loads(
        subprocess.check_output(
            ["docker", "inspect", args.container], text=True, timeout=10
        )
    )[0]
    config = metadata["HostConfig"]
    cpus = config.get("NanoCpus", 0) / 1e9
    memory = config.get("Memory", 0)
    header = {
        "kind": "server_container_resource_samples",
        "container_id": metadata["Id"],
        "image_id": metadata["Image"],
        "cpu_limit": cpus or None,
        "memory_limit_bytes": memory or None,
        "requested_interval_s": args.interval,
        "scope": "Docker container; not client process",
        "cpu_percent_capacity_is_unknown_without_explicit_cpu_limit": True,
    }
    started = monotonic()
    errors = 0
    count = 0
    with os.fdopen(
        os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        stream.write(json.dumps(header) + "\n")
        stream.flush()
        while monotonic() - started < args.duration:
            before = monotonic()
            try:
                raw = json.loads(
                    subprocess.check_output(
                        [
                            "docker",
                            "stats",
                            "--no-stream",
                            "--format",
                            "{{json .}}",
                            args.container,
                        ],
                        text=True,
                        timeout=10,
                    )
                )
                cpu = float(raw["CPUPerc"].rstrip("%"))
                used, limit = map(size_bytes, raw["MemUsage"].split("/"))
                row = {
                    "sampled_at_utc": datetime.now(timezone.utc).isoformat(),
                    "elapsed_s": monotonic() - started,
                    "cpu_percent_one_core": cpu,
                    "cpu_percent_capacity": cpu / cpus if cpus else None,
                    "memory_used_bytes": used,
                    "docker_reported_memory_limit_bytes": limit,
                    "ram_percent_capacity": used / memory * 100 if memory else None,
                    "collector_duration_s": monotonic() - before,
                }
                count += 1
            except (ValueError, KeyError, subprocess.SubprocessError):
                errors += 1
                row = {"elapsed_s": monotonic() - started, "sample_error": True}
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            sleep(
                max(
                    0,
                    min(
                        args.interval - (monotonic() - before),
                        args.duration - (monotonic() - started),
                    ),
                )
            )
        stream.write(
            json.dumps(
                {
                    "kind": "collection_summary",
                    "samples": count,
                    "errors": errors,
                    "wall_s": monotonic() - started,
                }
            )
            + "\n"
        )
    print(json.dumps({"samples": count, "errors": errors}))
    return 0 if count and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
