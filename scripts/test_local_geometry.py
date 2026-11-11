#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Compile and run the #9 C++17 fixtures; no hardware or third party packages."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitize", action="store_true", help="Enable AddressSanitizer and UBSan")
    args = parser.parse_args()
    compiler_name = os.environ.get("CXX", "c++")
    compiler = shutil.which(compiler_name)
    if not compiler:
        parser.error(f"C++17 compiler not found: {compiler_name}; set CXX to an executable")
    root = Path(__file__).resolve().parents[1]
    flags = ["-std=c++17", "-O2", "-g", "-Wall", "-Wextra", "-Werror"]
    if args.sanitize:
        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-fno-sanitize-recover=all"]
    with tempfile.TemporaryDirectory(prefix="sonar-local-geometry-") as directory:
        executable = Path(directory) / "local-geometry-tests"
        command = [compiler, *flags, "-I", str(root / "firmware/src/core"),
                   str(root / "firmware/tests/native/local_geometry_test.cpp"),
                   str(root / "firmware/src/core/local_geometry.cpp"), "-o", str(executable)]
        print(f"Compiler: {compiler}; C++17; sanitizer={args.sanitize}", flush=True)
        compiled = subprocess.run(command, cwd=root, check=False, timeout=120)
        if compiled.returncode:
            return compiled.returncode
        return subprocess.run([str(executable)], cwd=root, check=False, timeout=30).returncode


if __name__ == "__main__":
    raise SystemExit(main())
