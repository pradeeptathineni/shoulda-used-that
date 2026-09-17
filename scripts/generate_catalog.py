#!/usr/bin/env python3
"""Generate or verify the committed public catalog from its exact profile."""

from __future__ import annotations

import argparse
from pathlib import Path

from shoulda_used_that.curation import compile_profile, load_profile
from shoulda_used_that.public_export import render_public_catalog, write_public_catalog

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "curation" / "profiles" / "shoulda-used-that.json"
DEFAULT_OUTPUT = ROOT / "docs" / "curation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    snapshot = compile_profile(args.profile)
    if args.check:
        export, expected = render_public_catalog(snapshot, profile)
        observed = _read_tree(args.output)
        if observed != expected:
            missing = sorted(set(expected) - set(observed))
            extra = sorted(set(observed) - set(expected))
            changed = sorted(
                path for path in set(expected) & set(observed) if expected[path] != observed[path]
            )
            print(f"public catalog is stale: missing={missing} extra={extra} changed={changed}")
            return 1
        print(f"verified deterministic public catalog {export.export_id}")
        return 0

    export, changed = write_public_catalog(snapshot, profile, args.output)
    state = "updated" if changed else "semantic no-op"
    print(f"{state}: {export.export_id} -> {args.output}")
    return 0


def _read_tree(root: Path) -> dict[str, bytes]:
    if not root.is_dir() or root.is_symlink():
        return {}
    result: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            return {}
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
