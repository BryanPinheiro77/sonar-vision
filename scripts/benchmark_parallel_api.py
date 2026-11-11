"""#22 experimental parallel CPU models; original API defaults stay unchanged.

Operator entrypoint for a CPU image with trusted general + stair weights.
Two independent predictors run concurrently. Tracking/merge stay on the
request worker, with one global frame active and no frame queue.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, wait
import json
import logging
from threading import Lock

import numpy as np

from sonar_vision.core import Busy
from sonar_vision.ultralytics_backend import (
    UltralyticsFactory as BaseFactory,
    UltralyticsBackend,
    StairAugmentedBackend,
)


class ParallelFactory(BaseFactory):
    instances = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.config.device != "cpu" or self._direction_model is None:
            raise ValueError("experiment requires CPU general and stair models")
        self.frame_lock = Lock()
        self.intraop_threads = 1
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="model-cpu")
        self.metadata = {**self.metadata, "experiment": "parallel_cpu_models"}
        self.instances.append(self)

    def __call__(self):
        return ParallelBackend(self)

    def warmup(self):
        # Initialize predictors serially before concurrent use of global settings.
        backend = BaseFactory.__call__(self)
        try:
            backend.infer(np.zeros((480, 640, 3), dtype=np.uint8))
        finally:
            backend.close()

    def predict_model(self, model, image):
        import torch

        if torch.get_num_threads() != self.intraop_threads:
            raise RuntimeError("experiment prediction thread count differs from requested count")
        c = self.config
        return model.predict(
            image, conf=c.confidence, imgsz=c.image_size, device=c.device,
            max_det=c.max_detections, verbose=False, save=False,
        )[0]

    def shutdown(self):
        self.pool.shutdown(wait=True, cancel_futures=True)


class _PreparedPrimary:
    def __init__(self, backend):
        self.backend = backend

    def infer(self, image):
        return self.backend.primary_detections

    def close(self):
        self.backend.primary.close()


class ParallelBackend:
    def __init__(self, owner):
        self.owner = owner
        self.general_result = self.stair_result = None
        self.primary_detections = None
        self.closed = False
        self.primary = UltralyticsBackend(lambda image: self.general_result, owner.config)
        self.merger = StairAugmentedBackend(
            _PreparedPrimary(self), lambda image: self.stair_result,
        )

    def infer(self, image):
        if self.closed:
            raise RuntimeError("backend closed")
        if (not isinstance(image, np.ndarray) or image.dtype != np.uint8
                or image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1):
            raise ValueError("image must be a nonempty HxWx3 BGR uint8 array")
        if self.primary._shape is not None and image.shape[:2] != self.primary._shape:
            raise ValueError("resolution changed: reset tracker before processing")
        if not self.owner.frame_lock.acquire(blocking=False):
            raise Busy("detector busy")
        jobs = []
        try:
            self.primary._shape = image.shape[:2]
            jobs.append(self.owner.pool.submit(
                self.owner.predict_model, self.owner._model, image,
            ))
            jobs.append(self.owner.pool.submit(
                self.owner.predict_model, self.owner._direction_model, image,
            ))
            self.general_result = jobs[0].result()
            # Preserve primary tracker updates even if the stair pass later fails.
            self.primary_detections = self.primary.infer(image)
            self.stair_result = jobs[1].result()
            return self.merger.infer(image)
        finally:
            # A failed pass never releases ownership while another pass is running.
            wait(jobs)
            self.general_result = self.stair_result = self.primary_detections = None
            self.owner.frame_lock.release()

    def close(self):
        self.closed = True
        self.primary.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    import torch
    import uvicorn
    import sonar_vision.ultralytics_backend as adapters
    from sonar_vision_api.__main__ import build
    from sonar_vision_api.config import Settings
    from sonar_vision_api.service import log_event

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = Settings.from_env()
    if settings.backend != "ultralytics" or settings.stair_direction_weights is None:
        raise SystemExit("parallel experiment requires real general and stair weights")
    # Inject only in this explicit operator process; no production source edit.
    adapters.UltralyticsFactory = ParallelFactory
    app, service = build(settings)
    torch.set_num_threads(args.threads)
    for factory in ParallelFactory.instances:
        factory.intraop_threads = args.threads
    print(json.dumps({"event": "operator_parallel_cpu_experiment",
                      "model_workers": 2, "intraop_threads": torch.get_num_threads()}),
          flush=True)
    log_event("startup", **settings.public())
    try:
        uvicorn.run(
            app, host="0.0.0.0", port=8443,
            ssl_certfile="/run/sonar/tls/server.pem",
            ssl_keyfile="/run/sonar/tls/server-key.pem",
            workers=1, server_header=False, proxy_headers=False, log_level="info",
        )
    finally:
        service.close()
        for factory in ParallelFactory.instances:
            factory.shutdown()


if __name__ == "__main__":
    main()
