"""Prepare the trusted local #16 checkpoint for public distribution.

Only load a checkpoint produced by this project. PyTorch .pt files use pickle;
never run this on an untrusted download.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch


PUBLIC_ARGS = {
    "model": "stairs-up-down-v2.pt",
    "data": "issue16-full100-direction-v3/dataset.yaml",
    "project": "issue16-full100-direction-v3",
    "save_dir": "issue16-full100-direction-v3/train",
}


def prepare(source: Path, destination: Path) -> None:
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("O destino deve ser novo e diferente do peso original")
    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    if checkpoint.get("version") != "8.4.137":
        raise ValueError("Versão inesperada do checkpoint")
    if checkpoint["model"].names != {0: "stairs_up", 1: "stairs_down"}:
        raise ValueError("Classes inesperadas do checkpoint")

    for args in (checkpoint["train_args"], checkpoint["model"].args):
        args.update(PUBLIC_ARGS)
    checkpoint["git"] = None
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source, args.destination)
