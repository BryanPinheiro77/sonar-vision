"""Offered-load measurement for #22. No frame queue or transport changes."""

from collections import Counter
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import subprocess
from threading import Event, Thread
from time import perf_counter, process_time, sleep

from sonar_vision.benchmark import summarize
from sonar_vision.benchmark import resource
from .client import ClientBusy, Discarded


def current_rss_bytes():
    try:
        if platform.system() == "Linux":
            return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        if platform.system() == "Darwin":
            return int(subprocess.check_output(
                ["ps", "-o", "rss=", "-p", str(os.getpid())], text=True, timeout=1).strip()) * 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


class ResourceSampler:
    """Current process only: client+server in loopback; client only in remote mode."""

    def __init__(self, cpu_capacity=None, memory_capacity=None):
        self.cpu_capacity = cpu_capacity or os.cpu_count() or 1
        self.memory_capacity = memory_capacity
        self.rows = []
        self.stop = Event()

    def __enter__(self):
        self.started = perf_counter()
        self.initial_cpu = process_time()
        self.last_wall, self.last_cpu = self.started, self.initial_cpu
        self.thread = Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def _sample(self):
        while not self.stop.is_set():
            wall, cpu = perf_counter(), process_time()
            elapsed = wall - self.last_wall
            rss = current_rss_bytes()
            cpu_percent = (cpu - self.last_cpu) / elapsed * 100 if elapsed >= .1 else None
            self.rows.append({"sampled_at_utc": datetime.now(timezone.utc).isoformat(),
                              "elapsed_s": wall - self.started,
                              "cpu_percent_one_core": cpu_percent,
                              "cpu_percent_capacity": cpu_percent / self.cpu_capacity
                              if cpu_percent is not None else None,
                              "rss_bytes": rss,
                              "ram_percent_capacity": rss / self.memory_capacity * 100
                              if rss is not None and self.memory_capacity else None})
            self.last_wall, self.last_cpu = wall, cpu
            self.stop.wait(1)

    def __exit__(self, *exc):
        self.elapsed = perf_counter() - self.started
        self.cpu_seconds = process_time() - self.initial_cpu
        self.stop.set()
        self.thread.join(3)

    def report(self):
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource is not None else None
        return {"cpu_capacity_denominator": self.cpu_capacity,
                "measured_wall_s": self.elapsed, "process_cpu_s": self.cpu_seconds,
                "mean_cpu_percent_capacity": self.cpu_seconds / self.elapsed * 100 / self.cpu_capacity,
                "memory_capacity_bytes": self.memory_capacity,
                "samples": self.rows,
                "peak_rss_bytes_since_process_start": None if peak is None else
                peak if platform.system() == "Darwin" else peak * 1024,
                "peak_includes_initialization_and_warmup": True}


def run_load(client, frames, *, fps, duration_s):
    """Frames are preencoded dicts: clip_id, jpeg, source_timestamp_ms.

    Capture records are generated at each admitted sending opportunity, not at
    video preparation time. This measures synthetic acquisition, not a camera.
    Scheduling continues while send blocks; busy slots are dropped before capture.
    """
    if not frames or not math.isfinite(fps) or fps <= 0 or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("nonempty frames and finite positive fps/duration required")
    counts = Counter()
    rows, opportunities = [], []
    period = 1 / fps
    offered = math.ceil(duration_s * fps)
    started = perf_counter()
    active = None
    previous_clip = None
    unexpected = []

    def send(capture, frame, begin):
        status, observation_count = None, None
        send_started = perf_counter()
        try:
            response = client.send(capture)
            outcome = "admitted"
            observation_count = len(response["observation"]["objects"])
        except Discarded as error:
            outcome, status = error.reason, error.status
        except ClientBusy:
            outcome = "client_busy_race"
        except Exception as error:
            outcome = "unexpected_exception"
            unexpected.append(type(error).__name__)  # no secrets from exception text
        rows.append({"session_id": capture.session_id, "frame_id": capture.frame_id,
                     "clip_id": frame["clip_id"], "source_timestamp_ms": frame["source_timestamp_ms"],
                     "jpeg_bytes": len(capture.jpeg), "outcome": outcome,
                     "error_http_status": status, "object_count": observation_count,
                     "https_call_to_admission_ms": (perf_counter() - send_started) * 1000,
                     "synthetic_capture_to_admission_ms": (perf_counter() - begin) * 1000})

    for slot in range(offered):
        deadline = started + slot * period
        sleep(max(0, deadline - perf_counter()))
        late = perf_counter() - deadline
        if late >= period:
            outcome = "scheduler_late"
        elif (active is not None and active.is_alive()) or client.busy:
            outcome = "busy_before_capture"
        else:
            # Span the same ordered corpus at every rate; skip stale source samples.
            frame = frames[min(len(frames) - 1, slot * len(frames) // offered)]
            if previous_clip != frame["clip_id"]:
                client.restart()
                previous_clip = frame["clip_id"]
            begin = perf_counter()
            capture = client.capture(frame["jpeg"])
            active = Thread(target=send, args=(capture, frame, begin), daemon=True)
            active.start()
            outcome = "attempted"
        counts[outcome] += 1
        opportunities.append({"slot": slot, "scheduled_elapsed_s": slot * period,
                              "lateness_ms": late * 1000, "outcome": outcome})
    sleep(max(0, started + duration_s - perf_counter()))
    if active is not None:
        active.join(client.timeout_s + 1)
        if active.is_alive():
            raise RuntimeError("load worker did not finish")
    finished = perf_counter()
    admitted = [r for r in rows if r["outcome"] == "admitted"]
    assert sum(counts.values()) == offered
    assert counts["attempted"] == len(rows)
    return {"offered_fps": fps, "offering_duration_s": duration_s,
            "wall_s_including_drain": finished - started,
            "offered_opportunities": offered, "opportunity_counts": dict(counts),
            "attempt_outcomes": dict(Counter(r["outcome"] for r in rows)),
            "attempted_fps_in_offering_window": len(rows) / duration_s,
            "admitted_fps_including_drain": len(admitted) / (finished - started),
            "admitted_fps_over_offering_window": len(admitted) / duration_s,
            "attempt_failure_fraction": (len(rows) - len(admitted)) / len(rows) if rows else None,
            "synthetic_capture_to_admission": summarize(
                [r["synthetic_capture_to_admission_ms"] for r in admitted]) if admitted else None,
            "https_call_to_admission": summarize(
                [r["https_call_to_admission_ms"] for r in admitted]) if admitted else None,
            "rows": rows, "opportunities": opportunities,
            "unexpected_exception_types": unexpected}
