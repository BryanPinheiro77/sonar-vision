"""Local test CA and server certificate: `python -m sonar_vision_api.dev_tls DIR`.

For development only (requires the `api-dev` extra). Clients must trust
DIR/ca.pem explicitly; never disable certificate verification instead.
"""

import argparse
from pathlib import Path


def create(directory: Path, names=("localhost", "127.0.0.1", "::1")) -> dict[str, Path]:
    import trustme

    directory.mkdir(parents=True, exist_ok=True)
    ca = trustme.CA(organization_name="Sonar Vision local development CA")
    cert = ca.issue_cert(*names)
    paths = {"ca": directory / "ca.pem", "cert": directory / "server.pem",
             "key": directory / "server-key.pem"}
    ca.cert_pem.write_to_path(str(paths["ca"]))
    cert.private_key_pem.write_to_path(str(paths["key"]))
    paths["cert"].write_bytes(b"".join(blob.bytes() for blob in cert.cert_chain_pems))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    for name, path in create(args.directory).items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
