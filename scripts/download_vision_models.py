"""Baixa os pesos gerais e de escadas e verifica seus SHA-256.

O arquivo .pt deve ser carregado apenas depois de conferir sua origem.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen


WEIGHTS = {
    "yolov8n.pt": (
        "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolov8n.pt",
        "f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36",
    ),
    "stairs-up-down-v3.pt": (
        "https://github.com/BryanPinheiro77/sonar-vision/releases/download/"
        "model-stairs-v3-preview/stairs-up-down-v3.pt",
        "8949d163cab5bfe429a5b4c5d68f683d24a8291a468591f6f719488144d8fec4",
    ),
}
MAX_BYTES = 64 * 1024 * 1024


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def download(url: str, sha256: str, output: Path) -> None:
    if output.exists():
        if digest(output) != sha256:
            raise ValueError(f"Arquivo existente tem SHA-256 incorreto: {output}")
        print(f"Peso já verificado: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as file:
            temporary = Path(file.name)
            with urlopen(url, timeout=30) as response:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ValueError("Download excedeu o limite esperado")
                    file.write(chunk)
        if digest(temporary) != sha256:
            raise ValueError("SHA-256 do peso baixado não confere")
        os.replace(temporary, output)
        print(f"Peso baixado e verificado: {output}")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("models"))
    args = parser.parse_args()
    for name, (url, sha256) in WEIGHTS.items():
        download(url, sha256, args.directory / name)
