"""Temporary #22 CPU comparison using the main API builder and TLS contract.

Mount this operator script at /run/sonar/threads_experiment.py in the existing
CPU image. It sets two intraop threads after the builder's model warmup.
The measured CPU2 control did not improve FPS; this is not a production default.
CPU4 comparisons can request auto or a fixed thread count explicitly.
"""

import argparse
import json
import logging
from threading import Lock, current_thread, main_thread

import torch
import uvicorn

from sonar_vision_api.__main__ import build
from sonar_vision_api.config import Settings
from sonar_vision_api.service import log_event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threads", choices=("auto", "1", "2", "3", "4"), default="2")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Report the actual prediction thread as well as the builder thread.
    # Observation is confined to this explicit operator process.
    from sonar_vision.ultralytics_backend import UltralyticsFactory

    seen, guard = set(), Lock()

    def observe(original, label):
        def predict(self, image):
            count = torch.get_num_threads()
            thread = current_thread()
            key = (label, thread.name, count)
            with guard:
                first = key not in seen
                seen.add(key)
            if first:
                print(json.dumps({"event": "operator_prediction_threads",
                                  "model": label, "intraop_threads": count,
                                  "thread_role": "main" if thread is main_thread() else "worker"}),
                      flush=True)
            return original(self, image)
        return predict

    UltralyticsFactory._predict = observe(UltralyticsFactory._predict, "general")
    UltralyticsFactory._predict_stairs = observe(UltralyticsFactory._predict_stairs, "stairs")
    settings = Settings.from_env()
    app, service = build(settings)
    before = torch.get_num_threads()
    if args.threads != "auto":
        torch.set_num_threads(int(args.threads))
    print(json.dumps({
        "event": "operator_threads_experiment",
        "requested_threads": args.threads,
        "before_threads": before,
        "after_threads": torch.get_num_threads(),
        "inter_op_threads": torch.get_num_interop_threads(),
        "scope": "temporary comparison; not permanent runtime option",
    }), flush=True)
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


if __name__ == "__main__":
    main()
