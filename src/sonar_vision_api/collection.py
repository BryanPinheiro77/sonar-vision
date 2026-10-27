"""Opt-in private rounds (#73). Only this worker writes; inference never waits for disk."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
import re
import shutil
from threading import BoundedSemaphore, Event, Lock, RLock, Thread
from time import monotonic, time
from uuid import uuid4

from sonar_vision.core import identifier

from .validation import _no_constants, _no_duplicates

TOTAL_BYTES = 100 * 1024 * 1024
MAX_ROUNDS = 100
QUEUE_SIZE = 8
MAX_EVENTS = 20000
HEX = re.compile(r"[0-9a-f]{32}")
SAMPLE = re.compile(r"[0-9a-f]{64}")
MARKER = {"kind": "sonar_vision_experimental_rounds", "version": 1}


def _json(raw):
    return json.loads(raw, object_pairs_hook=_no_duplicates, parse_constant=_no_constants)


def _encoded(value):
    return (json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode()


def _write_new(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(data)


@dataclass(frozen=True)
class CollectionConfig:
    round_id: str
    source_id: str
    permission_ref: str
    max_duration_seconds: int
    max_frames: int
    max_bytes: int
    retention_seconds: int

    def __post_init__(self):
        if not HEX.fullmatch(self.round_id):
            raise ValueError("round_id must be a new UUID hex")
        identifier(self.source_id)
        identifier(self.permission_ref)
        for value, ceiling in ((self.max_duration_seconds, 600), (self.max_frames, 3000),
                               (self.max_bytes, TOTAL_BYTES), (self.retention_seconds, 86400)):
            if type(value) is not int or not 0 < value <= ceiling:
                raise ValueError("collection limits must be explicit, positive and within approved ceilings")

    @classmethod
    def load(cls, path):
        if Path(path).stat().st_size > 8192:
            raise ValueError("collection configuration too large")
        return cls(**_json(Path(path).read_bytes()))


class RoundArchive:
    """A bounded index of committed own files, shared by recording and read-only history.

    Metadata is indexed in memory, while immutable JPEGs and an append-only
    journal persist on the private volume. Partial trailing journal lines after
    interruption are ignored. Old rounds are never reopened for writing.
    """

    def __init__(self, root, *, wall_clock=time, clock=monotonic, automatic_cleanup=True):
        self.root = Path(root)
        self.wall_clock, self.clock = wall_clock, clock
        if self.root.is_symlink():
            raise ValueError("archive directory must not be a symlink")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.root.stat().st_mode & 0o077:
            raise ValueError("archive directory must be private (chmod 700)")
        self.root = self.root.resolve()
        marker = self.root / ".sonar-archive.json"
        if not marker.exists():
            if any(self.root.iterdir()):
                raise ValueError("refusing an unregistered nonempty archive directory")
            _write_new(marker, _encoded(MARKER))
        if marker.is_symlink() or marker.stat().st_size > 1024 or _json(marker.read_bytes()) != MARKER:
            raise ValueError("invalid archive ownership marker")
        self._ownership = marker.open("rb")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._ownership.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._ownership, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._ownership.close()
            raise ValueError("archive is already open; stop API before offline cleanup") from None
        try:
            self._lock = Lock()
            # Disk mutation and quota scans share a lock, separate from the index.
            self._storage_lock = RLock()
            self._rounds = {}
            self._leases = Counter()
            self._history_download = BoundedSemaphore(1)
            self._history_reads = BoundedSemaphore(2)
            self.recording = None
            self.total_bytes = self._disk_bytes()
            if self.total_bytes > TOTAL_BYTES:
                raise ValueError("archive exceeds aggregate 100 MiB capacity")
            directories = list(self.root.iterdir())
            if len(directories) > MAX_ROUNDS + 1:
                raise ValueError("archive exceeds bounded round count")
            for directory in directories:
                if directory.name == marker.name:
                    continue
                if not directory.is_dir() or not HEX.fullmatch(directory.name):
                    raise ValueError("unregistered archive entry")
                self._load(directory)
            self._closed = False
            self._house_stop = Event()
            self._house = Thread(target=self._housekeep, name="sonar-retention", daemon=True) if automatic_cleanup else None
            if self._house:
                self._house.start()
        except BaseException:
            self._ownership.close()
            raise

    def _housekeep(self):
        while not self._house_stop.wait(1):
            try:
                self.cleanup(dry_run=False)
            except (OSError, ValueError):
                # Fail closed on reads by expiry even if deletion needs operator repair.
                pass

    def _disk_bytes(self):
        size = 0
        for base, dirs, files in os.walk(self.root, followlinks=False):
            for name in dirs + files:
                path = Path(base) / name
                if path.is_symlink():
                    raise ValueError("symlinks are forbidden in the collection area")
            for name in files:
                try:
                    size += (Path(base) / name).stat().st_size
                except FileNotFoundError:
                    pass  # own retention may remove another expired round
        return size

    def _directory(self, round_id):
        if not isinstance(round_id, str) or not HEX.fullmatch(round_id):
            raise ValueError("invalid round identifier")
        directory = self.root / round_id
        if directory.is_symlink():
            raise ValueError("round symlink refused")
        return directory

    def _validate_tree(self, directory):
        for entry in directory.iterdir():
            if entry.is_symlink():
                raise ValueError("round contains symlink")
            if entry.name == "frames" and entry.is_dir():
                for image in entry.iterdir():
                    if image.is_symlink() or not image.is_file() or not SAMPLE.fullmatch(image.stem) or image.suffix != ".jpg":
                        raise ValueError("unregistered frame entry")
            elif entry.name not in ("manifest.json", "manifest.json.tmp", "events.jsonl") or not entry.is_file():
                raise ValueError("unregistered round artifact")

    def _load(self, directory):
        self._validate_tree(directory)
        manifest = directory / "manifest.json"
        if not manifest.is_file() or manifest.stat().st_size > 65536:
            raise ValueError("missing or excessive round manifest; operator recovery required")
        info = _json(manifest.read_bytes())
        if info.get("kind") != "sonar_vision_collection_round" or info.get("round_id") != directory.name:
            raise ValueError("unregistered round manifest")
        CollectionConfig(**info["limits"])
        if info.get("state") == "recording":
            info.update(state="interrupted", reason="process_interrupted")
        record = {"info": info, "frames": {}, "tof": [], "events": 0}
        journal = directory / "events.jsonl"
        if journal.exists():
            with journal.open("rb") as stream:
                while line := stream.readline(65537):
                    if len(line) > 65536:
                        raise ValueError("oversized collection journal row")
                    if not line.endswith(b"\n"):
                        info["recovery"] = "incomplete_tail_ignored"
                        break
                    self._apply(record, _json(line))
        info["frame_count"], info["tof_count"] = len(record["frames"]), len(record["tof"])
        self._rounds[directory.name] = record

    def _apply(self, record, event):
        record["events"] += 1
        if record["events"] > MAX_EVENTS:
            raise ValueError("round event index limit")
        kind, data = event["kind"], event["data"]
        if kind == "frame":
            sample = data["sample_id"]
            if not SAMPLE.fullmatch(sample) or len(record["frames"]) >= 3000:
                raise ValueError("frame index limit or invalid sample")
            record["frames"][sample] = data
        elif kind == "prediction":
            frame = record["frames"].get(data["sample_id"])
            if frame:
                self._check_prediction(frame, data)
                # sample_id includes source/boot/frame/capture/JPEG hash.
                frame["prediction_status"] = data["status"]
                frame["predictions"] = data.get("predictions")
        elif kind == "tof":
            if len(record["tof"]) >= 6000:
                raise ValueError("ToF event index limit")
            record["tof"].append(data)
        else:
            raise ValueError("invalid collection event")

    @staticmethod
    def _check_prediction(frame, data):
        if data["status"] not in ("available", "failed", "unavailable"):
            raise ValueError("invalid prediction status")
        prediction = data.get("predictions")
        if data["status"] == "available" and (not isinstance(prediction, dict) or
                any(prediction.get(k) != frame[k] for k in ("frame_id", "captured_at_ms", "jpeg_sha256")) or
                prediction.get("session_hash") != sha256(frame["session_id"].encode()).hexdigest()):
            raise ValueError("archived prediction correlation mismatch")

    def start(self, config, source, models):
        with self._storage_lock:
            self.cleanup(dry_run=False)
            if self.recording is not None or len(self._rounds) >= MAX_ROUNDS:
                raise ValueError("one explicit recording per process; round count bounded")
            directory = self._directory(config.round_id)
            if directory.exists():
                raise ValueError("round already exists; never overwrite or reopen a prior round")
            created = self.wall_clock()
            info = {"kind": "sonar_vision_collection_round", "version": 1,
                    "round_id": config.round_id, "source": source,
                    "permission_ref": config.permission_ref, "source_id": config.source_id,
                    "models": models, "limits": asdict(config), "created_at_ms": int(created * 1000),
                    "expires_at_ms": int((created + config.retention_seconds) * 1000),
                    "state": "recording", "reason": None, "drops": {},
                    "frame_count": 0, "tof_count": 0, "bytes_written": 0}
            initial = _encoded(info)
            if len(initial) + 4096 >= config.max_bytes or self.total_bytes + len(initial) + 4096 >= TOTAL_BYTES:
                raise ValueError("insufficient collection budget for manifest and final status")
            directory.mkdir(mode=0o700)
            (directory / "frames").mkdir(mode=0o700)
            _write_new(directory / "manifest.json", initial)
            _write_new(directory / "events.jsonl", b"")
            self.total_bytes += len(initial)
            info["bytes_written"] = len(initial)
            self._rounds[config.round_id] = {"info": info, "frames": {}, "tof": [], "events": 0}
            self.recording = Recording(self, config)
            return self.recording

    @staticmethod
    def sample_id(source, frame):
        return sha256(_encoded([source["device_id"], source["session_id"], frame["frame_id"],
                                frame["captured_at_ms"], frame["jpeg_sha256"]])).hexdigest()

    def _record(self, recording, kind, data, jpeg):
        with self._storage_lock:
            record = self._rounds[recording.config.round_id]
            info = record["info"]
            if kind == "prediction" and data["sample_id"] not in record["frames"]:
                recording.drops["prediction_without_saved_frame"] += 1
                return
            if kind == "prediction":
                self._check_prediction(record["frames"][data["sample_id"]], data)
            if kind == "frame" and len(record["frames"]) >= recording.config.max_frames:
                recording.stop("frame_limit")
                return
            if (kind == "tof" and len(record["tof"]) >= 6000) or record["events"] >= MAX_EVENTS:
                recording.stop("event_limit")
                return
            encoded = _encoded({"kind": kind, "data": data})
            size = len(encoded) + (len(jpeg) if jpeg else 0)
            if len(encoded) > 65536 or info["bytes_written"] + size + 4096 > recording.config.max_bytes:
                recording.stop("byte_limit")
                return
            if self.total_bytes + size + 4096 > TOTAL_BYTES:
                recording.stop("aggregate_byte_limit")
                return
            directory = self._directory(recording.config.round_id)
            if jpeg is not None:
                _write_new(directory / "frames" / (data["sample_id"] + ".jpg"), jpeg)
            with (directory / "events.jsonl").open("ab", buffering=0) as stream:
                stream.write(encoded)
            with self._lock:
                self._apply(record, {"kind": kind, "data": data})
                info["bytes_written"] += size
                self.total_bytes += size
                info["frame_count"], info["tof_count"] = len(record["frames"]), len(record["tof"])
            if kind == "frame" and info["frame_count"] >= recording.config.max_frames:
                recording.stop("frame_limit")

    def _finish(self, recording):
        with self._storage_lock:
            record = self._rounds[recording.config.round_id]
            with self._lock:
                record["info"].update(state="failed" if recording.reason == "write_error" else "completed",
                                      reason=recording.reason, drops=dict(recording.drops))
                data = _encoded(record["info"])
            path = self._directory(recording.config.round_id) / "manifest.json"
            temporary = path.with_suffix(".json.tmp")
            # A failed disk may prevent even this status from persisting. Recovery
            # then labels the old 'recording' manifest interrupted, never complete.
            with temporary.open("wb") as stream:
                os.chmod(temporary, 0o600)
                stream.write(data)
            os.replace(temporary, path)
            self.total_bytes = self._disk_bytes()

    def _visible(self, round_id):
        self._directory(round_id)
        record = self._rounds.get(round_id)
        if not record or self.wall_clock() * 1000 >= record["info"]["expires_at_ms"]:
            raise KeyError("round unavailable or expired")
        return record

    def summaries(self):
        with self._lock:
            return [{k: v for k, v in r["info"].items() if k != "permission_ref"}
                    for r in sorted(self._rounds.values(), key=lambda r: r["info"]["created_at_ms"], reverse=True)
                    if self.wall_clock() * 1000 < r["info"]["expires_at_ms"]]

    def timeline(self, round_id):
        with self._lock:
            record = self._visible(round_id)
            return {"round": dict(record["info"]),
                    "frames": [dict(f) for f in record["frames"].values()],
                    "tof": [dict(t) for t in record["tof"]]}

    def frame(self, round_id, sample_id):
        if not SAMPLE.fullmatch(sample_id):
            raise ValueError("invalid sample identifier")
        with self._lock:
            row = dict(self._visible(round_id)["frames"][sample_id])
        path = self._directory(round_id) / "frames" / (sample_id + ".jpg")
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError("frame symlink refused")
        if path.stat().st_size > 512 * 1024:
            raise ValueError("excessive archived image")
        data = path.read_bytes()
        if sha256(data).hexdigest() != row["jpeg_sha256"]:
            raise ValueError("archived frame hash mismatch")
        return data

    def cleanup(self, *, dry_run=True):
        with self._storage_lock:
            removed, eligible, refused = [], [], []
            with self._lock:
                candidates = [key for key, r in self._rounds.items()
                              if self.wall_clock() * 1000 >= r["info"]["expires_at_ms"]
                              and not self._leases[key]
                              and not (self.recording and self.recording.thread.is_alive() and self.recording.config.round_id == key)]
            for key in candidates:
                directory = self._directory(key)
                try:
                    self._validate_tree(directory)
                    marker = _json((directory / "manifest.json").read_bytes())
                    if marker.get("kind") != "sonar_vision_collection_round" or marker.get("round_id") != key:
                        raise ValueError("ownership marker changed")
                    eligible.append(key)
                    if not dry_run:
                        shutil.rmtree(directory)
                        with self._lock:
                            self._rounds.pop(key, None)
                        removed.append(key)
                except (OSError, ValueError):
                    refused.append(key)
            if removed:
                self.total_bytes = self._disk_bytes()
            return {"dry_run": dry_run, "eligible": eligible, "removed": removed, "refused": refused}

    def close(self):
        if self._closed:
            return
        self._closing = True
        with self._lock:
            if any(self._leases.values()):
                return
        if self.recording:
            self.recording.stop("operator_stop")
            self.recording.thread.join(3)
            if self.recording.thread.is_alive():
                return  # don't release filesystem ownership under an active writer
        self._house_stop.set()
        if self._house:
            self._house.join(3)
            if self._house.is_alive():
                return
        self._ownership.close()
        self._closed = True


class Recording:
    def __init__(self, archive, config):
        self.archive, self.config = archive, config
        self.source = archive._rounds[config.round_id]["info"]["source"]
        self.queue = Queue(maxsize=QUEUE_SIZE)
        self.enabled, self.reason, self.drops = True, None, Counter()
        self.started = archive.clock()
        self.thread = Thread(target=self._run, name="sonar-collection", daemon=True)
        self.thread.start()

    def stop(self, reason):
        if self.enabled:
            self.enabled, self.reason = False, reason

    def offer(self, kind, data, jpeg=None):
        if not self.enabled:
            return
        if jpeg is not None and len(jpeg) > 512 * 1024:
            self.drops["image_exceeds_collection_limit"] += 1
            return
        if self.archive.clock() - self.started >= self.config.max_duration_seconds:
            self.stop("duration_limit")
            return
        try:
            self.queue.put_nowait((kind, data, jpeg))
        except Full:
            self.drops["queue_full"] += 1

    def _run(self):
        try:
            while self.enabled or not self.queue.empty():
                if self.archive.clock() - self.started >= self.config.max_duration_seconds:
                    self.stop("duration_limit")
                if self.archive.wall_clock() * 1000 >= self.archive._rounds[self.config.round_id]["info"]["expires_at_ms"]:
                    self.stop("retention_expired")
                try:
                    kind, data, jpeg = self.queue.get(timeout=.1)
                except Empty:
                    continue
                if self.reason in ("frame_limit", "byte_limit", "aggregate_byte_limit", "event_limit"):
                    self.drops["capacity"] += 1
                    continue
                self.archive._record(self, kind, data, jpeg)
        except Exception:
            self.enabled, self.reason = False, "write_error"
        finally:
            self.enabled = False
            # Release all queued JPEG references even after a write failure.
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.drops["not_written"] += 1
                except Empty:
                    break
            try:
                self.archive._finish(self)
            except Exception:
                self.reason = "write_error"
                with self.archive._lock:
                    self.archive._rounds[self.config.round_id]["info"].update(state="failed", reason="write_error")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    config = sub.add_parser("configure", help="create a new explicit round configuration")
    config.add_argument("--output", type=Path, required=True)
    config.add_argument("--source-id", required=True)
    config.add_argument("--permission-ref", required=True)
    config.add_argument("--seconds", type=int, default=600)
    config.add_argument("--frames", type=int, default=3000)
    config.add_argument("--bytes", type=int, default=TOTAL_BYTES)
    config.add_argument("--retention-seconds", type=int, default=86400)
    cleanup = sub.add_parser("cleanup", help="dry-run unless --execute; only own expired rounds")
    cleanup.add_argument("--directory", type=Path, required=True)
    cleanup.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.command == "configure":
        value = CollectionConfig(uuid4().hex, args.source_id, args.permission_ref, args.seconds,
                                 args.frames, args.bytes, args.retention_seconds)
        _write_new(args.output, _encoded(asdict(value)))
        print(json.dumps({"round_id": value.round_id, "limits": asdict(value)}))
    else:
        if not (args.directory / ".sonar-archive.json").is_file():
            parser.error("cleanup requires an existing registered archive")
        archive = RoundArchive(args.directory, automatic_cleanup=False)
        try:
            print(json.dumps(archive.cleanup(dry_run=not args.execute)))
        finally:
            archive.close()


if __name__ == "__main__":
    main()
