"""Network-restricted, read-only browser surface; authenticated separate ToF wire."""

import base64
import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse, HTMLResponse
from starlette.concurrency import run_in_threadpool

from .demo import MAX_TOF_BYTES, parse_tof
from .errors import ApiError
from .validation import _no_constants, _no_duplicates

ASSETS = Path(__file__).with_name("demo_static")
HEADERS = {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache",
           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
           "X-Frame-Options": "DENY",
           "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; "
             "img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}


def install_demo(app, store, tokens, backend):
    public_assets = {"panel.css", "login.css", "login.js", "logo.jpeg", "favicon.png"}

    @app.middleware("http")
    async def demo_access(request, call_next):
        path = request.url.path
        is_demo = path == "/demo" or path.startswith("/demo/") or path.startswith("/v1/demo/")
        if not is_demo:
            return await call_next(request)
        public = path == "/demo/login" or path in {"/demo/assets/" + n for n in public_assets}
        if public and store.viewer_auth is not None:
            response = await call_next(request)
            response.headers.update(HEADERS)
            return response
        if request.method in ("GET", "HEAD"):
            if store.viewer_auth is not None:
                authorized = store.viewer_auth.valid_session(request.cookies.get("sonar_viewer"))
                if not authorized:
                    if path in {"/demo", "/demo/history"}:
                        return RedirectResponse("/demo/login", status_code=303, headers=HEADERS)
                    return JSONResponse({"error": {"code": "unauthorized"}}, status_code=401,
                                        headers=HEADERS)
            elif not request.client or not store.allowed(request.client.host):
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

    @app.get("/demo/login")
    async def login_page():
        if store.viewer_auth is None:
            return RedirectResponse("/demo", status_code=303, headers=HEADERS)
        return FileResponse(ASSETS / "login.html", headers=HEADERS)

    @app.post("/demo/login")
    async def login(request: Request):
        from .app import read_limited
        if store.viewer_auth is None:
            return Response(status_code=404, headers=HEADERS)
        if request.headers.get("origin") != str(request.base_url).rstrip("/"):
            return Response(status_code=403, headers=HEADERS)
        try:
            store.rate_limit("viewer_login", 2)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return Response(status_code=415, headers=HEADERS)
            data = json.loads(await read_limited(request, 2048),
                              object_pairs_hook=_no_duplicates, parse_constant=_no_constants)
            if (not isinstance(data, dict) or set(data) != {"username", "password"}
                    or not all(isinstance(data[k], str) for k in data)
                    or not 1 <= len(data["username"]) <= 64
                    or not 1 <= len(data["password"]) <= 256):
                return Response(status_code=400, headers=HEADERS)
            header = "Basic " + base64.b64encode((data["username"] + ":" + data["password"]).encode()).decode()
            accepted = await run_in_threadpool(store.viewer_auth.authenticate, header)
        except (ValueError, UnicodeError):
            return Response(status_code=400, headers=HEADERS)
        except ApiError as exc:
            return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status,
                                headers={**HEADERS, **({"Retry-After": "2"} if exc.status == 429 else {})})
        if not accepted:
            return JSONResponse({"error": {"code": "unauthorized"}}, status_code=401, headers=HEADERS)
        response = JSONResponse({"next": "/demo"}, headers=HEADERS)
        response.set_cookie("sonar_viewer", store.viewer_auth.issue_session(), max_age=28800,
                            secure=True, httponly=True, samesite="strict", path="/")
        return response

    @app.post("/demo/logout")
    async def logout(request: Request):
        if request.headers.get("origin") != str(request.base_url).rstrip("/"):
            return Response(status_code=403, headers=HEADERS)
        response = Response(status_code=204, headers=HEADERS)
        response.delete_cookie("sonar_viewer", path="/", secure=True, httponly=True, samesite="strict")
        return response

    async def browser_page(name):
        if store.viewer_auth is not None:
            return FileResponse(ASSETS / name, headers=HEADERS)
        markup = await run_in_threadpool((ASSETS / name).read_text, encoding="utf-8")
        return HTMLResponse(markup.replace('id="logout"', 'id="logout" hidden'), headers=HEADERS)

    @app.get("/demo")
    async def page():
        return await browser_page("index.html")

    @app.get("/demo/history")
    async def history_page():
        return await browser_page("history.html")

    @app.get("/demo/assets/{name}")
    async def asset(name: str):
        if name not in {"panel.css", "panel.js", "logo.jpeg", "demo-scene.webp", "history.js", "player-core.js", "logout.js", *public_assets}:
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
