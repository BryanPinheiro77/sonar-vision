"""Run the API over HTTPS only: `python -m sonar_vision_api --certfile ... --keyfile ...`.

There is deliberately no plain-HTTP mode. Configuration comes from SONAR_API_*
environment variables (see .env.example and docs/api.md).
"""

import argparse
import logging

from sonar_vision import VisionService

from .app import create_app
from .auth import TokenStore
from .config import Settings
from .service import InferenceService, header_only_decoder, log_event, opencv_decoder


def build(settings: Settings):
    if settings.backend == "simulated":
        from sonar_vision.benchmark import SyntheticBackend
        factory, decoder = SyntheticBackend, header_only_decoder
    else:
        from sonar_vision.ultralytics_backend import UltralyticsFactory
        factory, decoder = UltralyticsFactory(settings.weights), opencv_decoder
    vision = VisionService(factory, max_sessions=settings.max_sessions,
                           idle_seconds=settings.idle_seconds)
    service = InferenceService(vision, decoder, timeout_ms=settings.timeout_ms)
    app = create_app(service, TokenStore.from_file(settings.tokens_file),
                     backend=settings.backend, max_body_bytes=settings.max_body_bytes,
                     max_pixels=settings.max_pixels)
    return app, service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--certfile", required=True, help="PEM server certificate chain")
    parser.add_argument("--keyfile", required=True, help="PEM private key (outside Git)")
    args = parser.parse_args()

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    app, service = build(settings)
    if settings.backend == "simulated":
        logging.getLogger("sonar_vision_api").warning(
            "SIMULATED backend: scripted detections, not a model or tracking result")
    log_event("startup", **settings.public())
    try:
        # One process: sessions live in memory and must not be split across workers.
        uvicorn.run(app, host=args.host, port=args.port, ssl_certfile=args.certfile,
                    ssl_keyfile=args.keyfile, workers=1, server_header=False,
                    proxy_headers=False, log_level="info")
    finally:
        service.close()


if __name__ == "__main__":
    main()
