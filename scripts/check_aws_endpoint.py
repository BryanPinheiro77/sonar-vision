"""#23 external HTTPS/API smoke with a single simulated glasses credential.

No resource provisioning, retries, raw image storage or playback. Reports contain
aggregates only. Default JPEG is generated original black640x480 (vision extra).
"""

import argparse
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from sonar_vision_integration.client import DeviceClient, Discarded
from sonar_vision_integration.remote_load import validate


def run_probe(endpoint, token, ca_file, *, device="glasses-01", jpeg=None):
    validate(endpoint, [(device, token)], 10, 1, 0, "aligned")
    if jpeg is None:
        from sonar_vision_integration.bench import synthetic_jpeg

        jpeg = synthetic_jpeg(True)
    from sonar_vision_api.healthcheck import probe

    checks = []

    def check(name, ok):
        checks.append({"check": name, "passed": bool(ok)})
        if not ok:
            raise ValueError("endpoint check failed: " + name)

    check(
        "HTTPS health and peer certificate valid",
        probe(endpoint.rstrip("/") + "/healthz", str(ca_file)) is None,
    )
    client = DeviceClient(endpoint, token, ca_file)
    try:
        begin = perf_counter()
        result = client.send(client.capture(jpeg))
        latency = (perf_counter() - begin) * 1000
        check("authorized JPEG response admitted", True)
        classes = dict(
            Counter(item["class_name"] for item in result["observation"]["objects"])
        )
        audio_present = result["audio"] is not None
    finally:
        client.close()
    for label, credential in [
        ("missing credential rejected", ""),
        ("wrong credential rejected", token + "x"),
    ]:
        wrong = DeviceClient(endpoint, credential, ca_file)
        rejected = False
        try:
            wrong.send(wrong.capture(jpeg))
        except Discarded as error:
            rejected = error.status == 401
        finally:
            wrong.close()
        check(label, rejected)
    from sonar_vision_api.dev_tls import create

    with TemporaryDirectory() as temp:
        other = create(Path(temp) / "wrong-trust-root")
        wrong = DeviceClient(endpoint, token, other["ca"])
        rejected = False
        try:
            wrong.send(wrong.capture(jpeg))
        except Discarded as error:
            rejected = error.reason == "tls"
        finally:
            wrong.close()
        check("untrusted CA rejected without bypass", rejected)
    return {
        "kind": "external_https_operational_probe",
        "checks": checks,
        "classes_observed": classes,
        "audio_suggestion_present": audio_present,
        "jpeg_ready_to_admission_ms": latency,
        "physical_capture_or_tactile_validated": False,
        "accuracy_evaluated": False,
        "raw_response_identifiers_not_exported": True,
        "cloud_resources_created_by_probe": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_probe(
            args.endpoint,
            args.token_file.read_text().strip(),
            args.ca_file,
            jpeg=args.image.read_bytes() if args.image else None,
        )
        with args.output.open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (ValueError, OSError, Discarded):
        parser.exit(
            2,
            "Endpoint validation failed; inspect private inputs/server state without relaxing TLS.\n",
        )
    print("Endpoint checks passed; no raw responses or credentials exported.")


if __name__ == "__main__":
    main()
