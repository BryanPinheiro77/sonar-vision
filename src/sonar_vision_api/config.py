"""Startup configuration from environment variables; invalid values stop the process."""

from dataclasses import dataclass
import math
import os
from pathlib import Path

BACKENDS = ("simulated", "ultralytics")
CLIENT_TIMEOUT_MS = 2000  # contract 0.1: client timeout includes connect/send/read


def _int(env, name, default):
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer") from None
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class Settings:
    backend: str
    tokens_file: Path
    weights: Path | None = None
    max_body_bytes: int = 512 * 1024
    max_pixels: int = 1600 * 1200  # OV2640 UXGA; larger captures are rejected
    timeout_ms: int = 1500
    max_sessions: int = 8
    idle_seconds: float = 60.0
    catalog_dir: Path | None = None  # published voice package (#26); optional

    def __post_init__(self):
        if self.backend not in BACKENDS:
            raise ValueError("SONAR_API_BACKEND must be simulated or ultralytics")
        if not Path(self.tokens_file).is_file():
            raise ValueError("SONAR_API_TOKENS_FILE must point to an existing file")
        if self.backend == "ultralytics" and (self.weights is None or not Path(self.weights).is_file()):
            raise ValueError("SONAR_API_WEIGHTS must point to trusted local weights")
        for value in (self.max_body_bytes, self.max_pixels, self.timeout_ms, self.max_sessions):
            if type(value) is not int or value <= 0:
                raise ValueError("limits must be positive integers")
        # The server budget must end before the client gives up on the same request.
        if self.timeout_ms >= CLIENT_TIMEOUT_MS:
            raise ValueError("SONAR_API_TIMEOUT_MS must be below the 2000 ms client timeout")
        if not math.isfinite(self.idle_seconds) or self.idle_seconds <= 0:
            raise ValueError("SONAR_API_IDLE_SECONDS must be positive")
        if self.catalog_dir is not None and not Path(self.catalog_dir).is_dir():
            raise ValueError("SONAR_API_CATALOG_DIR must point to a package directory")

    @classmethod
    def from_env(cls, env=os.environ) -> "Settings":
        backend, tokens = env.get("SONAR_API_BACKEND"), env.get("SONAR_API_TOKENS_FILE")
        if not backend or not tokens:
            raise ValueError("SONAR_API_BACKEND and SONAR_API_TOKENS_FILE are required")
        weights = env.get("SONAR_API_WEIGHTS")
        try:
            idle = float(env.get("SONAR_API_IDLE_SECONDS", "60"))
        except ValueError:
            raise ValueError("SONAR_API_IDLE_SECONDS must be a number") from None
        return cls(backend=backend, tokens_file=Path(tokens),
                   weights=Path(weights) if weights else None,
                   catalog_dir=Path(env["SONAR_API_CATALOG_DIR"]) if env.get("SONAR_API_CATALOG_DIR") else None,
                   max_body_bytes=_int(env, "SONAR_API_MAX_BODY_BYTES", cls.max_body_bytes),
                   max_pixels=_int(env, "SONAR_API_MAX_PIXELS", cls.max_pixels),
                   timeout_ms=_int(env, "SONAR_API_TIMEOUT_MS", cls.timeout_ms),
                   max_sessions=_int(env, "SONAR_API_MAX_SESSIONS", cls.max_sessions),
                   idle_seconds=idle)

    def public(self) -> dict:
        """Values safe to log at startup: no paths to secrets."""
        return {"backend": self.backend, "max_body_bytes": self.max_body_bytes,
                "max_pixels": self.max_pixels, "timeout_ms": self.timeout_ms,
                "max_sessions": self.max_sessions, "idle_seconds": self.idle_seconds,
                "catalog_configured": self.catalog_dir is not None}
