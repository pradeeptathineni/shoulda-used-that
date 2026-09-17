#!/usr/bin/env python3
"""Write deterministic SHA-256 checksums for release assets."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

RELEASE_SUFFIXES = (".whl", ".tar.gz", ".cdx.json")


def checksum_lines(directory: Path) -> list[str]:
    assets = sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and not path.is_symlink() and path.name.endswith(RELEASE_SUFFIXES)
    )
    if not assets:
        raise ValueError(f"no release assets found in {directory}")
    return [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in assets]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    output = args.directory / "SHA256SUMS"
    output.write_text("\n".join(checksum_lines(args.directory)) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
