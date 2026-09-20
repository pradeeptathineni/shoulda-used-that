from __future__ import annotations

import json
from pathlib import Path

import pytest

from shoulda_used_that.legacy import (
    LegacyAdoptionPlan,
    LegacySaveReceipt,
    load_legacy_record,
)


def test_retired_receipts_remain_readable_without_creation_services(tmp_path: Path) -> None:
    save_path = tmp_path / "sav_legacy.json"
    save_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "save_id": "sav_0123456789abcdef",
                "created_at": "2026-09-17T12:00:00Z",
                "profile": "default",
                "repositories": ["fixture-labs/canonical-kit"],
                "created": ["fixture-labs/canonical-kit"],
                "already_saved": [],
                "disposition": "trial",
                "source_check_id": "chk_0123456789abcdef",
                "source_result_fingerprint": "result_legacy",
                "projection_plan_id": None,
            }
        ),
        encoding="utf-8",
    )
    adoption_path = tmp_path / "use_legacy.json"
    adoption_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "plan_id": "use_0123456789abcdef",
                "plan_fingerprint": "plan_legacy",
                "created_at": "2026-09-17T12:00:00Z",
                "profile": "default",
                "repository": "Fixture-Labs/Canonical-Kit",
                "need": "canonical bytes",
                "target": "synthetic-target",
                "proposed_files": ["adapter.py"],
                "native_tools": ["pytest"],
                "tests": ["published vectors"],
                "expected_postconditions": ["vectors pass"],
                "rollback": ["remove adapter"],
                "remaining_evidence": [],
                "mutation_state": "planning-only",
            }
        ),
        encoding="utf-8",
    )

    saved = load_legacy_record(save_path)
    adoption = load_legacy_record(adoption_path)
    assert isinstance(saved, LegacySaveReceipt)
    assert saved.repositories == ("fixture-labs/canonical-kit",)
    assert isinstance(adoption, LegacyAdoptionPlan)
    assert adoption.repository == "fixture-labs/canonical-kit"


def test_legacy_reader_refuses_unknown_and_symlink_inputs(tmp_path: Path) -> None:
    unknown = tmp_path / "unknown.json"
    unknown.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a retired"):
        load_legacy_record(unknown)

    link = tmp_path / "legacy-link.json"
    link.symlink_to(unknown)
    with pytest.raises(ValueError, match="non-symlink"):
        load_legacy_record(link)
