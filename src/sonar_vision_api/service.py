"""Admission, device sessions and timeout around VisionService; no HTTP here.

One inference runs at a time, mirroring VisionService's non-blocking lock.
A request that cannot start immediately gets `busy`: there is no frame queue.
A timeout ends the client's wait only; the worker thread cannot be interrupted,
so the slot stays occupied (new requests get `busy`) until the work finishes.
"""

import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import logging
from threading import Lock
from time import monotonic, perf_counter
from typing import Callable

from sonar_vision.core import Busy, Frame, SessionMissing, VisionService

from . import contract
from .errors import ApiError
from .policy import NullPolicy, PolicyFactory, SuggestionPolicy
from .validation import Metadata

log = logging.getLogger("sonar_vision_api")

Decoder = Callable[[bytes, tuple[int, int]], object]


def log_event(event: str, **fields) -> None:
    """One JSON line per event. Callers never pass images, tokens or text."""
    log.info(json.dumps({"event": event, **fields}, separators=(",", ":"), default=str))


def _ms(started: float) -> float:
    return round((perf_counter() - started) * 1000, 3)


def header_only_decoder(data: bytes, shape: tuple[int, int]) -> tuple[int, int]:
    """Simulated backend: pixels are ignored, so only the JPEG header is validated."""
    return shape


def opencv_decoder(data: bytes, shape: tuple[int, int]):
    """BGR uint8, without applying EXIF rotation (contract: no extra transforms)."""
    import cv2
    import numpy as np

    flags = cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), flags)
    if image is None or image.shape[:2] != shape:
        raise ApiError(400, "jpeg_decode")
    return image


@dataclass
class _DeviceSession:
    session_id: str
    policy: SuggestionPolicy
    last_frame: int = -1  # kept here even if VisionService drops the session
    last_capture: int = -1
    shape: tuple[int, int] | None = None
    open: bool = False


class InferenceService:
    def __init__(self, vision: VisionService, decoder: Decoder, *, timeout_ms: int,
                 policy_factory: PolicyFactory = NullPolicy, clock=monotonic, diagnostics=None):
        self.vision, self.decoder, self.policy_factory = vision, decoder, policy_factory
        self.timeout, self.clock = timeout_ms / 1000, clock
        self.counters = Counter()
        self.diagnostics = diagnostics
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sonar-inference")
        self._lock = Lock()
        self._busy = False
        self._devices: dict[str, _DeviceSession] = {}  # touched only by the worker thread

    def _count(self, name: str) -> None:
        with self._lock:
            self.counters[name] += 1

    async def infer(self, device_id: str, meta: Metadata, image: bytes,
                    shape: tuple[int, int], received_at: float, timings: dict) -> bytes:
        remaining = self.timeout - (self.clock() - received_at)
        if remaining <= 0:
            raise ApiError(503, "deadline_before_admission")
        with self._lock:
            if self._busy:
                self.counters["busy"] += 1
                raise ApiError(429, "server_busy")
            self._busy = True
        work = self._executor.submit(self._work, device_id, meta, image, shape,
                                     received_at, timings)
        # Released from the worker thread itself, even if the event loop is gone.
        work.add_done_callback(lambda done: self._release(done, timings))
        try:
            # shield: cancelling the wait (timeout, client gone) never cancels the worker.
            return await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(work)), remaining)
        except TimeoutError:
            timings["abandoned"] = True
            self._count("abandoned")
            raise ApiError(503, "inference_timeout") from None

    def _release(self, future, timings: dict) -> None:
        error = None if future.cancelled() else future.exception()
        with self._lock:
            self._busy = False
        if timings.get("abandoned"):
            # Late result: discarded, but its real duration matters for #22/#6.
            log_event("abandoned_work_finished", work_ms=timings.get("work_ms"),
                      outcome=getattr(error, "reason", type(error).__name__ if error else "ok"))

    def _work(self, device_id, meta: Metadata, data, shape, received_at, timings) -> bytes:
        started = perf_counter()
        try:
            image = self.decoder(data, shape)
            timings["decode_ms"] = _ms(started)
            session = self._session(device_id, meta.session_id)
            frame_no = int(meta.frame_id)
            if frame_no <= session.last_frame or meta.captured_at_ms < session.last_capture:
                raise ApiError(400, "frame_order")
            # The frame is consumed from here on; a retry of it is a replay.
            session.last_frame, session.last_capture = frame_no, meta.captured_at_ms
            if session.open and session.shape not in (None, shape):
                # Resolution change: explicit reset (new epoch) instead of a tracker error.
                self._vision(self.vision.reset, device_id, session.session_id)
                self._count("resolution_reset")
            session.shape = shape
            frame = Frame(device_id, meta.session_id, meta.frame_id, meta.captured_at_ms, image)
            result = self._process(device_id, session, frame)
            timings["inference_ms"] = round(result.processing_ms, 3)
            observation = result.observation()
            step = perf_counter()
            audio = self._select(session, observation, received_at)
            timings["policy_ms"] = _ms(step)
            step = perf_counter()
            body = self._encode(observation, audio)
            timings["encode_ms"] = _ms(step)
            if self.diagnostics is not None:
                try:
                    self.diagnostics.record(result, data, abandoned=timings.get("abandoned", False))
                except Exception:
                    # Optional diagnostics never invalidate a semantic observation.
                    self._count("diagnostics_error")
            timings["objects"] = len(observation["objects"])
            return body
        finally:
            timings["work_ms"] = _ms(started)

    def _vision(self, method, *args):
        try:
            return method(*args)
        except Busy:
            raise ApiError(429, "vision_busy_or_full") from None

    def _session(self, device_id: str, session_id: str) -> _DeviceSession:
        current = self._devices.get(device_id)
        if current is not None and current.session_id != session_id:
            # New session from the same device (reboot): drop the previous tracker state.
            if current.open:
                self._vision(self.vision.close, device_id, current.session_id)
            del self._devices[device_id]
            self._count("session_replaced")
            current = None
        if current is None:
            current = _DeviceSession(session_id, self.policy_factory(session_id))
            self._devices[device_id] = current
        if not current.open:
            self._vision(self.vision.open, device_id, session_id)
            current.open, current.shape = True, None
        return current

    def _process(self, device_id: str, session: _DeviceSession, frame: Frame):
        for attempt in range(2):
            try:
                return self.vision.process(frame)
            except SessionMissing:
                # Idle expiry inside VisionService; reopen once (new epoch).
                if attempt:
                    break
                self._vision(self.vision.open, device_id, session.session_id)
                self._count("session_reopened")
            except Busy:
                raise ApiError(429, "vision_busy") from None
            except Exception:
                # VisionService drops the session after backend errors; the replay
                # watermark above survives, so the next frame reopens a new epoch.
                session.open = False
                log.exception("vision processing failed")
                raise ApiError(500, "vision_failure") from None
        session.open = False
        raise ApiError(500, "session_lost")

    def _select(self, session: _DeviceSession, observation: dict, received_at: float):
        # Lower bound only: time already spent on this server since the request arrived.
        age = int((self.clock() - received_at) * 1000)
        try:
            return session.policy.select(observation, capture_age_lower_bound_ms=age)
        except Exception:
            self._count("policy_error")
            log.exception("announcement policy failed; sending audio=null")
            return None

    def _encode(self, observation: dict, audio) -> bytes:
        try:
            return contract.encode(observation, audio)
        except contract.ContractViolation as error:
            if audio is None:
                log_event("contract_violation", reason=str(error))
                raise ApiError(500, "observation_contract") from None
            # The observation must not be lost because a suggestion was invalid.
            self._count("audio_rejected")
            log_event("audio_rejected", reason=str(error))
        try:
            return contract.encode(observation, None)
        except contract.ContractViolation as error:
            log_event("contract_violation", reason=str(error))
            raise ApiError(500, "observation_contract") from None

    def close(self) -> None:
        self._executor.shutdown(wait=True)
        for device_id, session in self._devices.items():
            if session.open:
                try:
                    self.vision.close(device_id, session.session_id)
                except Busy:
                    pass
        self._devices.clear()
        if self.diagnostics is not None:
            self.diagnostics.close()
