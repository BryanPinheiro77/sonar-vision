"""Minimal glasses-side client for integration runs (#27). Not the #30 simulator.

Implements only what the end-to-end checks need from the device side of
contract 0.1: one active request per device (busy, never a queue), a 2000 ms
total timeout, capture records, and full response admission before any effect.
"""

from dataclasses import dataclass
import json
import ssl
from threading import Lock
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
                 timeout_s: float = CLIENT_TIMEOUT_S, server_hostname: str | None = None):
        import httpx2

        self.url, self.clock = url.rstrip("/"), clock
        # Certificate and hostname are always verified; there is no insecure switch.
        context = ssl.create_default_context(cafile=str(ca_file))
        self._http = httpx2.Client(verify=context, timeout=timeout_s, follow_redirects=False,
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

    def send(self, capture: Capture) -> dict:
        """POST one capture. Raises ClientBusy, or Discarded with the reason."""
        if not self._lock.acquire(blocking=False):
            raise ClientBusy("request already active")
        try:
            metadata = json.dumps({"version": "0.1", "session_id": capture.session_id,
                                   "frame_id": capture.frame_id,
                                   "captured_at_ms": capture.captured_at_ms})
            files = {"metadata": (None, metadata, "application/json"),
                     "image": ("frame.jpg", capture.jpeg, "image/jpeg")}
            try:
                response = self._http.post(f"{self.url}/v1/inference", files=files)
            except self._httpx.TimeoutException:
                raise Discarded("timeout") from None
            except self._httpx.ConnectError as error:
                cause = error.__cause__ or error.__context__
                tls = isinstance(cause, ssl.SSLError) or "certificate" in str(error).lower()
                raise Discarded("tls" if tls else "connect") from None
            except self._httpx.TransportError:
                raise Discarded("disconnected") from None
            if response.status_code != 200:
                try:
                    code = response.json()["error"]["code"]
                except (ValueError, KeyError, TypeError):
                    code = "unexpected_error_body"
                raise Discarded(code, response.status_code)
            return self.admit(response.content)
        finally:
            self._lock.release()

    def admit(self, body: bytes) -> dict:
        """Validate the whole envelope, then references, age and order (contract 0.1)."""
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
        except (UnicodeDecodeError, ValueError):
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
