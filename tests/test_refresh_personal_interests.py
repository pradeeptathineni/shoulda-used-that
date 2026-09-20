from __future__ import annotations

from typing import Any

import pytest

from scripts.refresh_personal_interests import build_entries


def _selection(*, gate_exceptions: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "reviewed_at": "2026-09-17T12:00:00Z",
        "minimum_stars": 1000,
        "maximum_staleness_days": 730,
        "evidence_receipt": "docs/decisions/example.json",
        "decision_receipt_id": "par_example",
        "collection_priority": ["tools"],
        "collections": {"tools": {"repositories": ["example/tool"]}},
        "gate_exceptions": gate_exceptions or {},
    }


def _metadata() -> dict[str, Any]:
    return {
        "example/tool": {
            "nameWithOwner": "example/tool",
            "url": "https://github.com/example/tool",
            "description": "An example tool.",
            "stargazerCount": 1200,
            "pushedAt": "2026-09-16T12:00:00Z",
            "isPrivate": False,
            "isArchived": False,
            "isDisabled": False,
            "isFork": False,
            "licenseInfo": {"spdxId": "MIT"},
            "latestRelease": {"tagName": "v1.0.0"},
            "defaultBranchRef": {"target": {"oid": "a" * 40}},
        }
    }


def test_refresh_separates_evidence_screening_and_projection() -> None:
    result = build_entries(
        _selection(),
        {"example/tool": ("tools",)},
        _metadata(),
    )

    assert result["schema_version"] == "3.0"
    assert set(result) == {
        "schema_version",
        "repository_evidence",
        "screenings",
        "projection_entries",
        "excluded_candidates",
    }
    assert result["repository_evidence"][0]["repository"] == "example/tool"
    assert result["screenings"][0] == {
        "repository": "example/tool",
        "domain_tags": ["tools"],
        "screening_basis": "metadata-and-eligibility",
        "decision_receipt_ids": ["par_example"],
        "evidence_receipt_ids": ["docs/decisions/example.json"],
        "notes": [],
        "screened_at": "2026-09-17T12:00:00Z",
    }
    assert result["projection_entries"][0] == {
        "repository": "example/tool",
        "collection_memberships": ["tools"],
        "primary_disposition": "reference",
    }
    assert "assessments" not in result


def test_gate_exception_is_screening_note_not_contextual_fit() -> None:
    result = build_entries(
        _selection(
            gate_exceptions={
                "example/tool": {
                    "waive": ["popularity"],
                    "reason": "Maintainer-reviewed niche utility.",
                }
            }
        ),
        {"example/tool": ("tools",)},
        _metadata(),
    )

    assert result["screenings"][0]["notes"] == ["Maintainer-reviewed niche utility."]
    assert all(
        key not in result["repository_evidence"][0]
        for key in ("role", "need", "rationale", "reconsideration_trigger")
    )


def test_retired_context_fields_require_explicit_assessment_migration() -> None:
    selection = _selection()
    selection["rationale_overrides"] = {"example/tool": "Old universal rationale."}

    with pytest.raises(SystemExit, match="explicit problem assessments"):
        build_entries(selection, {"example/tool": ("tools",)}, _metadata())


def test_overrides_must_name_a_selected_repository() -> None:
    selection = _selection()
    selection["disposition_overrides"] = {"other/tool": "reference"}

    with pytest.raises(SystemExit, match="unselected repositories: other/tool"):
        build_entries(selection, {"example/tool": ("tools",)}, _metadata())
