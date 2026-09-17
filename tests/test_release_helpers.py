from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.verify_release import verify
from scripts.write_checksums import checksum_lines


def test_checksums_are_sorted_and_include_only_release_assets(tmp_path: Path) -> None:
    (tmp_path / "b.whl").write_bytes(b"b")
    (tmp_path / "a.tar.gz").write_bytes(b"a")
    (tmp_path / "project.cdx.json").write_bytes(b"c")
    (tmp_path / ".gitignore").write_text("*", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not an asset", encoding="utf-8")
    (tmp_path / "SHA256SUMS").write_text("stale", encoding="utf-8")
    lines = checksum_lines(tmp_path)
    assert lines == [
        f"{hashlib.sha256(b'a').hexdigest()}  a.tar.gz",
        f"{hashlib.sha256(b'b').hexdigest()}  b.whl",
        f"{hashlib.sha256(b'c').hexdigest()}  project.cdx.json",
    ]


def test_checksums_require_assets(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no release assets"):
        checksum_lines(tmp_path)


def test_release_verifier_rejects_wrong_tag_without_git_lookup() -> None:
    problems = verify("v9.9.9", "0" * 40)
    assert "does not match package version" in problems[0]
    assert any("tag cannot be resolved" in item for item in problems)
