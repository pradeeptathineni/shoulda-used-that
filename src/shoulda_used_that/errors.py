"""Typed public errors for predictable CLI failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ShouldaError(Exception):
    """A failure with a stable machine code and actionable message."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class StateError(ShouldaError):
    """State is missing, invalid, unsafe, or conflicts with immutable data."""


class SourceError(ShouldaError):
    """A discovery or evidence source could not produce a complete result."""


class FilterError(ShouldaError):
    """A filter is invalid or could not be evaluated safely."""


class GitHubError(SourceError):
    """Base class for typed GitHub transport failures."""


class GitHubAuthError(GitHubError):
    """The official GitHub CLI is unavailable or not actively authenticated."""


class GitHubRateLimitError(GitHubError):
    """GitHub refused the operation because of a rate limit."""


class GitHubSchemaError(GitHubError):
    """A GitHub response did not match the documented shape."""


class GitHubPartialError(GitHubError):
    """Pagination began but did not complete, so no partial result may pass as complete."""
