"""Real HTTPS server in-process: uvicorn + TLS + API + VisionService (#27).

The default backend is deterministic and controllable (delay, block, failure),
so failure modes are reproducible. The real detector is opt-in (`weights`).
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import socket
from threading import Event, Thread
import time

from sonar_vision.core import Detection, VisionService
from sonar_vision_api.app import create_app
from sonar_vision_api.auth import TokenStore, new_token, token_hash
from sonar_vision_api.dev_tls import create
from sonar_vision_api.policy import NullPolicy
from sonar_vision_api.service import InferenceService, header_only_decoder, opencv_decoder


@dataclass
class Control:
    """Shared knobs for the simulated backend; tests flip them between requests."""
    delay_s: float = 0.0
    gate: Event | None = None  # when set, inference waits until gate.set()
    fail: bool = False
    calls: int = 0


class ControlledBackend:
    """Scripted detections (NOT a model): one confirmed person per frame."""

    def __init__(self, control: Control):
        self.control = control

    def infer(self, image):
        self.control.calls += 1
        if self.control.gate is not None:
            self.control.gate.wait(10)
        if self.control.delay_s:
            time.sleep(self.control.delay_s)
        if self.control.fail:
            raise RuntimeError("controlled backend failure")
        return [Detection("person", 0.9, (0.1, 0.2, 0.3, 0.8), "1")]

    def close(self):
        pass


class EventLog(logging.Handler):
    """Collects the API's JSON log events (they never contain tokens or images)."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.events: list[dict] = []

    def emit(self, record):
        message = record.getMessage()
        if message.startswith("{"):
            self.events.append(json.loads(message))

    def of(self, event: str) -> list[dict]:
        return [e for e in self.events if e.get("event") == event]


@dataclass
class Harness:
    directory: Path
    devices: tuple[str, ...] = ("glasses-01", "glasses-02")
    weights: Path | None = None  # opt-in real detector; requires the vision extra
    idle_seconds: float = 60.0
    timeout_ms: int = 1500
    max_body_bytes: int = 64 * 1024
    max_pixels: int = 1600 * 1200
    policy_factory: object = NullPolicy
    cert_names: tuple[str, ...] = ("localhost", "127.0.0.1")
    control: Control = field(default_factory=Control)
    tokens: dict[str, str] = field(default_factory=dict)
    stair_direction_weights: Path | None = None
    cpu_threads: int | None = None  # exploratory harness only; no production API setting

    def __enter__(self) -> "Harness":
        if self.cpu_threads is not None and (
                type(self.cpu_threads) is not int or self.cpu_threads <= 0 or self.weights is None):
            raise ValueError("cpu threads must be a positive integer with real weights")
        if self.stair_direction_weights is not None and self.weights is None:
            raise ValueError("stair direction weights require a primary detector")
        self.tls = create(Path(self.directory) / "tls", self.cert_names)
        self.tokens = {device: new_token() for device in self.devices}
        store = TokenStore({device: token_hash(token) for device, token in self.tokens.items()})
        if self.weights is None:
            self.model_metadata = None
            factory, decoder, self.backend = (lambda: ControlledBackend(self.control),
                                              header_only_decoder, "simulated")
        else:
            from sonar_vision.ultralytics_backend import UltralyticsFactory
            factory, decoder, self.backend = (UltralyticsFactory(
                self.weights, stair_direction_weights=self.stair_direction_weights),
                opencv_decoder, "ultralytics")
            self.model_metadata = dict(factory.metadata)
        self.service = InferenceService(VisionService(factory, idle_seconds=self.idle_seconds),
                                        decoder, timeout_ms=self.timeout_ms,
                                        policy_factory=self.policy_factory)
        self.worker_settings = None
        if self.weights is not None:
            def prepare():
                import torch
                # Ultralytics selects CPU and resets torch threads on its first
                # prediction. Initialize it before applying the experimental
                # override, in the same executor that will process requests.
                factory.warmup()
                selected = torch.get_num_threads()
                if self.cpu_threads is not None:
                    torch.set_num_threads(self.cpu_threads)
                factory.warmup()
                return {"intraop": torch.get_num_threads(),
                        "interop": torch.get_num_interop_threads(),
                        "ultralytics_selected_intraop": selected,
                        "requested_intraop": self.cpu_threads,
                        "warmup_frames": 2,
                        "scope": "inference executor after disposable warmup"}

            try:
                # Harness owns startup: no HTTP request can race this setup.
                self.worker_settings = self.service._executor.submit(prepare).result()
            except BaseException:
                self.service.close()
                raise
        app = create_app(self.service, store, backend=self.backend,
                         max_body_bytes=self.max_body_bytes, max_pixels=self.max_pixels)
        self.log = EventLog()
        logger = logging.getLogger("sonar_vision_api")
        logger.addHandler(self.log)
        self._previous_level = logger.level
        logger.setLevel(logging.INFO)
        logger.propagate = False

        import uvicorn

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning",
                                ssl_certfile=str(self.tls["cert"]), ssl_keyfile=str(self.tls["key"]))
        self._server = uvicorn.Server(config)
        self._thread = Thread(target=self._server.run, daemon=True)
        self._thread.start()
        deadline = time.monotonic() + 10
        while not self._server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        if not self._server.started:
            raise RuntimeError("integration server did not start")
        return self

    @property
    def url(self) -> str:
        return f"https://127.0.0.1:{self.port}"

    def stop(self) -> None:
        """Stop serving (used to simulate the VM disappearing mid-session)."""
        if self.control.gate is not None:
            self.control.gate.set()
        self._server.should_exit = True
        self._thread.join(10)

    def __exit__(self, *exc):
        self.stop()
        self.service.close()
        logger = logging.getLogger("sonar_vision_api")
        logger.removeHandler(self.log)
        logger.setLevel(self._previous_level)
        logger.propagate = True
