"""Opt-in private, bounded JSONL predictions. No images, wire change or endpoint."""

from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread


class PredictionJournal:
    """A slow/full/failing disk drops diagnostics without queuing inference work."""

    def __init__(
        self,
        path: Path,
        configuration: dict,
        *,
        max_bytes=64 * 1024 * 1024,
        capacity=64,
    ):
        self._stream = os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
        )
        self._queue = Queue(maxsize=capacity)
        self._stop = Event()
        self.max_bytes, self.written, self.dropped, self.failed = max_bytes, 0, 0, False
        try:
            header = (
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "private_prediction_journal",
                        "configuration": configuration,
                        "scope": "server processed; not client admission or physical risk",
                    }
                )
                + "\n"
            )
            self._stream.write(header)
            self._stream.flush()
            self.written = len(header.encode())
        except Exception:
            self._stream.close()
            raise
        self._thread = Thread(target=self._drain, name="sonar-diagnostics", daemon=True)
        self._thread.start()

    def record(self, result, jpeg, *, abandoned=False):
        if self.failed or self._stop.is_set():
            self.dropped += 1
            return
        row = {
            "message_id": result.message_id,
            "frame_id": result.frame_id,
            "session_hash": sha256(result.session_id.encode()).hexdigest(),
            "captured_at_ms": result.captured_at_ms,
            "tracker_epoch": result.tracker_epoch,
            "jpeg_sha256": sha256(jpeg).hexdigest(),
            "processing_ms": result.processing_ms,
            "abandoned_at_record_time": bool(abandoned),
            "camera_motion": "unknown",
            "detections": [
                {
                    "class_name": d.class_name,
                    "confidence": d.confidence,
                    "box": list(d.box),
                    "track_id": d.track_id,
                    "stair_direction": d.stair_direction,
                }
                for d in result.detections
            ],
        }
        try:
            self._queue.put_nowait(json.dumps(row, separators=(",", ":")) + "\n")
        except Full:
            self.dropped += 1

    def _drain(self):
        try:
            while not self._stop.is_set() or not self._queue.empty():
                try:
                    line = self._queue.get(timeout=0.1)
                except Empty:
                    continue
                size = len(line.encode())
                if self.written + size > self.max_bytes:
                    self.dropped += 1
                    continue
                self._stream.write(line)
                self._stream.flush()
                self.written += size
        except (OSError, ValueError):
            self.failed = True
        finally:
            self._stream.close()

    def close(self):
        self._stop.set()
        self._thread.join(3)
