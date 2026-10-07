"""Run the API over HTTPS only: `python -m sonar_vision_api --certfile ... --keyfile ...`.

There is deliberately no plain-HTTP mode. Configuration comes from SONAR_API_*
environment variables (see .env.example and docs/api.md).
"""

import argparse
import logging
from uuid import uuid4

from sonar_vision import VisionService

from .app import create_app
from .auth import TokenStore
from .catalog import PackageRejected, load_package
from .config import Settings
from .policy import NullPolicy, audio_policy_factory
from .runtime_options import checked_weights, load_audio_config, file_hash
from .service import InferenceService, header_only_decoder, log_event, opencv_decoder


def build(settings: Settings):
    tokens = TokenStore.from_file(settings.tokens_file)
    policy = (audio_policy_factory(load_audio_config(settings.audio_config))
              if settings.audio_config is not None else NullPolicy)
    models = {"backend": settings.backend}
    if settings.backend == "simulated":
        from sonar_vision.benchmark import SyntheticBackend
        factory, decoder = SyntheticBackend, header_only_decoder
    else:
        from sonar_vision.ultralytics_backend import UltralyticsFactory
        models["weights_sha256"] = checked_weights(settings.weights, settings.weights_sha256)
        if settings.stair_direction_weights is not None:
            models["stair_weights_sha256"] = checked_weights(
                settings.stair_direction_weights, settings.stair_weights_sha256)
        factory, decoder = UltralyticsFactory(settings.weights,
            stair_direction_weights=settings.stair_direction_weights), opencv_decoder
        factory.warmup()
    vision = VisionService(factory, max_sessions=settings.max_sessions,
                           idle_seconds=settings.idle_seconds)
    catalog = None
    if settings.catalog_dir is not None:
        try:
            catalog = load_package(settings.catalog_dir)
        except PackageRejected as error:
            # Fail fast: publishing a broken package is an operator error.
            raise SystemExit(f"voice catalog rejected: {error.reason}") from None
    diagnostics = None
    if settings.diagnostics_dir is not None:
        from .diagnostics import PredictionJournal
        diagnostics = PredictionJournal(settings.diagnostics_dir / ("predictions-" + uuid4().hex + ".jsonl"), {
            **models, "public_settings": settings.public(),
            "audio_config_sha256": file_hash(settings.audio_config) if settings.audio_config else None,
            "vision": factory.metadata if settings.backend == "ultralytics" else None})
    service = InferenceService(vision, decoder, timeout_ms=settings.timeout_ms,
                               policy_factory=policy, diagnostics=diagnostics)
    service.model_metadata = models
    log_event("model_configuration", **models)
    app = create_app(service, tokens,
                     backend=settings.backend, max_body_bytes=settings.max_body_bytes,
                     max_pixels=settings.max_pixels, catalog=catalog)
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
