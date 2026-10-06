"""Provision a device credential: `python -m sonar_vision_api.tokens DEVICE_ID FILE`.

Appends `DEVICE_ID <sha256>` to FILE (kept outside Git) and prints the token
once on stdout so it can be written to the device. The server never stores it.
"""

import argparse
from pathlib import Path

from sonar_vision.core import identifier

from .auth import new_token, token_hash


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device_id")
    parser.add_argument("tokens_file", type=Path)
    args = parser.parse_args()
    identifier(args.device_id)
    if not args.device_id.isprintable() or " " in args.device_id:
        parser.error("device_id must be printable and contain no spaces")
    if args.tokens_file.is_file():
        for line in args.tokens_file.read_text(encoding="utf-8").splitlines():
            if line.split()[:1] == [args.device_id]:
                parser.error("device already provisioned; remove its line to rotate")
    token = new_token()
    args.tokens_file.parent.mkdir(parents=True, exist_ok=True)
    with args.tokens_file.open("a", encoding="utf-8") as stream:
        stream.write(f"{args.device_id} {token_hash(token)}\n")
    print(token)


if __name__ == "__main__":
    main()
