from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from shoulda_used_that.models import Candidate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "candidates.json"
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


@pytest.fixture
def fixture_path() -> Path:
    return FIXTURE


@pytest.fixture
def candidate() -> Candidate:
    return Candidate(
        repository="Fixture-Labs/Canonical-Kit.git",
        role="library",
        language="Python",
        ecosystems=("pypi",),
        topics=("receipts", "canonical-json"),
        license="Apache-2.0",
        archived=False,
        disabled=False,
        pushed_at=NOW,
        released_at=NOW,
        platforms=("linux",),
        runtimes=("python",),
        evidence_state="verified",
        network_boundary="local",
        security_state="verified",
        stars=120,
    )
