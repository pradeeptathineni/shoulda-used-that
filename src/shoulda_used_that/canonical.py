"""RFC 8785 canonical JSON and content identity helpers."""

from __future__ import annotations

import hashlib
from typing import Any

import rfc8785

from shoulda_used_that.errors import ShouldaError


def canonical_bytes(value: Any) -> bytes:
    """Serialize a JSON-compatible value with RFC 8785."""

    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as exc:
        raise ShouldaError(
            code="canonicalization_failed",
            message=f"Value cannot be represented as RFC 8785 canonical JSON: {exc}",
        ) from exc


def digest(value: Any, *, prefix: str | None = None) -> str:
    """Return a SHA-256 content identity over canonical JSON."""

    value_digest = hashlib.sha256(canonical_bytes(value)).hexdigest()
    return f"{prefix}_{value_digest}" if prefix else value_digest


def short_id(value: Any, *, prefix: str, length: int = 24) -> str:
    """Return a readable, collision-resistant prefix of a canonical digest."""

    if length < 16:
        raise ValueError("short IDs must retain at least 16 hexadecimal characters")
    return f"{prefix}_{hashlib.sha256(canonical_bytes(value)).hexdigest()[:length]}"
