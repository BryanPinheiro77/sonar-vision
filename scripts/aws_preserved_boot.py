#!/usr/bin/env python3
"""Bounded autostart for the preserved #23 deployment; no AWS credentials."""

from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

STATE = Path("/var/lib/sonar23/auto-start.json")
TIMER = Path("/etc/systemd/system/sonar23-expiry.timer")


def choose_window(state, identity, now):
    if state.get("version") != 1 or identity["instanceId"] != state["instance_id"]:
        raise ValueError("Unexpected instance or state version")
    remaining = state["remaining_seconds"]
    deadline = state["deadline"]
    if type(remaining) is not int or remaining < 0 or type(deadline) is not int:
        raise ValueError("Invalid runtime quota")
    launched = int(
        datetime.fromisoformat(
            identity["pendingTime"].replace("Z", "+00:00")
        ).timestamp()
    )
    if launched > now + 60:
        raise ValueError("Invalid launch clock")
    launch = identity["pendingTime"]
    updated = dict(state)
    if deadline > now:
        # Restart or early Stop/Start continues the same absolute window.
        updated["launch_id"] = launch
        return updated
    if state["launch_id"] == launch:
        raise ValueError("Reboot cannot renew an expired usage window")
    duration = min(1200, remaining)
    if duration <= 0 or launched + duration <= now:
        raise ValueError("Approved runtime quota exhausted")
    updated.update(
        launch_id=launch,
        deadline=launched + duration,
        remaining_seconds=remaining - duration,
    )
    return updated


def identity_document():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url = "http://169.254.169.254/latest/"
    request = urllib.request.Request(
        url + "api/token",
        method="PUT",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
    )
    token = opener.open(request, timeout=3).read(4096).decode("ascii")
    request = urllib.request.Request(
        url + "dynamic/instance-identity/document",
        headers={"X-aws-ec2-metadata-token": token},
    )
    return json.loads(opener.open(request, timeout=3).read(16384))


def atomic_write(path, data):
    temporary = path.with_name(path.name + ".new")
    fd = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(fd, "w") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def main():
    with open("/var/lib/sonar23/auto-start.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(STATE.read_text())
        updated = choose_window(state, identity_document(), int(time.time()))
        deadline = updated["deadline"]
        stamp = datetime.fromtimestamp(deadline, timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        # Reserve quota before arming the timer. Failures never grant extra time.
        atomic_write(STATE, json.dumps(updated, indent=2) + "\n")
        atomic_write(Path("/var/lib/sonar23/deadline"), str(deadline) + "\n")
        atomic_write(
            TIMER,
            "[Unit]\nDescription=Absolute stop deadline for preserved Sonar Vision\n"
            "[Timer]\nOnCalendar=" + stamp + "\nPersistent=true\nAccuracySec=1s\n"
            "Unit=sonar23-expiry.service\n[Install]\nWantedBy=timers.target\n",
        )
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print(
            json.dumps(
                {
                    "deadline_utc": stamp,
                    "remaining_seconds": updated["remaining_seconds"],
                }
            )
        )


if __name__ == "__main__":
    main()
