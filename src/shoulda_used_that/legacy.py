"""Read-only validators for receipt kinds retired after v0.3.0.

Released tags retain the original schemas. This module lets existing local JSON be
validated and inspected without preserving commands that create more of it.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import field_validator

from shoulda_used_that.models import Candidate, Disposition, FrozenModel, normalize_repository


class LegacySavedItem(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    repository: str
    candidate: Candidate
    saved_at: datetime
    disposition: Disposition | None = None
    source_check_id: str | None = None
    source_result_fingerprint: str | None = None

    _normalize_repository = field_validator("repository")(normalize_repository)


class LegacySaveReceipt(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    save_id: str
    created_at: datetime
    profile: str
    repositories: tuple[str, ...]
    created: tuple[str, ...]
    already_saved: tuple[str, ...]
    disposition: Disposition | None = None
    source_check_id: str | None = None
    source_result_fingerprint: str | None = None
    projection_plan_id: str | None = None


class LegacyProjectionOperation(FrozenModel):
    repository: str
    classification: Literal["already_starred", "requires_star"]
    status: Literal["planned", "blocked"]
    operations: tuple[str, ...]


class LegacyProjectionPlan(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    plan_id: str
    plan_fingerprint: str
    created_at: datetime
    profile: str
    list_name: str
    source_check_id: str
    source_result_fingerprint: str
    source_state_fingerprint: str
    operations: tuple[LegacyProjectionOperation, ...]
    mutation_state: Literal["sealed-unapplied"] = "sealed-unapplied"


class LegacyAdoptionPlan(FrozenModel):
    schema_version: Literal["1.0"] = "1.0"
    plan_id: str
    plan_fingerprint: str
    created_at: datetime
    profile: str
    repository: str
    need: str
    target: str
    proposed_files: tuple[str, ...] = ()
    native_tools: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    expected_postconditions: tuple[str, ...]
    rollback: tuple[str, ...]
    remaining_evidence: tuple[str, ...] = ()
    mutation_state: Literal["planning-only"] = "planning-only"

    _normalize_repository = field_validator("repository")(normalize_repository)


type LegacyRecord = LegacySavedItem | LegacySaveReceipt | LegacyProjectionPlan | LegacyAdoptionPlan


def load_legacy_record(path: Path) -> LegacyRecord:
    """Validate one explicit retired record without mutating or migrating it."""

    if path.is_symlink() or not path.is_file():
        raise ValueError("legacy record must be a regular non-symlink file")
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"legacy record is unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("legacy record must contain a JSON object")
    if "save_id" in payload:
        return LegacySaveReceipt.model_validate(payload)
    if isinstance(payload.get("plan_id"), str) and payload["plan_id"].startswith("prj_"):
        return LegacyProjectionPlan.model_validate(payload)
    if isinstance(payload.get("plan_id"), str) and payload["plan_id"].startswith("use_"):
        return LegacyAdoptionPlan.model_validate(payload)
    if "saved_at" in payload and "candidate" in payload:
        return LegacySavedItem.model_validate(payload)
    raise ValueError("record is not a retired save, projection, or adoption record")
