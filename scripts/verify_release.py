#!/usr/bin/env python3
"""Fail closed unless a release run is bound to the expected annotated version tag."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to verify an annotated release tag")
    completed = subprocess.run(  # noqa: S603 - fixed Git executable and repository arguments
        (git, *args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def verify(tag: str, expected_commit: str) -> list[str]:
    problems: list[str] = []
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    expected_tag = f"v{project['version']}"
    if tag != expected_tag:
        problems.append(f"tag {tag!r} does not match package version {expected_tag!r}")
    try:
        object_type = _git("cat-file", "-t", tag)
        peeled = _git("rev-parse", f"{tag}^{{}}")
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        problems.append(f"tag cannot be resolved: {exc}")
    else:
        if object_type != "tag":
            problems.append(f"{tag} is not an annotated tag")
        if peeled != expected_commit:
            problems.append(f"tag resolves to {peeled}, not workflow commit {expected_commit}")
    if not (ROOT / "docs" / "releases" / f"{tag}.md").is_file():
        problems.append(f"release notes are missing for {tag}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    parser.add_argument("commit")
    args = parser.parse_args()
    problems = verify(args.tag, args.commit)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"verified annotated release identity {args.tag} at {args.commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
