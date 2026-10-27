"""Network-restricted, read-only browser surface; authenticated separate ToF wire."""

from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response

from .demo import MAX_TOF_BYTES, parse_tof
from .errors import ApiError

ASSETS = Path(__file__).with_name("demo_static")
HEADERS = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache",
           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
           "X-Frame-Options": "DENY",
           "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; "
             "img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}


def install_demo(app, store, tokens, backend):
    @app.middleware("http")
    async def demo_access(request, call_next):
        path = request.url.path
        is_demo = path == "/demo" or path.startswith("/demo/") or path.startswith("/v1/demo/")
        if not is_demo:
            return await call_next(request)
        if request.method in ("GET", "HEAD"):
            if not request.client or not store.allowed(request.client.host):
                return JSONResponse({"error": {"code": "forbidden"}}, status_code=403, headers=HEADERS)
            try:
                if path.startswith("/v1/demo/history"):
                    route = "history_image" if "/frames/" in path else "history_download" if path.endswith("/download") else "history_metadata"
                    limit = {"history_image": 12, "history_download": 1, "history_metadata": 2}[route]
                else:
                    route = "snapshot" if path == "/v1/demo/snapshot" else "image" if path == "/v1/demo/image" else "assets"
                    limit = 3 if route != "assets" else 24
                store.rate_limit(route, limit)
            except ApiError:
                return JSONResponse({"error": {"code": "busy"}}, status_code=429,
                                    headers={**HEADERS, "Retry-After": "2"})
        response = await call_next(request)
        response.headers.update(HEADERS)
        return response

    @app.get("/demo")
    async def page():
        return FileResponse(ASSETS / "index.html", headers=HEADERS)

    @app.get("/demo/assets/{name}")
    async def asset(name: str):
        if name not in {"panel.css", "panel.js", "logo.jpeg"}:
            return Response(status_code=404, headers=HEADERS)
        return FileResponse(ASSETS / name, headers=HEADERS)

    @app.get("/v1/demo/snapshot")
    async def snapshot():
        return JSONResponse(store.snapshot(backend), headers=HEADERS)

    @app.get("/v1/demo/image")
    async def image(frame_id: str, sha256: str):
        return Response(store.image(frame_id, sha256), media_type="image/jpeg", headers=HEADERS)

    @app.post("/v1/demo/tof")
    async def tof(request: Request):
        from .app import read_limited
        device = tokens.authenticate(request.headers.get("authorization"))
        if device != store.settings.device_id:
            raise ApiError(403, "demo_source")
        store.rate_limit("tof", 10)
        if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
            raise ApiError(415, "tof_media_type")
        data = parse_tof(await read_limited(request, MAX_TOF_BYTES))
        store.ingest_tof(device, data)
        return Response(status_code=204, headers=HEADERS)

    @app.delete("/v1/demo/session")
    async def end(request: Request):
        device = tokens.authenticate(request.headers.get("authorization"))
        if device != store.settings.device_id:
            raise ApiError(403, "demo_source")
        store.end()
        return Response(status_code=204, headers=HEADERS)

    from .history import install_history
    install_history(app, store)
