from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from shoulda_used_that.errors import SourceError
from shoulda_used_that.github import GhResult
from shoulda_used_that.models import Candidate, SourceKind, SourceRequest
from shoulda_used_that.sources import SourceBatch, load_sources, merge_batches

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


class FakeGitHub:
    def starred(self) -> GhResult:
        return GhResult(
            [
                {
                    "starred_at": "2026-09-01T00:00:00Z",
                    "repo": _github_item("Fixture-Labs/Starred", "MIT"),
                }
            ],
            "2.test",
            "user/starred",
            True,
        )

    def search(self, query: str, *, maximum: int = 100) -> GhResult:
        assert query == "canonical"
        assert maximum == 100
        return GhResult(
            [_github_item("Fixture-Labs/Search", "NOASSERTION")],
            "2.test",
            "search/repositories",
            False,
        )

    def repository(self, repository: str) -> GhResult:
        return GhResult(
            _github_item(repository, "Apache-2.0"),
            "2.test",
            f"repos/{repository}",
            False,
        )


def _github_item(repository: str, license_id: str) -> dict[str, Any]:
    return {
        "full_name": repository,
        "description": "Synthetic GitHub response",
        "language": "Python",
        "topics": ["receipts"],
        "license": {"spdx_id": license_id},
        "archived": False,
        "disabled": False,
        "pushed_at": "2026-09-01T00:00:00Z",
        "stargazers_count": 7,
        "html_url": f"https://github.com/{repository}",
    }


def test_json_and_yaml_fixtures_load_with_content_identity(
    fixture_path: Path, tmp_path: Path
) -> None:
    json_batch = load_sources(
        (SourceRequest(kind=SourceKind.FIXTURE, locator=str(fixture_path)),),
        observed_at=NOW,
    )[0]
    yaml_path = tmp_path / "same.yaml"
    yaml_path.write_text(
        "candidates:\n  - repository: fixture-labs/yaml\n    license: MIT\n",
        encoding="utf-8",
    )
    yaml_batch = load_sources(
        (SourceRequest(kind=SourceKind.FIXTURE, locator=str(yaml_path)),),
        observed_at=NOW,
    )[0]

    assert len(json_batch.candidates) == 5
    assert json_batch.observation.payload_fingerprint.startswith("payload_")
    assert json_batch.candidates[0].sources[0].startswith("fixture:src_")
    assert yaml_batch.candidates[0].repository == "fixture-labs/yaml"


@pytest.mark.parametrize(
    ("source_request", "code"),
    [
        (SourceRequest(kind=SourceKind.FIXTURE), "fixture_required"),
        (SourceRequest(kind=SourceKind.GITHUB_SEARCH), "query_required"),
        (SourceRequest(kind=SourceKind.REPOSITORY), "repository_required"),
    ],
)
def test_explicit_sources_require_their_locator(source_request: SourceRequest, code: str) -> None:
    with pytest.raises(SourceError) as raised:
        load_sources(
            (source_request,),
            github=FakeGitHub(),
            observed_at=NOW,  # type: ignore[arg-type]
        )
    assert raised.value.code == code


def test_fixture_safety_and_schema_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(SourceError, match="cannot be read"):
        load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(missing)),))

    real = tmp_path / "real.json"
    real.write_text("[]", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(SourceError) as linked:
        load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(link)),))
    assert linked.value.code == "fixture_not_regular_file"

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    with pytest.raises(SourceError) as malformed:
        load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(invalid)),))
    assert malformed.value.code == "fixture_invalid"

    wrong_shape = tmp_path / "shape.json"
    wrong_shape.write_text('{"candidates": {}}', encoding="utf-8")
    with pytest.raises(SourceError) as schema:
        load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(wrong_shape)),))
    assert schema.value.code == "fixture_schema_invalid"

    bad_candidate = tmp_path / "candidate.json"
    bad_candidate.write_text('[{"repository": "not-a-repository"}]', encoding="utf-8")
    with pytest.raises(SourceError) as candidate:
        load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(bad_candidate)),))
    assert candidate.value.code == "fixture_candidate_invalid"

    monkeypatch.setattr("shoulda_used_that.sources.MAX_FIXTURE_BYTES", 1)
    with pytest.raises(SourceError) as large:
        load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(real)),))
    assert large.value.code == "fixture_too_large"


def test_github_sources_normalize_typed_candidates() -> None:
    requests = (
        SourceRequest(kind=SourceKind.STARS),
        SourceRequest(kind=SourceKind.GITHUB_SEARCH, query="canonical"),
        SourceRequest(kind=SourceKind.REPOSITORY, locator="Fixture-Labs/Exact"),
    )
    batches = load_sources(requests, github=FakeGitHub(), observed_at=NOW)  # type: ignore[arg-type]

    assert [item.candidates[0].repository for item in batches] == [
        "fixture-labs/starred",
        "fixture-labs/search",
        "fixture-labs/exact",
    ]
    assert batches[0].candidates[0].is_starred is True
    assert batches[0].candidates[0].starred_at is not None
    assert batches[1].candidates[0].license is None
    assert all(item.observation.tool_version == "gh/2.test" for item in batches)


def test_github_source_schema_failures() -> None:
    class BadStars(FakeGitHub):
        def starred(self) -> GhResult:
            return GhResult([{}], "x", "user/starred", True)

    class BadRepo(FakeGitHub):
        def repository(self, repository: str) -> GhResult:
            return GhResult({}, "x", repository, False)

    with pytest.raises(SourceError) as star_error:
        load_sources(
            (SourceRequest(kind=SourceKind.STARS),),
            github=BadStars(),  # type: ignore[arg-type]
        )
    assert star_error.value.code == "github_star_schema_invalid"
    with pytest.raises(SourceError) as repo_error:
        load_sources(
            (SourceRequest(kind=SourceKind.REPOSITORY, locator="a/b"),),
            github=BadRepo(),  # type: ignore[arg-type]
        )
    assert repo_error.value.code == "github_repository_schema_invalid"


def test_merge_is_deterministic_and_preserves_conflicts() -> None:
    request = SourceRequest(kind=SourceKind.FIXTURE, locator="synthetic")
    observation_data = {
        "kind": SourceKind.FIXTURE,
        "locator": "synthetic",
        "observed_at": NOW,
        "tool_version": "test/1",
        "payload_fingerprint": "payload_abc",
        "candidate_count": 1,
    }
    from shoulda_used_that.models import SourceObservation

    observation = SourceObservation(**observation_data)
    first = Candidate(
        repository="fixtures/merge",
        language="Python",
        license=None,
        topics=("one",),
        evidence_state="claim",
        metadata={"first": True},
    )
    second = Candidate(
        repository="fixtures/merge",
        language="Go",
        license="MIT",
        topics=("two",),
        evidence_state="verified",
        metadata={"second": True},
    )
    batches = (
        SourceBatch(request, observation, (first,)),
        SourceBatch(request, observation, (second,)),
    )
    merged, raw_count = merge_batches(batches)

    assert raw_count == 2
    assert merged[0].language == "Python"
    assert merged[0].license == "MIT"
    assert merged[0].topics == ("one", "two")
    assert merged[0].evidence_state.value == "verified"
    assert "language: retained first observed value" in merged[0].conflicts
    assert merged[0].metadata == {"second": True, "first": True}


def test_fixture_payload_fingerprint_matches_parsed_content(tmp_path: Path) -> None:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps([{"repository": "fixture-labs/a"}]), encoding="utf-8")
    batch = load_sources((SourceRequest(kind=SourceKind.FIXTURE, locator=str(path)),))[0]
    assert batch.observation.candidate_count == 1
