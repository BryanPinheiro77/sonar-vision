"""FastAPI routes: thin adapter from HTTP to InferenceService."""

from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from .auth import TokenStore
from .errors import ApiError
from .multipart import parse_form
from .service import InferenceService, log, log_event
from .validation import jpeg_dimensions, parse_metadata


def _error(status: int, code: str, headers=None) -> JSONResponse:
    return JSONResponse({"error": {"code": code}}, status_code=status, headers=headers)


async def read_limited(request: Request, limit: int) -> bytes:
    """Stop reading as soon as the body exceeds the limit; never trust Content-Length alone."""
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise ApiError(400, "content_length")
        if int(declared) > limit:
            raise ApiError(413, "body_declared_too_large")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise ApiError(413, "body_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(service: InferenceService, tokens: TokenStore, *, backend: str,
               max_body_bytes: int, max_pixels: int, clock=None) -> FastAPI:
    clock = clock or service.clock
    # No interactive docs or schema endpoint on the device-facing service.
    app = FastAPI(title="Sonar Vision inference", docs_url=None, redoc_url=None,
                  openapi_url=None)

    @app.exception_handler(ApiError)
    async def api_error(request: Request, error: ApiError):
        headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else None
        return _error(error.status, error.code, headers)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "invalid_request")
        return _error(error.status_code, code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return _error(400, "invalid_request")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception):
        log.exception("unexpected API error")
        return _error(500, "internal_error")

    @app.get("/healthz")
    async def health():
        # Makes the simulated backend explicit to anyone operating the service.
        return {"status": "ok", "backend": backend, "contract": "0.1"}

    @app.post("/v1/inference")
    async def inference(request: Request):
        received_at, started = clock(), perf_counter()
        timings = {"request_id": uuid4().hex, "backend": backend}
        status, reason = 200, "ok"
        try:
            # Authenticate before reading the upload.
            timings["device_id"] = device_id = tokens.authenticate(
                request.headers.get("authorization"))
            content_type = request.headers.get("content-type", "")
            if not content_type.lower().startswith("multipart/form-data"):
                raise ApiError(415, "request_not_multipart")
            body = await read_limited(request, max_body_bytes)
            timings["body_bytes"] = len(body)
            timings["read_ms"] = round((perf_counter() - started) * 1000, 3)
            raw_metadata, image = parse_form(body, content_type)
            meta = parse_metadata(raw_metadata)
            timings.update(session_id=meta.session_id, frame_id=meta.frame_id)
            shape = jpeg_dimensions(image, max_pixels)
            timings["image_height_width"] = list(shape)
            result = await service.infer(device_id, meta, image, shape, received_at, timings)
            return Response(result, media_type="application/json")
        except ApiError as error:
            status, reason = error.status, error.reason
            raise
        except BaseException as error:
            # Includes cancellation when the client disconnects or the server stops.
            status, reason = None, type(error).__name__
            raise
        finally:
            timings["total_ms"] = round((perf_counter() - started) * 1000, 3)
            log_event("inference_request", status=status, reason=reason, **timings)

    return app
