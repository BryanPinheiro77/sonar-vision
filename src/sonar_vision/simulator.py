"""Computer-only glasses simulator for #30. No sensors, playback or tactile IO."""
import argparse
from hashlib import sha256
from pathlib import Path
import base64
from dataclasses import dataclass
import http.client
import json
import math
import os
import socket
import ssl
from threading import Event, Lock, Thread
from time import monotonic, sleep
from urllib.parse import urlsplit
from uuid import uuid4

from .core import CLASSES, identifier

MAX_BODY = 16384
ENVELOPE = {"version", "type", "session_id", "message_id", "frame_id",
            "captured_at_ms", "valid_for_ms"}
OBJECT = {"track_id", "class_name", "confidence", "direction", "movement", "stair_direction"}
SCENARIOS = ("success", "expired", "timeout", "old_session", "wrong_capture",
             "malformed", "oversized", "unauthorized", "disconnect", "duplicate")


class Rejected(Exception):
    """Only fixed diagnostic codes may be exposed to the console."""


def integer(value, positive=False):
    return type(value) is int and (1 if positive else 0) <= value <= 2**53 - 1


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != expected:
        raise Rejected("invalid_message")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected("invalid_message")
        result[key] = value
    return result


def parse_response(body):
    if not isinstance(body, bytes) or len(body) > MAX_BODY:
        raise Rejected("response_too_large")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=unique_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(Rejected("invalid_message")))
        fields(value, {"observation", "audio"})
        obs, audio = value["observation"], value["audio"]
        fields(obs, ENVELOPE | {"tracker_epoch", "objects"})
        messages = [(obs, "visual_observation")]
        if audio is not None:
            fields(audio, ENVELOPE | {"observation_id", "text", "directional"})
            messages.append((audio, "audio_suggestion"))
        for msg, kind in messages:
            if msg["version"] != "0.1" or msg["type"] != kind:
                raise Rejected("invalid_message")
            for name in ("session_id", "message_id", "frame_id"):
                identifier(msg[name])
            frame = msg["frame_id"]
            if not frame.isascii() or not frame.isdecimal() or str(int(frame)) != frame:
                raise Rejected("invalid_message")
            if not integer(msg["captured_at_ms"]) or not integer(msg["valid_for_ms"], True):
                raise Rejected("invalid_message")
        identifier(obs["tracker_epoch"])
        if not isinstance(obs["objects"], list) or len(obs["objects"]) > 20:
            raise Rejected("invalid_message")
        tracks = set()
        for obj in obs["objects"]:
            fields(obj, OBJECT)
            track = obj["track_id"]
            if track is not None:
                identifier(track)
                if track in tracks:
                    raise Rejected("invalid_message")
                tracks.add(track)
            if (not isinstance(obj["class_name"], str) or obj["class_name"] not in CLASSES
                    or type(obj["confidence"]) not in (int, float)
                    or not math.isfinite(obj["confidence"]) or not 0 <= obj["confidence"] <= 1
                    or obj["direction"] not in ("left", "center", "right", "unknown")
                    or obj["movement"] not in ("approaching", "receding", "crossing", "stable", "unknown")
                    or (obj["stair_direction"] not in ("up", "down", "unknown")
                        if obj["class_name"] == "stairs" else obj["stair_direction"] is not None)):
                raise Rejected("invalid_message")
        if audio is not None:
            identifier(audio["observation_id"])
            if (not isinstance(audio["text"], str) or not audio["text"].strip()
                    or len(audio["text"]) > 120 or type(audio["directional"]) is not bool):
                raise Rejected("invalid_message")
            if any(audio[k] != obs[k] for k in ("session_id", "frame_id", "captured_at_ms")):
                raise Rejected("reference_mismatch")
            if audio["observation_id"] != obs["message_id"] or audio["message_id"] == obs["message_id"]:
                raise Rejected("reference_mismatch")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise Rejected("invalid_message") from exc


@dataclass(frozen=True)
class Profile:
    """Contract #12 defaults; experimental, not validated safety margins."""
    validity_ms: int = 1000
    timeout_ms: int = 2000
    angle_deg: float = 15

    def __post_init__(self):
        if (not integer(self.validity_ms, True) or not integer(self.timeout_ms, True)
                or type(self.angle_deg) not in (int, float)
                or not math.isfinite(self.angle_deg) or not 0 <= self.angle_deg <= 180):
            raise ValueError("invalid experimental profile")


@dataclass(frozen=True)
class Orientation:
    """Explicit synthetic 3D orientation; never a sensor measurement."""
    quaternion: tuple
    reference: str = "simulated"
    valid: bool = True

    def __post_init__(self):
        identifier(self.reference)
        if type(self.valid) is not bool or len(self.quaternion) != 4:
            raise ValueError("invalid simulated orientation")
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in self.quaternion):
            raise ValueError("invalid quaternion")
        norm = math.hypot(*self.quaternion)
        if norm == 0:
            raise ValueError("zero quaternion")
        object.__setattr__(self, "quaternion", tuple(v / norm for v in self.quaternion))

    @classmethod
    def yaw(cls, degrees, *, valid=True, reference="simulated"):
        if not math.isfinite(degrees):
            raise ValueError("invalid yaw")
        half = math.radians(degrees) / 2
        return cls((math.cos(half), 0, 0, math.sin(half)), reference, valid)

    def separation(self, other):
        if not self.valid or not other.valid or self.reference != other.reference:
            raise Rejected("orientation_invalid")
        dot = abs(sum(a * b for a, b in zip(self.quaternion, other.quaternion)))
        return math.degrees(2 * math.acos(min(1.0, dot)))


@dataclass(frozen=True)
class LocalState:
    orientation: Orientation
    urgent: bool = False

    def __post_init__(self):
        if not isinstance(self.orientation, Orientation) or type(self.urgent) is not bool:
            raise ValueError("invalid simulated state")


@dataclass(frozen=True)
class Capture:
    session_id: str
    frame_id: str
    captured_at_ms: int
    jpeg: bytes
    orientation: Orientation

    def metadata(self):
        return {"version": "0.1", "session_id": self.session_id,
                "frame_id": self.frame_id, "captured_at_ms": self.captured_at_ms}


def multipart(capture):
    boundary = "sonar-" + uuid4().hex
    metadata = json.dumps(capture.metadata(), separators=(",", ":")).encode()
    chunks = []
    for name, content_type, data, filename in (
            ("metadata", "application/json", metadata, ""),
            ("image", "image/jpeg", capture.jpeg, '; filename="capture.jpg"')):
        header = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"{filename}\r\n"
                  f"Content-Type: {content_type}\r\n\r\n").encode()
        chunks.extend((header, data, b"\r\n"))
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class HTTPS:
    """Verified TLS, no redirects. One worker remains guarded even after timeout.

    DNS may outlive the deadline; no replacement worker/capture is queued.
    Abandoned workers check the deadline after connect before sending pixels.
    """
    def __init__(self, endpoint, token, *, ca_file=None, profile=Profile()):
        url = urlsplit(endpoint)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/", "/v1/inference")):
            raise ValueError("endpoint must be HTTPS /v1/inference without credentials or query")
        if not isinstance(token, str) or not token or not token.isascii() or any(
                ord(c) <= 32 or ord(c) == 127 for c in token):
            raise ValueError("invalid external credential")
        self.host, self.port = url.hostname, url.port or 443
        self.token, self.profile = token, profile
        self.context = ssl.create_default_context(cafile=ca_file)
        self._active = Lock()

    def ready(self):
        return not self._active.locked()

    def send(self, capture):
        if not self._active.acquire(blocking=False):
            raise Rejected("busy")
        finished, cancelled = Event(), Event()
        result = []
        connection = http.client.HTTPSConnection(
            self.host, self.port, context=self.context, timeout=self.profile.timeout_ms / 1000)
        deadline = monotonic() + self.profile.timeout_ms / 1000

        def remaining():
            value = deadline - monotonic()
            if value <= 0 or cancelled.is_set():
                raise Rejected("timeout")
            if connection.sock is not None:
                connection.sock.settimeout(value)
            return value

        def worker():
            try:
                body, content_type = multipart(capture)
                connection.connect()
                remaining()
                connection.request("POST", "/v1/inference", body, {
                    "Content-Type": content_type, "Authorization": "Bearer " + self.token})
                remaining()
                response = connection.getresponse()
                if response.status != 200:
                    raise Rejected("http_" + str(response.status))
                if response.getheader("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                    raise Rejected("invalid_content_type")
                length = response.getheader("Content-Length")
                if length is not None and (not length.isdecimal() or int(length) > MAX_BODY):
                    raise Rejected("response_too_large")
                data = bytearray()
                while True:
                    remaining()
                    chunk = response.read1(min(4096, MAX_BODY + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > MAX_BODY:
                        raise Rejected("response_too_large")
                remaining()
                result.append(bytes(data))
            except Rejected as exc:
                result.append(exc)
            except ssl.SSLError:
                result.append(Rejected("tls_error"))
            except (TimeoutError, socket.timeout):
                result.append(Rejected("timeout"))
            except (OSError, http.client.HTTPException, ValueError):
                result.append(Rejected("network_error"))
            finally:
                connection.close()
                self._active.release()
                finished.set()

        Thread(target=worker, daemon=True).start()
        if not finished.wait(max(0, deadline - monotonic())):
            cancelled.set()
            sock = connection.sock
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            raise Rejected("timeout")
        if isinstance(result[0], Rejected):
            raise result[0]
        return result[0]


class Simulator:
    """Single exchange, bounded capture/ID memory; explicit local state only."""
    def __init__(self, *, clock=lambda: int(monotonic() * 1000), profile=Profile()):
        self.clock, self.profile = clock, profile
        self._active = Lock()
        self.restart()

    def restart(self):
        self.session_id = uuid4().hex
        self.counter = 0
        self._seen = {}
        self._last_capture = -1
        self._released_at = -1
        self._urgent = False

    def update_local(self, state):
        if self._urgent and not state.urgent:
            self._released_at = self.clock()
        self._urgent = state.urgent

    def admit(self, body, capture, local):
        value = parse_response(body)
        obs, audio = value["observation"], value["audio"]
        if capture.session_id != self.session_id or obs["session_id"] != self.session_id:
            raise Rejected("session_mismatch")
        if obs["frame_id"] != capture.frame_id or obs["captured_at_ms"] != capture.captured_at_ms:
            raise Rejected("capture_mismatch")
        now = self.clock()
        age = now - capture.captured_at_ms
        if age < 0:
            self._seen.clear()
            raise Rejected("clock_regression")
        if age >= min(obs["valid_for_ms"], self.profile.validity_ms):
            raise Rejected("expired")
        self._seen = {k: v for k, v in self._seen.items() if now < v[0]}
        ids = [obs["message_id"]] + ([audio["message_id"]] if audio else [])
        for msg in [obs] + ([audio] if audio else []):
            previous = self._seen.get(msg["message_id"])
            if previous is not None:
                raise Rejected("duplicate" if previous[1] == msg else "id_conflict")
        if len(self._seen) + len(ids) > 64:
            raise Rejected("capacity")
        if capture.captured_at_ms < self._last_capture:
            raise Rejected("out_of_order")
        self._last_capture = capture.captured_at_ms
        for msg in [obs] + ([audio] if audio else []):
            self._seen[msg["message_id"]] = (
                capture.captured_at_ms + min(msg["valid_for_ms"], self.profile.validity_ms), msg)
        self.update_local(local)
        reason = "no_suggestion"
        if audio:
            reason = "accepted"
            if age >= min(audio["valid_for_ms"], obs["valid_for_ms"], self.profile.validity_ms):
                reason = "expired"
            elif local.urgent:
                reason = "local_urgent"
            elif capture.captured_at_ms <= self._released_at:
                reason = "before_urgent_release"
            elif audio["directional"]:
                try:
                    if capture.orientation.separation(local.orientation) > self.profile.angle_deg + 1e-9:
                        reason = "orientation_changed"
                except Rejected as exc:
                    reason = str(exc)
        return {"observation": "accepted", "audio": reason,
                "observation_id": obs["message_id"], "tracker_epoch": obs["tracker_epoch"],
                "captured_at_ms": obs["captured_at_ms"],
                "audio_text": audio["text"] if audio and reason == "accepted" else None,
                "objects": [dict(obj) for obj in obs["objects"]]}

    def exchange(self, source, transport, local):
        if not self._active.acquire(blocking=False):
            return {"outcome": "discarded", "reason": "busy"}
        capture = None
        started = self.clock()
        try:
            if not transport.ready():
                raise Rejected("busy")
            initial = local()
            self.update_local(initial)
            session = self.session_id
            frame = str(self.counter)
            self.counter += 1
            jpeg, timestamp = source.read(self.clock)
            if not integer(timestamp) or not isinstance(jpeg, bytes) or not jpeg:
                raise Rejected("capture_error")
            capture = Capture(session, frame, timestamp, jpeg, initial.orientation)
            body = transport.send(capture)
            if self.clock() - started >= self.profile.timeout_ms:
                raise Rejected("timeout")
            result = self.admit(body, capture, local())
            return {"outcome": "accepted", **result,
                    "frame_id": frame, "latency_ms": self.clock() - timestamp,
                    "jpeg_sha256": sha256(capture.jpeg).hexdigest()}
        except Rejected as exc:
            return {"outcome": "discarded", "reason": str(exc),
                    "frame_id": capture.frame_id if capture else None,
                    "latency_ms": self.clock() - capture.captured_at_ms if capture else None}
        finally:
            self._active.release()


class VirtualClock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now


# Original synthetic 8x8 black JPEG, generated in memory; AGPL-3.0-only.
FIXTURE_JPEG = base64.b64decode("/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD8qqKKKAP/2Q==")


class FixtureSource:
    def read(self, clock):
        return FIXTURE_JPEG, clock()

    def close(self):
        pass


class FixtureTransport:
    """In-process fixtures; never represented as a real HTTPS/API validation."""
    def __init__(self, clock, scenario="success"):
        if scenario not in SCENARIOS:
            raise ValueError("unknown fixture")
        self.clock, self.scenario = clock, scenario
        self.previous = None

    def ready(self):
        return True

    def send(self, capture):
        self.clock.now += {"expired": 1000, "timeout": 2000}.get(self.scenario, 100)
        if self.scenario == "disconnect":
            raise Rejected("network_error")
        if self.scenario == "unauthorized":
            raise Rejected("http_401")
        obs = {**capture.metadata(), "type": "visual_observation",
               "message_id": "obs-" + capture.frame_id, "valid_for_ms": 1000,
               "tracker_epoch": "fixture", "objects": [{
                   "track_id": "1", "class_name": "person", "confidence": 0.8,
                   "direction": "left", "movement": "unknown", "stair_direction": None}]}
        audio = {**capture.metadata(), "type": "audio_suggestion",
                 "message_id": "audio-" + capture.frame_id, "valid_for_ms": 1000,
                 "observation_id": obs["message_id"], "text": "Pessoa à esquerda",
                 "directional": True}
        value = {"observation": obs, "audio": audio}
        if self.scenario == "old_session":
            obs["session_id"] = audio["session_id"] = "previous-session"
        if self.scenario == "wrong_capture":
            obs["captured_at_ms"] = audio["captured_at_ms"] = capture.captured_at_ms + 1
        body = json.dumps(value, ensure_ascii=False).encode()
        if self.scenario == "malformed":
            body = b'{"observation":'
        if self.scenario == "oversized":
            body = b" " * (MAX_BODY + 1)
        if self.scenario == "duplicate" and self.previous is not None:
            # Reused message IDs on a newer frame constitute an ID/content conflict.
            value["observation"]["message_id"] = self.previous["observation"]["message_id"]
            value["audio"]["message_id"] = self.previous["audio"]["message_id"]
            value["audio"]["observation_id"] = value["observation"]["message_id"]
            body = json.dumps(value).encode()
        self.previous = value
        return body


class OpenCVSource:
    """Latest webcam frame in one slot, or video positioned by elapsed time."""
    def __init__(self, source, *, webcam=False, max_edge=None, jpeg_quality=95):
        if max_edge is not None and (type(max_edge) is not int or max_edge <= 0):
            raise ValueError("invalid_max_edge")
        self.max_edge = max_edge
        if type(jpeg_quality) is not int or not 1 <= jpeg_quality <= 100:
            raise ValueError("invalid_jpeg_quality")
        self.jpeg_quality = jpeg_quality
        try:
            import cv2
        except ImportError as exc:
            raise Rejected("opencv_missing") from exc
        self.cv2, self.webcam = cv2, webcam
        self.cap = cv2.VideoCapture(source)
        self._lock, self._stop, self._available = Lock(), Event(), Event()
        self._latest = None
        self._error = False
        self._started = None
        self._last_index = -1
        self._thread = None
        if not self.cap.isOpened():
            self.cap.release()
            raise Rejected("capture_error")
        if webcam:
            self._thread = Thread(target=self._reader, daemon=True)
            self._thread.start()
        else:
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(self.fps) or self.fps <= 0:
                self.close()
                raise Rejected("video_fps_invalid")

    def _reader(self):
        while not self._stop.is_set():
            ok, image = self.cap.read()
            timestamp = int(monotonic() * 1000)
            with self._lock:
                self._error = not ok
                self._latest = (image, timestamp) if ok else None
            self._available.set()
            if not ok:
                break

    def read(self, clock):
        if self.webcam:
            if not self._available.wait(2):
                raise Rejected("capture_timeout")
            with self._lock:
                if self._error or self._latest is None:
                    raise Rejected("capture_error")
                image, timestamp = self._latest
                self._latest = None
                self._available.clear()
        else:
            now = clock()
            if self._started is None:
                self._started = now
            index = max(self._last_index + 1, int((now - self._started) * self.fps / 1000))
            if index != self._last_index + 1:
                if not self.cap.set(self.cv2.CAP_PROP_POS_FRAMES, index):
                    raise Rejected("video_seek_failed")
            ok, image = self.cap.read()
            timestamp = clock()
            self._last_index = index
            if not ok:
                raise Rejected("source_ended_or_decode_failed")
        if self.max_edge is not None:
            ratio = min(1, self.max_edge / max(image.shape[:2]))
            if ratio < 1:
                image = self.cv2.resize(image, (max(1, round(image.shape[1]*ratio)),
                    max(1, round(image.shape[0]*ratio))), interpolation=self.cv2.INTER_AREA)
        ok, jpeg = self.cv2.imencode(".jpg", image, [self.cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        if not ok:
            raise Rejected("capture_error")
        return jpeg.tobytes(), timestamp

    def close(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.5)
        self.cap.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Simulador #30; entradas locais sintéticas, sem sensores/TTS.")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--fixture", choices=SCENARIOS)
    sources.add_argument("--video")
    sources.add_argument("--webcam", type=int)
    parser.add_argument("--source-id", help="Identificador não pessoal e origem do vídeo/webcam")
    parser.add_argument("--endpoint")
    parser.add_argument("--ca-file")
    parser.add_argument("--frames", type=int, default=3)
    parser.add_argument("--max-edge", type=int, help="explicit upload resize, aspect ratio preserved")
    parser.add_argument("--jpeg-quality", type=int, help="explicit JPEG quality 1..100; default 95")
    parser.add_argument("--fps", type=float, help="maximum requested cadence; no stale frame queue")
    parser.add_argument("--report", type=Path, help="new private JSONL receipts; no images or token")
    parser.add_argument("--capture-yaw", type=float, default=0)
    parser.add_argument("--current-yaw", type=float, default=0)
    parser.add_argument("--orientation-invalid", action="store_true")
    parser.add_argument("--urgent", action="store_true")
    args = parser.parse_args(argv)
    if args.frames <= 0 or (args.webcam is not None and args.webcam < 0):
        parser.error("frames must be positive and webcam nonnegative")
    if args.fixture and (args.endpoint or args.ca_file):
        parser.error("fixtures are in-process; omit HTTPS options")
    if not args.fixture and (not args.endpoint or not args.source_id):
        parser.error("real capture requires --endpoint and --source-id")
    if args.max_edge is not None and (args.max_edge <= 0 or args.fixture):
        parser.error("max-edge must be positive and only applies to real capture")
    if args.jpeg_quality is not None and (not 1 <= args.jpeg_quality <= 100 or args.fixture):
        parser.error("jpeg-quality must be 1..100 and only applies to real capture")
    if args.fps is not None and (not math.isfinite(args.fps) or args.fps <= 0 or args.fixture):
        parser.error("fps must be positive finite and only applies to real capture")
    source, report = None, None
    try:
        initial = LocalState(Orientation.yaw(args.capture_yaw), args.urgent)
        current = LocalState(Orientation.yaw(args.current_yaw, valid=not args.orientation_invalid), args.urgent)
        clock = VirtualClock() if args.fixture else lambda: int(monotonic() * 1000)
        client = Simulator(clock=clock)
        if args.fixture:
            source = FixtureSource()
            transport = FixtureTransport(clock, args.fixture)
        else:
            token = os.environ.get("SONAR_VISION_TOKEN", "")
            transport = HTTPS(args.endpoint, token, ca_file=args.ca_file)
            source = OpenCVSource(args.video if args.video else args.webcam, webcam=args.webcam is not None,
                                  max_edge=args.max_edge, jpeg_quality=args.jpeg_quality if args.jpeg_quality is not None else 95)
        if args.report:
            report = os.fdopen(os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w")
            digest = None
            if args.video:
                hasher = sha256()
                with open(args.video, "rb") as original:
                    for chunk in iter(lambda: original.read(1024*1024), b""):
                        hasher.update(chunk)
                digest = hasher.hexdigest()
            report.write(json.dumps({"schema_version": 1, "kind": "private_client_receipts",
                        "source_id": args.fixture or args.source_id, "video_sha256": digest,
                        "local_inputs": "simulated", "requested_fps": args.fps, "upload_max_edge": args.max_edge,
                        "upload_jpeg_quality": args.jpeg_quality if args.jpeg_quality is not None else 95})+"\n")
            report.flush()
        print(json.dumps({"mode": "in_process_fixture" if args.fixture else "https",
                          "local_inputs": "simulated", "profile": vars(client.profile),
                          "source": args.fixture or args.source_id}, ensure_ascii=True))
        next_frame = monotonic()
        for _ in range(args.frames):
            if args.fps is not None:
                sleep(max(0, next_frame - monotonic()))
            states = iter((initial, current))
            result = client.exchange(source, transport, lambda: next(states))
            if args.video and isinstance(source, OpenCVSource):
                result["source_frame_index"] = source._last_index
            print(json.dumps(result, ensure_ascii=True))
            if report is not None:
                report.write(json.dumps(result, ensure_ascii=True)+"\n")
                report.flush()
            if args.fps is not None:
                next_frame = max(next_frame + 1/args.fps, monotonic())
            if result.get("reason") in ("source_ended_or_decode_failed", "capture_error", "capture_timeout"):
                break
        return 0
    except (Rejected, ValueError, OSError):
        # Never log arbitrary exception strings, URLs, tokens, image paths or response text.
        print(json.dumps({"outcome": "discarded", "reason": "configuration_or_source_error"}))
        return 2
    finally:
        if source:
            source.close()
        if report is not None:
            report.close()


if __name__ == "__main__":
    raise SystemExit(main())
