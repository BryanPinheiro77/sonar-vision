"""Bounded read-only history and streaming ZIP exports. No inference or disk writes."""

import asyncio
from io import RawIOBase
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import monotonic
from zipfile import ZipFile, ZIP_STORED

from .collection import _encoded
from .errors import ApiError

MAX_TIMELINE_BYTES = 16 * 1024 * 1024
DOWNLOAD_SECONDS = 90


class HistoryReader:
    def __init__(self, archive):
        self.archive = archive
        self._reads = archive._history_reads
        self._download = archive._history_download

    async def read(self, function, *args):
        if not self._reads.acquire(blocking=False):
            raise ApiError(429, "history_read_busy")
        work = asyncio.create_task(asyncio.to_thread(function, *args))
        work.add_done_callback(lambda task: self._reads.release())
        return await asyncio.shield(work)

    def timeline(self, round_id):
        data = self.archive.timeline(round_id)
        data["round"].pop("permission_ref", None)
        data["round"]["limits"] = {k: v for k, v in data["round"]["limits"].items() if k != "permission_ref"}
        encoded = _encoded(data)
        if len(encoded) > MAX_TIMELINE_BYTES:
            raise ApiError(413, "history_timeline_limit")
        return encoded

    def summaries(self):
        rows = self.archive.summaries()
        for row in rows:
            row["limits"] = {k: v for k, v in row["limits"].items() if k != "permission_ref"}
        return rows

    def download(self, round_id):
        if not self._download.acquire(blocking=False):
            raise ApiError(429, "history_download_busy")
        try:
            with self.archive._lock:
                self.archive._visible(round_id)
                self.archive._leases[round_id] += 1
            try:
                data = self.archive.timeline(round_id)
            except BaseException:
                with self.archive._lock:
                    self.archive._leases[round_id] -= 1
                raise
            try:
                return ZipDownload(self, round_id, data)
            except BaseException:
                with self.archive._lock:
                    self.archive._leases[round_id] -= 1
                raise
        except BaseException:
            self._download.release()
            raise


class ZipDownload(RawIOBase):
    """Unseekable ZIP sink, 2×64 KiB queue, one producer and 90-second lease.

    No temporary ZIP on disk or complete archive in RAM. Cancellation wakes the
    producer; retention never deletes its round while files are being read.
    """

    def __init__(self, reader, round_id, data):
        self.reader, self.round_id, self.data = reader, round_id, data
        self.queue, self.stop = Queue(maxsize=2), Event()
        self.deadline = monotonic() + DOWNLOAD_SECONDS
        self.position = 0
        self.error = None
        self.thread = Thread(target=self._produce, name="sonar-download", daemon=True)
        self.thread.start()

    def tell(self):
        return self.position

    def seekable(self):
        return False

    def write(self, data):
        size = len(data)
        for offset in range(0, size, 65536):
            self._put(bytes(data[offset:offset + 65536]))
        self.position += size
        return size

    def flush(self):
        pass

    def _put(self, value):
        while not self.stop.is_set() and monotonic() < self.deadline:
            try:
                self.queue.put(value, timeout=.1)
                return
            except Full:
                pass
        raise TimeoutError("download canceled or expired")

    def _produce(self):
        try:
            self.data["exported_at_ms"] = int(self.reader.archive.wall_clock() * 1000)
            self.data["scope"] = "snapshot of stored evidence; not a dataset or physical validation"
            sums = {}
            with ZipFile(self, "w", compression=ZIP_STORED) as archive:
                archive.writestr("round.json", _encoded(self.data))
                for frame in self.data["frames"]:
                    # The export lease permits completion after retention, but
                    # always verifies the original bytes before packaging them.
                    path = self.reader.archive._directory(self.round_id) / "frames" / (frame["sample_id"] + ".jpg")
                    if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > 512 * 1024:
                        raise ValueError("invalid export image")
                    image = path.read_bytes()
                    from hashlib import sha256
                    if sha256(image).hexdigest() != frame["jpeg_sha256"]:
                        raise ValueError("export image hash mismatch")
                    name = "frames/" + frame["sample_id"] + ".jpg"
                    sums[name] = frame["jpeg_sha256"]
                    archive.writestr(name, image)
                archive.writestr("sha256.json", _encoded(sums))
                archive.writestr("README.txt", "Private experimental evidence. Open round.json for original predictions and independent ToF events.\nNot human annotations; not training data.\n")
        except Exception as error:
            self.error = type(error).__name__
        finally:
            try:
                self._put(None)
            except TimeoutError:
                pass
            with self.reader.archive._lock:
                self.reader.archive._leases[self.round_id] -= 1
            self.reader._download.release()
            if getattr(self.reader.archive, "_closing", False):
                self.reader.archive.close()

    def chunks(self):
        try:
            while monotonic() < self.deadline:
                try:
                    chunk = self.queue.get(timeout=.2)
                except Empty:
                    continue
                if chunk is None:
                    if self.error:
                        raise OSError("incomplete collection export")
                    break
                yield chunk
        finally:
            self.close()

    def close(self):
        self.stop.set()


def install_history(app, store):
    from fastapi import Request
    from fastapi.responses import JSONResponse, Response, StreamingResponse
    from starlette.background import BackgroundTask
    from .demo_routes import HEADERS

    reader = HistoryReader(store.archive) if store.archive else None

    async def run(function, *args):
        if reader is None:
            return None
        try:
            return await reader.read(function, *args)
        except (KeyError, FileNotFoundError):
            raise ApiError(404, "history_not_found", "history_unavailable") from None
        except ValueError:
            raise ApiError(400, "history_invalid_artifact") from None

    @app.get("/v1/demo/history")
    async def rounds():
        return JSONResponse({"enabled": reader is not None,
                             "rounds": await run(reader.summaries) if reader else []}, headers=HEADERS)

    @app.get("/v1/demo/history/{round_id}")
    async def timeline(round_id: str):
        if reader is None:
            raise ApiError(404, "history_disabled", "history_unavailable")
        return Response(await run(reader.timeline, round_id), media_type="application/json", headers=HEADERS)

    @app.get("/v1/demo/history/{round_id}/frames/{sample_id}")
    async def image(round_id: str, sample_id: str):
        if reader is None:
            raise ApiError(404, "history_disabled", "history_unavailable")
        return Response(await run(reader.archive.frame, round_id, sample_id), media_type="image/jpeg", headers=HEADERS)

    @app.get("/v1/demo/history/{round_id}/download")
    async def download(round_id: str, request: Request):
        if reader is None:
            raise ApiError(404, "history_disabled", "history_unavailable")
        export = await run(reader.download, round_id)
        return StreamingResponse(export.chunks(), media_type="application/zip",
            headers={**HEADERS, "Content-Disposition": f'attachment; filename="sonar-round-{round_id}.zip"'},
            background=BackgroundTask(export.close))
