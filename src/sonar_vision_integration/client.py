"""Minimal glasses-side client for integration runs (#27). Not the #30 simulator.

Implements only what the end-to-end checks need from the device side of
contract 0.1: one active request per device (busy, never a queue), a 2000 ms
TOTAL deadline (connect + send + read, measured on a monotonic clock), a
streamed 16 KiB response limit, capture records, and full response admission
before any effect.

Transport runs in a worker thread. When the deadline passes, the caller stops
waiting and gets `timeout`, but the per-device lock stays held until that
worker really finishes, so a late request can never overlap a new one. A late
response is never admitted.
"""

from dataclasses import dataclass
import json
import ssl
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

from sonar_vision_api import contract

CLIENT_TIMEOUT_S = 2.0
LOCAL_VALIDITY_MS = 1000
MAX_RECORDS = 64  # bounded capture memory; a harness limit, not a risk threshold


class ClientBusy(Exception):
    """A request is already active for this device; the new capture is dropped."""


class Discarded(Exception):
    """Response or failure that must not produce any effect; `reason` is stable."""

    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.reason, self.status = reason, status


@dataclass(frozen=True)
class Capture:
    session_id: str
    frame_id: str
    captured_at_ms: int
    jpeg: bytes


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON key")
    return dict(pairs)


def _reject_constant(name):
    raise ValueError("NaN/Infinity are not JSON")


def monotonic_ms() -> int:
    return int(monotonic() * 1000)


class DeviceClient:
    def __init__(self, url: str, token: str, ca_file, *, clock=monotonic_ms,
                 timeout_s: float = CLIENT_TIMEOUT_S, transport=None):
        import httpx2

        self.url, self.clock, self.timeout_s = url.rstrip("/"), clock, timeout_s
        # Certificate and hostname are always verified; there is no insecure switch.
        context = ssl.create_default_context(cafile=str(ca_file) if ca_file is not None else None)
        self._http = httpx2.Client(verify=context, follow_redirects=False, transport=transport,
                                   headers={"Authorization": f"Bearer {token}"} if token else {})
        self._httpx = httpx2
        self._lock = Lock()
        self.restart()

    def restart(self) -> None:
        """Simulated reboot: new session, counters and records; old replies become invalid."""
        self.session_id = uuid4().hex
        self._next_frame = 0
        self.records: dict[str, int] = {}
        self.seen: set[str] = set()
        self.last_admitted_frame = -1

    def capture(self, jpeg: bytes) -> Capture:
        frame_id = str(self._next_frame)
        self._next_frame += 1
        record = Capture(self.session_id, frame_id, self.clock(), jpeg)
        self.records[frame_id] = record.captured_at_ms
        while len(self.records) > MAX_RECORDS:
            self.records.pop(next(iter(self.records)))
        return record

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    def send(self, capture: Capture) -> dict:
        """POST one capture. Raises ClientBusy, or Discarded with the reason."""
        if not self._lock.acquire(blocking=False):
            raise ClientBusy("request already active")
        deadline = monotonic() + self.timeout_s
        outcome, done = {}, Event()

        def work():
            try:
                outcome["value"] = self._transfer(capture, deadline)
            except BaseException as error:  # handed to the caller, never lost
                outcome["error"] = error
            finally:
                done.set()
                self._lock.release()  # only when the transport has really stopped

        Thread(target=work, daemon=True, name="device-transport").start()
        if not done.wait(max(0.0, deadline - monotonic())):
            # Deadline reached: stop waiting; the worker keeps the lock until it ends.
            raise Discarded("timeout")
        if "error" in outcome:
            raise outcome["error"]
        status, body = outcome["value"]
        if status != 200:
            try:
                code = json.loads(body)["error"]["code"]
                if not isinstance(code, str):
                    raise TypeError
            except (ValueError, KeyError, TypeError):
                code = "unexpected_error_body"
            raise Discarded(code, status)
        return self.admit(body)

    def _transfer(self, capture: Capture, deadline: float) -> tuple[int, bytes]:
        """Worker side: every byte counted against 16 KiB, every chunk against the deadline."""
        httpx = self._httpx
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise Discarded("timeout")
        metadata = json.dumps({"version": "0.1", "session_id": capture.session_id,
                               "frame_id": capture.frame_id,
                               "captured_at_ms": capture.captured_at_ms})
        files = {"metadata": (None, metadata, "application/json"),
                 "image": ("frame.jpg", capture.jpeg, "image/jpeg")}
        try:
            # Per-operation timeouts never exceed what is left of the total deadline.
            with self._http.stream("POST", f"{self.url}/v1/inference", files=files,
                                   timeout=httpx.Timeout(remaining)) as response:
                declared = response.headers.get("content-length")
                if declared is not None and (not declared.isdigit()
                                             or int(declared) > contract.MAX_RESPONSE_BYTES):
                    raise Discarded("response_too_large", response.status_code)
                chunks, size = [], 0
                # Applies to error responses too; Content-Length alone is not trusted.
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > contract.MAX_RESPONSE_BYTES:
                        raise Discarded("response_too_large", response.status_code)
                    if monotonic() >= deadline:
                        raise Discarded("timeout")
                    chunks.append(chunk)
                return response.status_code, b"".join(chunks)
        except httpx.TimeoutException:
            raise Discarded("timeout") from None
        except httpx.ConnectError as error:
            cause = error.__cause__ or error.__context__
            tls = isinstance(cause, ssl.SSLError) or "certificate" in str(error).lower()
            raise Discarded("tls" if tls else "connect") from None
        except httpx.TransportError:
            raise Discarded("disconnected") from None

    def admit(self, body: bytes) -> dict:
        """Validate the whole envelope, then references, age and order (contract 0.1).

        Any malformed response becomes Discarded("invalid_message") and leaves the
        admission state (seen IDs, last admitted frame) untouched.
        """
        if len(body) > contract.MAX_RESPONSE_BYTES:
            raise Discarded("response_too_large")
        try:
            data = json.loads(body.decode("utf-8"), object_pairs_hook=_no_duplicates,
                              parse_constant=_reject_constant)
            if not isinstance(data, dict) or set(data) != {"observation", "audio"}:
                raise ValueError("envelope")
            observation, audio = data["observation"], data["audio"]
            contract.validate_observation(observation)
            if audio is not None:
                contract.validate_audio(audio, observation)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError, AttributeError):
            raise Discarded("invalid_message") from None
        if observation["session_id"] != self.session_id:
            raise Discarded("session_mismatch")
        if self.records.get(observation["frame_id"]) != observation["captured_at_ms"]:
            raise Discarded("capture_mismatch")
        if observation["message_id"] in self.seen:
            raise Discarded("duplicate")
        age = self.clock() - observation["captured_at_ms"]
        if age < 0 or age >= min(observation["valid_for_ms"], LOCAL_VALIDITY_MS):
            raise Discarded("expired")
        if int(observation["frame_id"]) <= self.last_admitted_frame:
            raise Discarded("out_of_order")
        self.seen.add(observation["message_id"])
        self.last_admitted_frame = int(observation["frame_id"])
        return data

    def close(self) -> None:
        self._http.close()
