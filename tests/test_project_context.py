from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from shoulda_used_that.cli import cli
from shoulda_used_that.errors import GitHubError, GitHubNotFoundError, SourceError, StateError
from shoulda_used_that.github import GhResult, GhSbomResult
from shoulda_used_that.models import FilterSpec
from shoulda_used_that.project_context import ProjectSnapshot, inspect_project
from shoulda_used_that.services import checked, inspected, rechecked
from shoulda_used_that.state import StateStore
from tests.support import LATER, NOW, fixture_request

ROOT = Path(__file__).resolve().parents[1]
SPDX = ROOT / "fixtures" / "project_context" / "spdx.json"
CYCLONEDX = ROOT / "fixtures" / "project_context" / "cyclonedx.json"


class FakeProjectGitHub:
    def __init__(self, sbom: GhSbomResult | BaseException) -> None:
        self.sbom = sbom
        self.calls: list[str] = []

    def repository(self, repository: str) -> GhResult:
        self.calls.append(f"repository:{repository}")
        return GhResult(
            payload={
                "full_name": repository,
                "node_id": "R_fixture",
                "visibility": "public",
                "private": False,
                "default_branch": "main",
                "archived": False,
                "topics": ["receipts", "open-source"],
                "license": {"spdx_id": "Apache-2.0"},
            },
            tool_version="2.test",
            endpoint=f"repos/{repository}",
            paginated=False,
        )

    def repository_languages(self, repository: str) -> GhResult:
        self.calls.append(f"languages:{repository}")
        return GhResult(
            payload={"Python": 1200, "Shell": 20},
            tool_version="2.test",
            endpoint=f"repos/{repository}/languages",
            paginated=False,
        )

    def repository_commit(self, repository: str, reference: str) -> GhResult:
        self.calls.append(f"commit:{repository}@{reference}")
        return GhResult(
            payload={"sha": "a" * 40},
            tool_version="2.test",
            endpoint=f"repos/{repository}/commits/{reference}",
            paginated=False,
        )

    def dependency_sbom(self, repository: str) -> GhSbomResult:
        self.calls.append(f"sbom:{repository}")
        if isinstance(self.sbom, BaseException):
            raise self.sbom
        return self.sbom


def _spdx_payload() -> dict[str, Any]:
    payload = json.loads(SPDX.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _local_project(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    source = root / "src"
    source.mkdir()
    (source / "ignored.bin").write_bytes(b"\xff\xfe")


def test_local_snapshot_is_bounded_portable_deterministic_and_read_only(tmp_path: Path) -> None:
    project = tmp_path / "Fixture Project"
    _local_project(project)
    before = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))

    first = inspect_project(str(project), sbom_path=SPDX, observed_at=NOW)
    second = inspect_project(str(project), sbom_path=SPDX, observed_at=NOW)
    after = sorted(path.relative_to(project).as_posix() for path in project.rglob("*"))

    assert second == first
    assert before == after
    assert first.target_identity == "local:fixture-project"
    assert [item.relative_path for item in first.manifest_facts] == [
        "pyproject.toml",
        "uv.lock",
    ]
    assert first.sbom is not None
    assert first.sbom.format == "spdx"
    assert first.sbom.specification_version == "SPDX-2.3"
    assert [item.identity for item in first.dependency_components] == [
        "pkg:pypi/click@8.5.0",
        "pkg:pypi/fixture-python-project@0.2.0",
    ]
    assert first.ecosystems == ("pypi",)
    serialized = json.dumps(first.model_dump(mode="json"), sort_keys=True)
    assert str(tmp_path) not in serialized
    assert "ignored.bin" not in serialized


def test_cyclonedx_nested_components_are_normalized(tmp_path: Path) -> None:
    project = tmp_path / "web"
    project.mkdir()
    (project / "package.json").write_text("{}\n", encoding="utf-8")

    snapshot = inspect_project(str(project), sbom_path=CYCLONEDX, observed_at=NOW)

    assert snapshot.sbom is not None
    assert snapshot.sbom.format == "cyclonedx"
    assert snapshot.sbom.document_name == "fixture-web-project"
    assert [item.identity for item in snapshot.dependency_components] == [
        "pkg:npm/example-package@2.0.0",
        "pkg:npm/nested-package@1.2.3",
    ]
    assert snapshot.ecosystems == ("npm",)


def test_github_snapshot_records_metadata_languages_commit_and_native_sbom() -> None:
    github = FakeProjectGitHub(
        GhSbomResult("available", _spdx_payload(), "00000000-0000-0000-0000-000000000001", "2.test")
    )

    snapshot = inspect_project("github:Fixture-Labs/Project", github=github, observed_at=NOW)

    assert snapshot.target_identity == "github:fixture-labs/project"
    assert snapshot.repository_metadata is not None
    assert snapshot.repository_metadata.head_commit == "a" * 40
    assert snapshot.repository_metadata.default_branch == "main"
    assert [item.name for item in snapshot.languages] == ["Python", "Shell"]
    assert snapshot.topics == ("open-source", "receipts")
    assert snapshot.sbom is not None
    assert snapshot.sbom.component_count == 2
    assert snapshot.evidence_gaps == ()
    assert github.calls == [
        "repository:fixture-labs/project",
        "languages:fixture-labs/project",
        "commit:fixture-labs/project@main",
        "sbom:fixture-labs/project",
    ]


@pytest.mark.parametrize(
    ("sbom_result", "state", "code"),
    [
        (
            GhSbomResult("pending", None, "00000000-0000-0000-0000-000000000002", "2.test"),
            "pending",
            "github_sbom_pending",
        ),
        (
            GitHubNotFoundError("github_not_found", "missing"),
            "unavailable",
            "github_sbom_unavailable",
        ),
        (
            GitHubError("github_sbom_generation_failed", "failed"),
            "error",
            "github_sbom_generation_failed",
        ),
    ],
)
def test_github_sbom_pending_missing_and_failure_are_typed(
    sbom_result: GhSbomResult | BaseException, state: str, code: str
) -> None:
    snapshot = inspect_project(
        "github:fixture-labs/project",
        github=FakeProjectGitHub(sbom_result),
        observed_at=NOW,
    )

    assert snapshot.sbom is None
    gap = next(item for item in snapshot.evidence_gaps if item.subject == "dependency inventory")
    assert gap.state.value == state
    assert gap.code == code


def test_supplied_sbom_prevents_native_github_sbom_request() -> None:
    github = FakeProjectGitHub(AssertionError("native SBOM must not be requested"))

    snapshot = inspect_project(
        "github:fixture-labs/project",
        sbom_path=CYCLONEDX,
        github=github,
        observed_at=NOW,
    )

    assert snapshot.sbom is not None
    assert snapshot.sbom.format == "cyclonedx"
    assert not any(call.startswith("sbom:") for call in github.calls)


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_local_boundaries_reject_root_and_nested_symlink_escape(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _local_project(project)
    root_link = tmp_path / "root-link"
    try:
        root_link.symlink_to(project, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(StateError) as linked_root:
        inspect_project(str(root_link), observed_at=NOW)
    assert linked_root.value.code == "project_root_unsafe"

    outside = tmp_path / "outside.toml"
    outside.write_text("outside = true\n", encoding="utf-8")
    (project / "nested-link").symlink_to(outside)
    with pytest.raises(StateError) as escaped:
        inspect_project(str(project), observed_at=NOW)
    assert escaped.value.code == "project_symlink_escape"


def test_local_file_count_size_and_invalid_sbom_are_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    _local_project(project)
    monkeypatch.setattr("shoulda_used_that.project_context.MAX_LOCAL_FILES", 1)
    with pytest.raises(StateError) as file_count:
        inspect_project(str(project), observed_at=NOW)
    assert file_count.value.code == "project_tree_too_large"

    monkeypatch.setattr("shoulda_used_that.project_context.MAX_LOCAL_FILES", 20_000)
    monkeypatch.setattr("shoulda_used_that.project_context.MAX_MANIFEST_BYTES", 4)
    with pytest.raises(SourceError) as manifest_size:
        inspect_project(str(project), observed_at=NOW)
    assert manifest_size.value.code == "project_manifest_too_large"

    invalid = tmp_path / "invalid-sbom.json"
    invalid.write_bytes(b"\xff\xfe")
    monkeypatch.setattr("shoulda_used_that.project_context.MAX_MANIFEST_BYTES", 2 * 1024 * 1024)
    with pytest.raises(SourceError) as invalid_sbom:
        inspect_project(str(project), sbom_path=invalid, observed_at=NOW)
    assert invalid_sbom.value.code == "project_sbom_invalid_json"


def test_local_traversal_permission_failure_is_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()

    def denied_walk(*_args: Any, onerror: Any, **_kwargs: Any) -> Any:
        onerror(PermissionError("denied"))
        yield from ()

    monkeypatch.setattr("shoulda_used_that.project_context.os.walk", denied_walk)
    with pytest.raises(StateError) as raised:
        inspect_project(str(project), observed_at=NOW)
    assert raised.value.code == "project_tree_unreadable"


def test_project_state_and_checked_context_are_visible_and_replayable(
    tmp_path: Path, fixture_path: Path
) -> None:
    project = tmp_path / "project"
    _local_project(project)
    store = StateStore(tmp_path / "state")
    snapshot = inspected(store, target=str(project), sbom_path=SPDX, observed_at=NOW)

    assert store.write_project(snapshot) is False
    assert store.read_project(snapshot.project_snapshot_id) == snapshot
    assert store.latest_project() == snapshot
    assert store.latest_project(snapshot.target_identity) == snapshot

    receipt = checked(
        store,
        need="select a compatible reusable component",
        source_requests=(fixture_request(fixture_path),),
        filter_spec=FilterSpec(limit=5),
        project_snapshot=snapshot,
        observed_at=NOW,
    )
    assert receipt.project_snapshot_id == snapshot.project_snapshot_id
    canonical = next(
        item
        for item in receipt.evaluations
        if item.candidate.repository == "fixture-labs/canonical-kit"
    )
    javascript = next(
        item
        for item in receipt.evaluations
        if item.candidate.repository == "fixture-labs/js-helper"
    )
    assert canonical.applicability[0].relationship == "match"
    assert javascript.applicability[0].relationship == "mismatch"
    assert canonical.applicability[0].effect == "evidence-only"

    replay = rechecked(store, target_id=receipt.check_id, checked_at=LATER)
    assert replay.source_errors == ()
    replayed_check = store.read_check(
        next(
            path.stem
            for path in (store.profile_root / "checks").glob("chk_*.json")
            if path.stem != receipt.check_id
        )
    )
    assert replayed_check.project_snapshot_id == snapshot.project_snapshot_id
    assert replayed_check.evaluations[0].applicability


def test_cli_inspected_then_checked_in_snapshot(tmp_path: Path, fixture_path: Path) -> None:
    project = tmp_path / "project"
    _local_project(project)
    state = tmp_path / "state"
    runner = CliRunner()
    inspected_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "inspected",
            str(project),
            "--sbom",
            str(SPDX),
        ],
    )
    assert inspected_result.exit_code == 0, inspected_result.output
    snapshot: dict[str, Any] = json.loads(inspected_result.stdout)

    checked_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "json",
            "checked",
            "context-aware fixture check",
            "--source",
            "fixture",
            "--fixture",
            str(fixture_path),
            "--in",
            snapshot["project_snapshot_id"],
        ],
    )
    assert checked_result.exit_code == 0, checked_result.output
    receipt: dict[str, Any] = json.loads(checked_result.stdout)
    assert receipt["project_snapshot_id"] == snapshot["project_snapshot_id"]
    assert receipt["evaluations"][0]["applicability"]

    table_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(state),
            "--format",
            "table",
            "checked",
            "context-aware fixture check",
            "--source",
            "fixture",
            "--fixture",
            str(fixture_path),
            "--in",
            snapshot["project_snapshot_id"],
        ],
    )
    assert table_result.exit_code == 0, table_result.output
    assert "ecosystem:match" in table_result.stdout
    assert table_result.stdout.count("fixture-labs/canonical-kit") == 1


def test_project_snapshot_rejects_unknown_schema() -> None:
    github = FakeProjectGitHub(
        GhSbomResult("available", _spdx_payload(), "00000000-0000-0000-0000-000000000003", "2.test")
    )
    snapshot = inspect_project("github:fixture-labs/project", github=github, observed_at=NOW)
    payload = snapshot.model_dump(mode="json")
    payload["schema_version"] = "99.0"
    with pytest.raises(ValidationError, match="schema_version"):
        ProjectSnapshot.model_validate(payload)
