from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shoulda_used_that.models import (
    Candidate,
    FilterSpec,
    SourceKind,
    SourceObservation,
    normalize_repository,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Owner/Repo", "owner/repo"),
        ("Owner/Repo.git", "owner/repo"),
        ("https://github.com/Owner/Repo", "owner/repo"),
    ],
)
def test_repository_identity_is_canonical(raw: str, expected: str) -> None:
    assert normalize_repository(raw) == expected
    assert Candidate(repository=raw).repository == expected


@pytest.mark.parametrize("raw", ["repo", "owner/repo/extra", "", "https://example.com/x/y"])
def test_repository_identity_rejects_non_github_shape(raw: str) -> None:
    with pytest.raises(ValueError, match="owner/name"):
        normalize_repository(raw)


def test_candidate_normalizes_sets_and_rejects_extra_fields() -> None:
    candidate = Candidate(
        repository="a/b",
        topics=["z", "A", "z"],
        platforms="linux",
    )
    assert candidate.topics == ("A", "z")
    assert candidate.platforms == ("linux",)
    with pytest.raises(ValidationError, match="Extra inputs"):
        Candidate(repository="a/b", secret="nope")  # type: ignore[call-arg]


def test_naive_candidate_and_observation_times_are_rejected() -> None:
    naive = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
    with pytest.raises(ValidationError, match="timezone"):
        Candidate(repository="a/b", pushed_at=naive)
    with pytest.raises(ValidationError, match="timezone"):
        SourceObservation(
            kind=SourceKind.FIXTURE,
            observed_at=naive,
            tool_version="test/1",
            payload_fingerprint="payload_abc",
            candidate_count=0,
        )


def test_filter_spec_repeated_values_preserve_order_and_license_overlap_fails() -> None:
    spec = FilterSpec(languages=["Python", "Go", "Python"])
    assert spec.languages == ("Python", "Go")
    with pytest.raises(ValidationError, match="both allowed and denied"):
        FilterSpec(license_allow=("MIT",), license_deny=("mit",))


def test_filter_view_has_stable_public_aliases(candidate: Candidate) -> None:
    view = candidate.filter_view()
    assert view["repo"] == "fixture-labs/canonical-kit"
    assert view["updated"].startswith("2026-09-17")
    assert "pushed_at" not in view
    assert view["security"]["state"] == "verified"
