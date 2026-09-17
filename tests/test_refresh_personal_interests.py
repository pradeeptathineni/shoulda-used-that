from __future__ import annotations

from typing import Any

import pytest

from scripts.refresh_personal_interests import build_entries


def _selection(*, rationale_overrides: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "reviewed_at": "2026-09-17T12:00:00Z",
        "minimum_stars": 1000,
        "maximum_staleness_days": 730,
        "evidence_receipt": "docs/decisions/example.json",
        "decision_receipt_id": "par_example",
        "collection_priority": ["tools"],
        "collections": {
            "tools": {
                "role": "example prior art",
                "need": "Compare an existing tool before building.",
                "reconsideration_trigger": "The evidence changes.",
            }
        },
        "rationale_overrides": rationale_overrides or {},
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


def test_default_rationale_states_the_review_boundary() -> None:
    result = build_entries(
        _selection(),
        {"example/tool": ("tools",)},
        _metadata(),
    )

    rationale = result["entries"][0]["rationale"]
    assert "public metadata and fit review" in rationale
    assert "not code, security, or adoption approval" in rationale


def test_reviewed_repository_can_have_a_specific_rationale() -> None:
    result = build_entries(
        _selection(rationale_overrides={"example/tool": "Use only as a learning map."}),
        {"example/tool": ("tools",)},
        _metadata(),
    )

    assert result["entries"][0]["rationale"] == "Use only as a learning map."


def test_rationale_override_must_name_a_selected_repository() -> None:
    with pytest.raises(SystemExit, match="unselected repositories: other/tool"):
        build_entries(
            _selection(rationale_overrides={"other/tool": "Not selected."}),
            {"example/tool": ("tools",)},
            _metadata(),
        )
