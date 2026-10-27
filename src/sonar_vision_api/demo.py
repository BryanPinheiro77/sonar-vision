"""Opt-in, single-source demonstration. Bounded volatile state, no hardware control."""

from dataclasses import dataclass
from hashlib import sha256
from ipaddress import ip_address, ip_network
import json
from threading import Lock
from time import monotonic, time

from sonar_vision.core import identifier

from .diagnostics import prediction_record
from .errors import ApiError
from .validation import _no_constants, _no_duplicates, _COUNTER

STALE_SECONDS = 5
RETENTION_SECONDS = 30
POLL_MS = 2000
MAX_TOF_BYTES = 2048


@dataclass(frozen=True)
class DemoSettings:
    device_id: str
    session_id: str
    source_kind: str
    allowed_cidrs: tuple[str, ...] = ("127.0.0.1/32", "::1/128")

    def __post_init__(self):
        identifier(self.device_id)
        identifier(self.session_id)
        if self.source_kind not in ("simulated", "esp32"):
            raise ValueError("SONAR_DEMO_SOURCE_KIND must be simulated or esp32")
        if not self.allowed_cidrs:
            raise ValueError("demo requires an explicit network allowlist")
        for cidr in self.allowed_cidrs:
            network = ip_network(cidr)
            if network.prefixlen == 0:
                raise ValueError("demo refuses unrestricted networks")

    @classmethod
    def from_env(cls, env):
        if env.get("SONAR_DEMO_ENABLED", "0") not in ("0", "1"):
            raise ValueError("SONAR_DEMO_ENABLED must be 0 or 1")
        if env.get("SONAR_DEMO_ENABLED", "0") == "0":
            return None
        return cls(env["SONAR_DEMO_DEVICE_ID"], env["SONAR_DEMO_SESSION_ID"],
                   env["SONAR_DEMO_SOURCE_KIND"],
                   tuple(env.get("SONAR_DEMO_ALLOWED_CIDRS", "127.0.0.1/32,::1/128").split(",")))


def parse_tof(raw):
    try:
        data = json.loads(raw, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
        fields = {"version", "session_id", "sequence", "captured_at_ms", "distance_mm",
                  "valid", "quality", "sector", "zone", "aggregation"}
        if not isinstance(data, dict) or set(data) != fields or data["version"] != "demo-tof-1":
            raise ValueError()
        identifier(data["session_id"])
        identifier(data["sequence"])
        if not _COUNTER.fullmatch(data["sequence"]):
            raise ValueError()
        if type(data["captured_at_ms"]) is not int or not 0 <= data["captured_at_ms"] < 2**53:
            raise ValueError()
        valid, distance = data["valid"], data["distance_mm"]
        if type(valid) is not bool:
            raise ValueError()
        if valid:
            if type(distance) is not int or not 0 <= distance < 2**31:
                raise ValueError()
            if data["quality"] not in ("good", "degraded"):
                raise ValueError()
        elif distance is not None or data["quality"] != "invalid":
            raise ValueError()
        if data["sector"] not in ("left", "center", "right", "all"):
            raise ValueError()
        if data["aggregation"] == "zone":
            if type(data["zone"]) is not int or not 0 <= data["zone"] <= 63:
                raise ValueError()
        elif data["aggregation"] != "min_valid_8x8" or data["zone"] is not None or data["sector"] != "all":
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise ApiError(400, "tof_schema") from None


class DemoStore:
    """One configured boot/device, one JPEG <= upload limit and one ToF reading.

    Optional inference hooks never wait for the panel lock. Expiry drops payloads
    but keeps constant-size watermarks so replay cannot make expired data fresh.
    """

    def __init__(self, settings, *, clock=monotonic, wall_clock=time):
        self.settings, self.clock, self.wall_clock = settings, clock, wall_clock
        self._networks = tuple(ip_network(c) for c in settings.allowed_cidrs)
        self._lock = Lock()
        self.frame = self.tof = None
        self.jpeg = None
        self.ended = False
        self.seen_frame = self.seen_tof = False
        self.last_sequence = self.last_capture = -1
        self.rejected = 0
        self._rate = {}  # fixed route names, never client identities

    def allowed(self, host):
        try:
            address = ip_address(host)
            return any(address in n for n in self._networks)
        except ValueError:
            return False

    def rate_limit(self, route, limit):
        now = int(self.clock())
        second, count = self._rate.get(route, (now, 0))
        count = count if second == now else 0
        if count >= limit:
            raise ApiError(429, "demo_rate")
        self._rate[route] = (now, count + 1)

    def _expire(self):
        now = self.clock()
        if self.frame and now - self.frame["received_monotonic"] >= RETENTION_SECONDS:
            self.frame = self.jpeg = None
        if (self.frame and self.frame["inference"] == "pending" and
                now - self.frame["received_monotonic"] >= 2):
            self.frame["inference"] = "unavailable"
            self.frame.pop("_pending", None)
        if self.tof and now - self.tof["received_monotonic"] >= RETENTION_SECONDS:
            self.tof = None

    def expire(self):
        with self._lock:
            self._expire()

    def end(self):
        with self._lock:
            self.frame = self.jpeg = self.tof = None
            self.ended = True

    def accepted(self, device, meta, jpeg, shape, received_at):
        if device != self.settings.device_id or not self._lock.acquire(blocking=False):
            return
        try:
            if meta.session_id != self.settings.session_id:
                self.frame = self.jpeg = self.tof = None
                self.ended = True  # reboot: operator must select the new boot explicitly
            if self.ended:
                return
            self._expire()
            self.jpeg = jpeg
            self.seen_frame = True
            self.frame = {"frame_id": meta.frame_id, "captured_at_ms": meta.captured_at_ms,
                          "jpeg_sha256": sha256(jpeg).hexdigest(), "shape": list(shape),
                          "received_monotonic": received_at,
                          "received_at_ms": int((self.wall_clock() - (self.clock() - received_at)) * 1000),
                          "inference": "pending", "predictions": None}
        finally:
            self._lock.release()

    def record(self, device, result, jpeg, *, abandoned=False):
        if device != self.settings.device_id:
            return
        row = prediction_record(result, jpeg, abandoned=abandoned)
        if not self._lock.acquire(blocking=False):
            return
        try:
            self._expire()
            if (self.frame and result.session_id == self.settings.session_id and
                    self.frame["frame_id"] == row["frame_id"] and
                    self.frame["captured_at_ms"] == row["captured_at_ms"] and
                    self.frame["jpeg_sha256"] == row["jpeg_sha256"]):
                if abandoned:
                    self.frame.update(inference="unavailable", predictions=None)
                    self.frame.pop("_pending", None)
                elif self.frame["inference"] == "pending":
                    self.frame["_pending"] = row
        finally:
            self._lock.release()

    def complete(self, device, meta):
        """Only the successful async waiter may publish the worker projection.

        This avoids a timeout racing with a diagnostic record and resurrecting
        abandoned boxes. Dropped completion is safely unavailable after 2 s.
        """
        if device != self.settings.device_id or not self._lock.acquire(blocking=False):
            return
        try:
            self._expire()
            if (self.frame and meta.session_id == self.settings.session_id and
                    self.frame["frame_id"] == meta.frame_id and
                    self.frame["captured_at_ms"] == meta.captured_at_ms and
                    self.frame["inference"] == "pending" and "_pending" in self.frame):
                self.frame.update(inference="available", predictions=self.frame.pop("_pending"))
        finally:
            self._lock.release()

    def unavailable(self, device, meta):
        if device != self.settings.device_id or not self._lock.acquire(blocking=False):
            return
        try:
            if (self.frame and meta.session_id == self.settings.session_id and
                    self.frame["frame_id"] == meta.frame_id and
                    self.frame["captured_at_ms"] == meta.captured_at_ms):
                self.frame.update(inference="unavailable", predictions=None)
                self.frame.pop("_pending", None)
        finally:
            self._lock.release()

    def ingest_tof(self, device, data):
        with self._lock:
            if device != self.settings.device_id:
                raise ApiError(403, "demo_source")
            if self.ended or data["session_id"] != self.settings.session_id:
                self.rejected += 1
                raise ApiError(409, "demo_session", "demo_conflict")
            if int(data["sequence"]) <= self.last_sequence or data["captured_at_ms"] < self.last_capture:
                self.rejected += 1
                raise ApiError(409, "tof_order", "demo_conflict")
            self.last_sequence, self.last_capture = int(data["sequence"]), data["captured_at_ms"]
            self.seen_tof = True
            self.tof = {**data, "received_monotonic": self.clock(),
                        "received_at_ms": int(self.wall_clock() * 1000)}

    def snapshot(self, backend):
        with self._lock:
            self._expire()
            def channel(row, seen):
                if row is None:
                    return {"state": "expired" if seen else "waiting", "data": None}
                age = max(0, round((self.clock() - row["received_monotonic"]) * 1000))
                state = "stale" if age >= STALE_SECONDS * 1000 else "receiving"
                if "valid" in row and not row["valid"] and state == "receiving":
                    state = "invalid"
                return {"state": state, "age_ms": age,
                        "data": {k: v for k, v in row.items()
                                 if k != "received_monotonic" and not k.startswith("_")}}
            return {"source": {"device_id": self.settings.device_id,
                               "session_id": self.settings.session_id,
                               "kind": self.settings.source_kind}, "backend": backend,
                    "ended": self.ended, "poll_ms": POLL_MS,
                    "stale_ms": STALE_SECONDS * 1000, "retention_ms": RETENTION_SECONDS * 1000,
                    "rejected_tof": self.rejected,
                    "image": channel(self.frame, self.seen_frame),
                    "tof": channel(self.tof, self.seen_tof)}

    def image(self, frame_id, digest):
        with self._lock:
            self._expire()
            if (not self.frame or self.frame["frame_id"] != frame_id or
                    self.frame["jpeg_sha256"] != digest):
                raise ApiError(409, "demo_image_changed", "demo_conflict")
            return self.jpeg
