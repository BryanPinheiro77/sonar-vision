"""Container health probe: `python -m sonar_vision_api.healthcheck --cafile CA.pem`.

Exit 0 only when GET /healthz answers 200 with `status: ok` over HTTPS and the
server certificate validates against the given CA. There is no switch to skip
certificate or hostname verification, and redirects are never followed, so a
3xx answer (including a downgrade to plain HTTP) is reported as unhealthy.
"""

import argparse
import json
import ssl
import sys
from urllib.error import URLError
from urllib.request import HTTPSHandler, OpenerDirector

TIMEOUT_S = 3.0
MAX_BYTES = 4096


def probe(url: str, cafile: str, timeout_s: float = TIMEOUT_S) -> str | None:
    """Return None when healthy, otherwise a short reason."""
    if not url.startswith("https://"):
        return "only https:// URLs are accepted"
    try:
        context = ssl.create_default_context(cafile=cafile)
    except (OSError, ssl.SSLError):
        return "cafile unreadable or invalid"
    # Bare OpenerDirector instead of build_opener: no HTTP, redirect or proxy
    # handlers, so the only request ever sent is the HTTPS one to `url`.
    opener = OpenerDirector()
    opener.add_handler(HTTPSHandler(context=context))
    try:
        with opener.open(url, timeout=timeout_s) as response:
            if response.status != 200:
                return f"status {response.status}"
            body = response.read(MAX_BYTES + 1)
    except (URLError, OSError, ValueError) as error:
        return f"unreachable: {type(error).__name__}"
    if len(body) > MAX_BYTES:
        return "response too large"
    try:
        payload = json.loads(body)
    except ValueError:
        return "invalid JSON"
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return "not ok"
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cafile", required=True, help="PEM CA that signed the server certificate")
    parser.add_argument("--url", default="https://localhost:8443/healthz")
    args = parser.parse_args(argv)
    if not args.url.startswith("https://"):
        parser.error("only https:// URLs are accepted")
    reason = probe(args.url, args.cafile)
    if reason:
        print(f"unhealthy: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
