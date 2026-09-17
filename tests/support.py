from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from shoulda_used_that.models import SourceKind, SourceRequest

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
LATER = datetime(2026, 9, 17, 13, tzinfo=UTC)


def fixture_request(path: Path) -> SourceRequest:
    return SourceRequest(kind=SourceKind.FIXTURE, locator=str(path))
