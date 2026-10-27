"""#73 explicit simulated source: synthetic JPEGs and ToF over verified HTTPS."""

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
import ssl
from time import monotonic, sleep
from urllib.parse import urlsplit


def synthetic_jpeg(index):
    import cv2
    import numpy as np
    image = np.full((480, 640, 3), (240, 245, 245), dtype=np.uint8)
    x = 60 if index % 2 == 0 else 360
    color = (120, 100, 20) if index % 2 == 0 else (100, 160, 20)
    cv2.rectangle(image, (x, 140), (x + 180, 350), color, -1)
    cv2.putText(image, "FONTE SIMULADA " + str(index), (32, 60),
                cv2.FONT_HERSHEY_SIMPLEX, .9, (75, 55, 10), 2)
    cv2.putText(image, "Sem camera / sem sensor fisico", (32, 440),
                cv2.FONT_HERSHEY_SIMPLEX, .7, (75, 55, 10), 2)
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise ValueError("synthetic JPEG encoding failed")
    return encoded.tobytes()


def main():
    import httpx2
    from sonar_vision_api.demo import parse_tof
    from sonar_vision_integration.client import DeviceClient, Discarded

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--ca-file", type=Path)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--frames", type=int, default=20)
    parser.add_argument("--interval", type=float, default=2)
    parser.add_argument("--images-only", action="store_true")
    parser.add_argument("--tof-only", action="store_true")
    parser.add_argument("--exercise-errors", action="store_true",
                        help="send invalid measurements and duplicate sequences explicitly")
    parser.add_argument("--end-session", action="store_true", help="discard both channels after sending")
    args = parser.parse_args()
    url = urlsplit(args.endpoint)
    if (url.scheme != "https" or not url.netloc or url.username or url.password or
            url.path not in ("", "/") or url.query or url.fragment):
        parser.error("endpoint must be an HTTPS origin without credentials/path/query")
    if args.frames < 1 or not math.isfinite(args.interval) or args.interval < .5 or args.interval > 60 or (args.images_only and args.tof_only):
        parser.error("frames >=1; interval .5..60 seconds; select at most one channel")
    token = args.token_file.read_text().strip()
    context = ssl.create_default_context(cafile=args.ca_file)
    device = DeviceClient(args.endpoint, token, args.ca_file)
    device.session_id = args.session
    try:
        with httpx2.Client(verify=context, follow_redirects=False, timeout=2,
                           headers={"Authorization": "Bearer " + token}) as client:
            snapshot = client.get(args.endpoint.rstrip("/") + "/v1/demo/snapshot")
            snapshot.raise_for_status()
            source = snapshot.json()["source"]
            if source["kind"] != "simulated" or source["session_id"] != args.session:
                raise ValueError("simulator requires matching session and SIMULATED source on server")
            device._next_frame = int(monotonic() * 1000)
            for index in range(args.frames):
                if not args.tof_only:
                    image = synthetic_jpeg(index)
                    capture = device.capture(image)
                    try:
                        device.send(capture)
                        status = "admitted"
                    except Discarded as error:
                        status = error.reason
                    print(json.dumps({"kind": "SIMULATED_IMAGE", "frame": capture.frame_id,
                                      "sha256": sha256(image).hexdigest(), "result": status}))
                if not args.images_only:
                    invalid = args.exercise_errors and index % 3 == 1
                    reading = {"version": "demo-tof-1", "session_id": args.session,
                               "sequence": str(int(monotonic() * 1000)),
                               "captured_at_ms": int(monotonic() * 1000),
                               "distance_mm": None if invalid else 1250 + index * 10,
                               "valid": not invalid, "quality": "invalid" if invalid else "good",
                               "sector": "all", "zone": None, "aggregation": "min_valid_8x8"}
                    parse_tof(json.dumps(reading))
                    response = client.post(args.endpoint.rstrip("/") + "/v1/demo/tof", json=reading)
                    print(json.dumps({"kind": "SIMULATED_TOF", "sequence": reading["sequence"],
                                      "valid": reading["valid"], "http": response.status_code}))
                    response.raise_for_status()
                    if args.exercise_errors:
                        duplicate = client.post(args.endpoint.rstrip("/") + "/v1/demo/tof", json=reading)
                        if duplicate.status_code != 409:
                            raise RuntimeError("expected replay rejection")
                if index + 1 < args.frames:
                    sleep(args.interval)
            if args.end_session:
                client.delete(args.endpoint.rstrip("/") + "/v1/demo/session").raise_for_status()
    finally:
        device.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
