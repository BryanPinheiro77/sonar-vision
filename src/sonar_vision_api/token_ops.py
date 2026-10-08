"""Offline credential maintenance for #23; no HTTP or authentication changes.

Writes a new private snapshot atomically. Recreate the API container to load it;
a process already running retains its previous TokenStore. Plaintext credentials
are output once to a new mode-600 file, never accepted as command arguments.
"""

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import tempfile

from sonar_vision.core import identifier
from .auth import TokenStore, new_token, token_hash


def _regular(path: Path):
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISREG(mode):
        raise ValueError("credential paths must be regular files, not symlinks")


@contextmanager
def _lock(path: Path):
    lock = path.with_name(path.name + ".lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink()


def _read(path: Path):
    _regular(path)
    if not path.exists():
        return {}
    entries = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 2 or fields[0] in entries:
            raise ValueError("invalid or duplicate credential entry")
        entries[fields[0]] = fields[1]
    TokenStore(entries)  # validate identifiers, hashes and uniqueness before writing
    return entries


def maintain(path: Path, device: str, action: str, token_file: Path | None = None):
    """Provision/rotate/revoke one device; failure preserves the previous snapshot."""
    path = Path(path)
    identifier(device)
    if not device.isprintable() or any(c.isspace() for c in device):
        raise ValueError("device must be printable without whitespace")
    if action not in ("provision", "rotate", "revoke"):
        raise ValueError("unknown credential action")
    if (action == "revoke") != (token_file is None):
        raise ValueError("provision/rotate require a new token file; revoke does not")
    if not path.parent.is_dir():
        raise ValueError("create a private credential directory first")
    output = Path(token_file) if token_file is not None else None
    if output is not None and output.resolve() == path.resolve():
        raise ValueError("plaintext output must differ from the hash snapshot")
    with _lock(path):
        entries = _read(path)
        if action == "provision" and device in entries:
            raise ValueError("device already provisioned")
        if action != "provision" and device not in entries:
            raise ValueError("device not provisioned")
        token = None
        if action == "revoke":
            del entries[device]
        else:
            token = new_token()
            entries[device] = token_hash(token)
        TokenStore(entries)
        temporary = None
        output_created = False
        try:
            if output is not None:
                fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                output_created = True
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(token + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            fd, name = tempfile.mkstemp(prefix=".credentials-", dir=path.parent)
            temporary = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                for key, digest in sorted(entries.items()):
                    stream.write(f"{key} {digest}\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
        except BaseException:
            if output_created:
                output.unlink()
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return {"action": action, "devices_remaining": len(entries), "reload_required": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("provision", "rotate", "revoke"))
    parser.add_argument("device_id")
    parser.add_argument("tokens_file", type=Path)
    parser.add_argument("--token-file", type=Path, help="new private plaintext file; never overwritten")
    args = parser.parse_args(argv)
    try:
        result = maintain(args.tokens_file, args.device_id, args.action, args.token_file)
    except (OSError, ValueError):
        parser.exit(2, "credential update failed; check files, action and operator lock privately\n")
    print(f"{result['action']}: snapshot updated; recreate API to reload credentials")
    if result["devices_remaining"] == 0:
        print("No devices remain: API startup will fail closed until a device is provisioned.")


if __name__ == "__main__":
    main()
