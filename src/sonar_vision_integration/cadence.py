"""#23 opt-in capture when available; fixed ceiling, one active request, no queue.

This is a measurement harness, not ESP firmware or a changed protocol. Unlike
periodic offered load, it waits to capture fresh data after the previous request
finishes. Timing and outcomes are reported with the original client admission.
"""

from collections import Counter
import math
from time import perf_counter, sleep

from sonar_vision.benchmark import summarize
from .client import ClientBusy, Discarded


def run_available_load(client, frames, *, fps, duration_s):
    if not frames or not all(math.isfinite(x) and x > 0 for x in (fps, duration_s)):
        raise ValueError("nonempty source and positive finite rate/duration required")
    started = perf_counter()
    end = started + duration_s
    eligible = started
    previous_clip = None
    rows, opportunities, unexpected = [], [], []
    transport_waits = 0
    while True:
        now = perf_counter()
        if now >= end:
            break
        if client.busy:
            transport_waits += 1
            sleep(min(0.01, end - now))
            continue
        if now < eligible:
            sleep(min(eligible - now, end - now))
            continue
        # Source follows wall time; never queue stale samples/captures.
        index = min(len(frames) - 1, int((now - started) / duration_s * len(frames)))
        frame = frames[index]
        if previous_clip != frame["clip_id"]:
            client.restart()
            previous_clip = frame["clip_id"]
        begin = perf_counter()
        capture = client.capture(frame["jpeg"])
        eligible = begin + 1 / fps
        status, count = None, None
        send_started = perf_counter()
        try:
            response = client.send(capture)
            outcome = "admitted"
            count = len(response["observation"]["objects"])
        except Discarded as error:
            outcome, status = error.reason, error.status
        except ClientBusy:
            outcome = "client_busy_race"
        except Exception as error:
            outcome = "unexpected_exception"
            unexpected.append(type(error).__name__)
        completed = perf_counter()
        rows.append(
            {
                "session_id": capture.session_id,
                "frame_id": capture.frame_id,
                "clip_id": frame["clip_id"],
                "source_timestamp_ms": frame["source_timestamp_ms"],
                "jpeg_bytes": len(capture.jpeg),
                "outcome": outcome,
                "error_http_status": status,
                "object_count": count,
                "completed_elapsed_s": completed - started,
                "https_call_to_admission_ms": (completed - send_started) * 1000,
                "synthetic_capture_to_admission_ms": (completed - begin) * 1000,
            }
        )
        opportunities.append(
            {
                "slot": len(rows) - 1,
                "scheduled_elapsed_s": begin - started,
                "lateness_ms": 0,
                "outcome": "attempted",
            }
        )
    # A timeout may return before its transport worker releases ownership.
    # Include that bounded drain before declaring this report complete.
    drain_end = perf_counter() + client.timeout_s + 1
    while client.busy:
        now = perf_counter()
        if now >= drain_end:
            raise RuntimeError("available transport did not drain")
        sleep(min(0.01, drain_end - now))
    finished = perf_counter()
    admitted = [r for r in rows if r["outcome"] == "admitted"]
    within = sum(r["completed_elapsed_s"] <= duration_s for r in admitted)
    return {
        "offered_fps": fps,
        "offering_duration_s": duration_s,
        "scheduling": "when_available",
        "rate_is_capture_start_ceiling": True,
        "offered_opportunities": None,
        "opportunity_counts": {"attempted": len(rows)},
        "transport_busy_poll_count": transport_waits,
        "wall_s_including_drain": finished - started,
        "attempt_outcomes": dict(Counter(r["outcome"] for r in rows)),
        "attempted_fps_in_offering_window": len(rows) / duration_s,
        "admitted_fps_including_drain": len(admitted) / (finished - started),
        "admitted_within_offering_window": within,
        "admitted_fps_within_offering_window": within / duration_s,
        "admitted_fps_over_offering_window": len(admitted) / duration_s,
        "attempt_failure_fraction": (len(rows) - len(admitted)) / len(rows)
        if rows
        else None,
        "synthetic_capture_to_admission": summarize(
            [r["synthetic_capture_to_admission_ms"] for r in admitted]
        )
        if admitted
        else None,
        "https_call_to_admission": summarize(
            [r["https_call_to_admission_ms"] for r in admitted]
        )
        if admitted
        else None,
        "rows": rows,
        "opportunities": opportunities,
        "unexpected_exception_types": unexpected,
    }
