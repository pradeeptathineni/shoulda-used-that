from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.cli import cli
from shoulda_used_that.curation import (
    CurationCounts,
    CurationSemanticDiff,
    CurationSnapshot,
    MutationPolicy,
    OperationCaps,
    ProjectionPolicy,
    _snapshot_semantic,
    compile_profile,
    validate_curation_snapshot,
)
from shoulda_used_that.errors import StateError
from shoulda_used_that.github import GhAuthStatus, GhResult
from shoulda_used_that.github_lists import (
    GitHubCapabilityProbe,
    GitHubCapabilityState,
    GitHubCurationState,
    GitHubListMember,
    GitHubListState,
    GitHubRelevantRepository,
)
from shoulda_used_that.projection import (
    FORBIDDEN_OPERATION_CLASSES,
    PROJECTABLE_DISPOSITIONS,
    GitHubProjectionOperation,
    GitHubProjectionPlan,
    build_projection_plan,
    desired_projection_repositories,
)
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.services import projected
from shoulda_used_that.state import StateStore

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PROFILE = ROOT / "curation" / "profiles" / "shoulda-used-that.json"
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)
PROJECTION_REPOSITORIES = (
    "actions/runner",
    "addyosmani/agent-skills",
    "astral-sh/uv",
    "browser-use/browser-use",
    "ollama/ollama",
    "pallets/click",
)
PROJECTION_COLLECTIONS = (
    "generative-ai-agents",
    "platform-engineering-delivery",
)


@lru_cache(maxsize=1)
def _projection_snapshot() -> CurationSnapshot:
    """Keep projection mechanics tests bounded as the public catalog grows."""

    source = compile_profile(PUBLIC_PROFILE)
    collections = tuple(
        collection
        for collection in source.collection_definitions
        if collection.slug in PROJECTION_COLLECTIONS
    )
    entries = tuple(
        sorted(
            (
                entry.model_copy(
                    update={
                        "collection_memberships": tuple(
                            slug
                            for slug in PROJECTION_COLLECTIONS
                            if slug in entry.collection_memberships
                        )
                    }
                )
                for entry in source.entries
                if entry.repository in PROJECTION_REPOSITORIES
            ),
            key=lambda entry: entry.repository,
        )
    )
    projection_policy = ProjectionPolicy(
        enabled=True,
        account="pradeeptathineni",
        selected_collection_slugs=PROJECTION_COLLECTIONS,
        max_projected_lists=len(PROJECTION_COLLECTIONS),
    )
    mutation_policy = MutationPolicy(
        plan_expiry_hours=24,
        caps=OperationCaps(
            total=20,
            create_lists=2,
            star_repositories=10,
            add_memberships=20,
        ),
    )
    membership_map = {
        slug: tuple(entry.repository for entry in entries if slug in entry.collection_memberships)
        for slug in sorted(PROJECTION_COLLECTIONS)
    }
    counts = CurationCounts(
        sources=len(source.source_snapshots),
        entries=len(entries),
        excluded=0,
        inbox=0,
        stale=0,
        partial=0,
        blocked=0,
    )
    semantic = _snapshot_semantic(
        profile_fingerprint=source.profile_fingerprint,
        compiler_version=source.compiler_version,
        compiled_at=source.compiled_at,
        collections=collections,
        projection_policy=projection_policy,
        mutation_policy=mutation_policy,
        source_snapshots=source.source_snapshots,
        entries=entries,
        exclusions=(),
        membership_map=membership_map,
        counts=counts,
    )
    fixture = source.model_copy(
        update={
            "curation_snapshot_id": short_id(semantic, prefix="cur"),
            "collection_definitions": collections,
            "projection_policy": projection_policy,
            "mutation_policy": mutation_policy,
            "entries": entries,
            "excluded_candidates": (),
            "unresolved_inbox_entries": (),
            "stale_entries": (),
            "partial_entries": (),
            "blocked_entries": (),
            "collection_membership_map": membership_map,
            "counts": counts,
            "semantic_diff": CurationSemanticDiff(
                added_repositories=tuple(entry.repository for entry in entries),
                material=True,
            ),
            "canonical_fingerprint": digest(semantic, prefix="curation"),
        }
    )
    validate_curation_snapshot(fixture)
    return fixture


class ReadOnlyProjectionClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def auth_status(self) -> GhAuthStatus:
        self.calls.append("auth-status")
        return GhAuthStatus("pradeeptathineni", "github.com", ("repo",), "fixture", "2.test")

    def graphql(
        self,
        query: str,
        *,
        variables: dict[str, str] | None = None,
        maximum_output_bytes: int = 20 * 1024 * 1024,
    ) -> GhResult:
        del variables, maximum_output_bytes
        self.calls.append("graphql-capability" if "userType:" in query else "graphql-lists")
        if "userType:" in query:
            payload: dict[str, Any] = {
                "data": {
                    "viewer": {"login": "pradeeptathineni", "id": "U_owner"},
                    "userType": {"fields": [{"name": "lists"}]},
                    "itemType": {
                        "kind": "UNION",
                        "possibleTypes": [{"name": "Repository"}],
                    },
                    "mutationType": {
                        "fields": [
                            {"name": "createUserList"},
                            {"name": "updateUserListsForItem"},
                        ]
                    },
                    "createInput": {
                        "inputFields": [
                            {"name": "name"},
                            {"name": "description"},
                            {"name": "isPrivate"},
                        ]
                    },
                    "membershipInput": {"inputFields": [{"name": "itemId"}, {"name": "listIds"}]},
                }
            }
        else:
            payload = {
                "data": {
                    "viewer": {
                        "login": "pradeeptathineni",
                        "id": "U_owner",
                        "lists": {
                            "totalCount": 0,
                            "nodes": [],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        },
                    }
                }
            }
        return GhResult(payload, "2.test", "graphql", False)

    def api_version_probe(self) -> GhResult:
        self.calls.append("api-version")
        return GhResult({}, "2.test", "meta", False)

    def starred(self) -> GhResult:
        self.calls.append("read-stars")
        return GhResult([], "2.test", "user/starred", True)

    def user_starred(self, login: str) -> GhResult:
        raise AssertionError(f"public stars are not used for viewer {login}")

    def repository(self, repository: str) -> GhResult:
        self.calls.append(f"read-repository:{repository}")
        return GhResult(
            {
                "node_id": _node(repository),
                "full_name": repository,
                "private": False,
                "archived": False,
                "html_url": f"https://github.com/{repository}",
            },
            "2.test",
            f"repos/{repository}",
            False,
        )


def _capability(
    state: GitHubCapabilityState = GitHubCapabilityState.AVAILABLE,
) -> GitHubCapabilityProbe:
    missing = ("user",) if state is GitHubCapabilityState.MISSING_SCOPE else ()
    return GitHubCapabilityProbe(
        observed_at=NOW,
        state=state,
        login="pradeeptathineni",
        node_id="U_owner",
        gh_version="2.test",
        scopes=("repo",) if missing else ("repo", "user"),
        rest_api_version="2026-03-10",
        rest_api_probe_passed=True,
        lists_field_present=True,
        repository_item_union_exact=True,
        required_mutations_present=True,
        missing_scopes=missing,
        operator_command=("gh auth refresh --hostname github.com -s user" if missing else None),
    )


def _member(repository: str, node_id: str | None = None) -> GitHubListMember:
    return GitHubListMember(
        node_id=node_id or _node(repository),
        repository=repository,
        is_private=False,
        is_archived=False,
        url=f"https://github.com/{repository}",
    )


def _node(repository: str) -> str:
    return "R_" + repository.replace("/", "_")


def _github_state(
    *,
    starred: bool = False,
    lists: tuple[GitHubListState, ...] = (),
    private_repository: str | None = None,
    archived_repository: str | None = None,
    extra_repository: str | None = None,
) -> GitHubCurationState:
    snapshot = _projection_snapshot()
    repositories = [
        GitHubRelevantRepository(
            node_id=_node(repository),
            repository=repository,
            is_private=repository == private_repository,
            is_archived=repository == archived_repository,
            url=f"https://github.com/{repository}",
            starred=starred,
            starred_at=NOW if starred else None,
        )
        for repository in desired_projection_repositories(snapshot)
    ]
    if extra_repository:
        repositories.append(
            GitHubRelevantRepository(
                node_id=_node(extra_repository),
                repository=extra_repository,
                is_private=False,
                is_archived=False,
                url=f"https://github.com/{extra_repository}",
                starred=starred,
                starred_at=NOW if starred else None,
            )
        )
    repositories.sort(key=lambda item: item.repository)
    semantic = {
        "account": "pradeeptathineni",
        "account_node_id": "U_owner",
        "relevant_repositories": [item.model_dump(mode="json") for item in repositories],
        "lists": [item.model_dump(mode="json") for item in lists],
    }
    return GitHubCurationState(
        account="pradeeptathineni",
        account_node_id="U_owner",
        observed_at=NOW,
        total_starred_count=len(repositories) if starred else 0,
        relevant_repositories=tuple(repositories),
        lists=lists,
        state_fingerprint=digest(semantic, prefix="github"),
    )


def _satisfied_lists() -> tuple[GitHubListState, ...]:
    snapshot = _projection_snapshot()
    collections = {item.slug: item for item in snapshot.collection_definitions}
    return tuple(
        GitHubListState(
            node_id=f"L_{slug}",
            name=collections[slug].title,
            description=collections[slug].description,
            is_private=False,
            slug=slug,
            members=tuple(
                _member(repository) for repository in snapshot.collection_membership_map[slug]
            ),
        )
        for slug in snapshot.projection_policy.selected_collection_slugs
    )


def _reseal_with_caps(snapshot: CurationSnapshot, caps: OperationCaps) -> CurationSnapshot:
    mutation_policy = MutationPolicy(
        plan_expiry_hours=snapshot.mutation_policy.plan_expiry_hours,
        caps=caps,
    )
    semantic = _snapshot_semantic(
        profile_fingerprint=snapshot.profile_fingerprint,
        compiler_version=snapshot.compiler_version,
        compiled_at=snapshot.compiled_at,
        collections=snapshot.collection_definitions,
        projection_policy=snapshot.projection_policy,
        mutation_policy=mutation_policy,
        source_snapshots=snapshot.source_snapshots,
        entries=snapshot.entries,
        exclusions=snapshot.excluded_candidates,
        membership_map=snapshot.collection_membership_map,
        counts=snapshot.counts,
    )
    return snapshot.model_copy(
        update={
            "mutation_policy": mutation_policy,
            "curation_snapshot_id": short_id(semantic, prefix="cur"),
            "canonical_fingerprint": digest(semantic, prefix="curation"),
        }
    )


def test_additive_projection_is_deterministic_bounded_and_explicit() -> None:
    snapshot = _projection_snapshot()
    state = _github_state()

    first = build_projection_plan(
        snapshot,
        state,
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )
    second = build_projection_plan(
        snapshot,
        state,
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    projected_repositories = desired_projection_repositories(snapshot)
    selected = set(snapshot.projection_policy.selected_collection_slugs)
    expected_memberships = sum(
        entry.primary_disposition in PROJECTABLE_DISPOSITIONS
        and bool(selected.intersection(entry.collection_memberships))
        for entry in snapshot.entries
        for _ in selected.intersection(entry.collection_memberships)
    )
    expected_lists = len(selected)
    expected_repositories = len(projected_repositories)
    assert [item.kind for item in first.operations] == (
        ["create-list"] * expected_lists
        + ["star-repository"] * expected_repositories
        + ["add-membership"] * expected_memberships
    )
    assert first.operation_counts.model_dump() == {
        "create_lists": expected_lists,
        "star_repositories": expected_repositories,
        "add_memberships": expected_memberships,
        "total": expected_lists + expected_repositories + expected_memberships,
    }
    assert first.apply_ready is True
    assert first.mutation_state == "sealed-unapplied"
    assert first.forbidden_operation_classes == FORBIDDEN_OPERATION_CLASSES
    assert not {
        "unstar-repository",
        "delete-list",
        "rename-list",
        "remove-list-membership",
    }.intersection(item.kind for item in first.operations)


def test_projection_preserves_unrelated_memberships_and_replays_as_noop() -> None:
    snapshot = _projection_snapshot()
    repository = desired_projection_repositories(snapshot)[0]
    unrelated = GitHubListState(
        node_id="L_unrelated",
        name="My unrelated List",
        description="Existing user-authored organization.",
        is_private=True,
        slug="my-unrelated-list",
        members=(_member(repository),),
    )
    plan = build_projection_plan(
        snapshot,
        _github_state(lists=(unrelated,)),
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )
    repository_plan = next(
        item for item in plan.projected_repositories if item.repository == repository
    )
    membership = next(
        item
        for item in plan.operations
        if item.kind == "add-membership" and item.repository == repository
    )
    assert repository_plan.preserved_existing_list_ids == ("L_unrelated",)
    assert membership.preserved_list_ids == ("L_unrelated",)

    noop = build_projection_plan(
        snapshot,
        _github_state(starred=True, lists=_satisfied_lists()),
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )
    assert noop.operations == ()
    assert noop.operation_counts.total == 0
    assert noop.apply_ready is True


def test_missing_scope_seals_preview_but_never_marks_it_apply_ready() -> None:
    plan = build_projection_plan(
        _projection_snapshot(),
        _github_state(),
        _capability(GitHubCapabilityState.MISSING_SCOPE),
        account="pradeeptathineni",
        created_at=NOW,
    )
    assert plan.capability.state is GitHubCapabilityState.MISSING_SCOPE
    assert plan.apply_ready is False
    assert plan.capability.operator_command == "gh auth refresh --hostname github.com -s user"


@pytest.mark.parametrize(
    ("lists", "code"),
    [
        (
            (
                GitHubListState(
                    node_id="L1",
                    name="Generative AI & Agents",
                    description="wrong",
                    is_private=False,
                    slug="one",
                    members=(),
                ),
            ),
            "github_list_conflict",
        ),
        (
            (
                GitHubListState(
                    node_id="L1",
                    name="Same",
                    description="one",
                    is_private=False,
                    slug="one",
                    members=(),
                ),
                GitHubListState(
                    node_id="L2",
                    name="same",
                    description="two",
                    is_private=False,
                    slug="two",
                    members=(),
                ),
            ),
            "github_list_name_ambiguous",
        ),
        (
            (
                GitHubListState(
                    node_id="L1",
                    name="Future",
                    description="future",
                    is_private=False,
                    slug="future",
                    members=(),
                    unknown_item_types=("FutureListItem",),
                ),
            ),
            "github_preview_changed",
        ),
    ],
)
def test_list_conflicts_ambiguity_and_unknown_union_types_fail_closed(
    lists: tuple[GitHubListState, ...], code: str
) -> None:
    with pytest.raises(StateError) as raised:
        build_projection_plan(
            _projection_snapshot(),
            _github_state(lists=lists),
            _capability(),
            account="pradeeptathineni",
            created_at=NOW,
        )
    assert raised.value.code == code


@pytest.mark.parametrize(
    ("state", "code"),
    [
        (
            _github_state(private_repository="addyosmani/agent-skills"),
            "github_private_repository_blocked",
        ),
        (
            _github_state(archived_repository="addyosmani/agent-skills"),
            "github_archived_repository_blocked",
        ),
        (_github_state(extra_repository="fixture/extra"), "github_state_scope_mismatch"),
    ],
)
def test_private_archived_and_out_of_scope_repositories_block(
    state: GitHubCurationState, code: str
) -> None:
    with pytest.raises(StateError) as raised:
        build_projection_plan(
            _projection_snapshot(),
            state,
            _capability(),
            account="pradeeptathineni",
            created_at=NOW,
        )
    assert raised.value.code == code


def test_account_identity_cap_and_curation_drift_cannot_be_bypassed() -> None:
    snapshot = _projection_snapshot()
    with pytest.raises(StateError) as account:
        build_projection_plan(
            snapshot,
            _github_state(),
            _capability(),
            account="someone-else",
            created_at=NOW,
        )
    assert account.value.code == "github_account_mismatch"

    strict = _reseal_with_caps(
        snapshot,
        OperationCaps(total=1, create_lists=1, star_repositories=1, add_memberships=1),
    )
    with pytest.raises(StateError) as cap:
        build_projection_plan(
            strict,
            _github_state(),
            _capability(),
            account="pradeeptathineni",
            created_at=NOW,
        )
    assert cap.value.code == "github_operation_cap_exceeded"

    duplicated_map = dict(snapshot.collection_membership_map)
    selected = snapshot.projection_policy.selected_collection_slugs[0]
    duplicated_map[selected] = (*duplicated_map[selected], duplicated_map[selected][0])
    drifted = snapshot.model_copy(update={"collection_membership_map": duplicated_map})
    with pytest.raises(StateError) as drift:
        validate_curation_snapshot(drifted)
    assert drift.value.code == "curation_snapshot_inconsistent"


def test_plan_fingerprint_state_storage_and_human_renderings_are_coherent(
    tmp_path: Path,
) -> None:
    plan = build_projection_plan(
        _projection_snapshot(),
        _github_state(),
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )
    store = StateStore(tmp_path / "state")
    assert store.write_github_projection(plan) is True
    assert store.write_github_projection(plan) is False
    assert store.read_github_projection(plan.plan_id) == plan

    table = render(plan, OutputFormat.TABLE)
    markdown = render(plan, OutputFormat.MARKDOWN)
    assert plan.plan_id in table
    assert "create-list" in table
    assert "Intentionally forbidden" in markdown
    assert plan.canonical_plan_fingerprint in markdown

    payload = plan.model_dump(mode="json")
    payload["target_account"] = "tampered"
    with pytest.raises(ValidationError):
        GitHubProjectionPlan.model_validate(payload)

    stored_path = store.profile_root / "plans" / "github-curation" / f"{plan.plan_id}.json"
    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    assert stored["mutation_state"] == "sealed-unapplied"


def test_projected_service_reads_and_seals_without_any_mutation(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    snapshot = _projection_snapshot()
    store.write_curation(snapshot)
    client = ReadOnlyProjectionClient()

    plan = projected(
        store,
        curation_snapshot_id=snapshot.curation_snapshot_id,
        account="pradeeptathineni",
        github=client,
        planned_at=NOW,
    )

    assert plan.capability.state is GitHubCapabilityState.MISSING_SCOPE
    assert plan.apply_ready is False
    assert store.read_github_projection(plan.plan_id) == plan
    assert client.calls[:4] == [
        "auth-status",
        "api-version",
        "graphql-capability",
        "read-stars",
    ]
    assert client.calls.count("graphql-lists") == 1
    assert len([item for item in client.calls if item.startswith("read-repository:")]) == len(
        desired_projection_repositories(snapshot)
    )
    assert all("create" not in item and "update" not in item for item in client.calls)

    untouched = ReadOnlyProjectionClient()
    with pytest.raises(StateError) as mismatch:
        projected(
            store,
            curation_snapshot_id=snapshot.curation_snapshot_id,
            account="someone-else",
            github=untouched,
            planned_at=NOW,
        )
    assert mismatch.value.code == "github_account_mismatch"
    assert untouched.calls == []


def test_projected_cli_emits_the_sealed_machine_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "state"
    store = StateStore(state_root)
    snapshot = _projection_snapshot()
    store.write_curation(snapshot)
    client = ReadOnlyProjectionClient()
    monkeypatch.setattr("shoulda_used_that.services.GhClient", lambda: client)

    result = CliRunner().invoke(
        cli,
        [
            "--state-dir",
            str(state_root),
            "--format",
            "json",
            "projected",
            snapshot.curation_snapshot_id,
            "--to",
            "github-lists",
            "--account",
            "pradeeptathineni",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["plan_kind"] == "github-curation"
    assert payload["mutation_state"] == "sealed-unapplied"
    assert payload["capability"]["state"] == "missing_scope"


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "create-list"},
        {
            "kind": "create-list",
            "collection_slug": "one",
            "list_name": "One",
            "list_description": "Description",
            "repository": "a/b",
        },
        {"kind": "star-repository"},
        {
            "kind": "star-repository",
            "repository": "a/b",
            "repository_node_id": "R1",
            "list_name": "not-allowed",
        },
        {"kind": "add-membership", "repository": "a/b"},
    ],
)
def test_projection_operation_shapes_fail_closed(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        GitHubProjectionOperation.model_validate({"operation_id": "op_" + ("0" * 24), **payload})


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("expiry", "expiry"),
        ("counts", "counts"),
        ("forbidden", "forbidden"),
        ("apply-ready", "available"),
        ("id", "ID"),
    ],
)
def test_projection_plan_coherence_is_revalidated(mutation: str, message: str) -> None:
    plan = build_projection_plan(
        _projection_snapshot(),
        _github_state(),
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )
    payload = plan.model_dump(mode="json")
    if mutation == "expiry":
        payload["expires_at"] = payload["created_at"]
    elif mutation == "counts":
        payload["operation_counts"]["total"] = 0
    elif mutation == "forbidden":
        payload["forbidden_operation_classes"] = []
    elif mutation == "apply-ready":
        payload["capability"]["state"] = "missing_scope"
    else:
        payload["plan_id"] = "gcp_" + ("0" * 24)
    with pytest.raises(ValidationError, match=message):
        GitHubProjectionPlan.model_validate(payload)


def test_projection_identity_and_capability_mismatches_are_typed() -> None:
    snapshot = _projection_snapshot()
    state = _github_state()
    wrong_login = _capability().model_copy(update={"login": "someone-else"})
    with pytest.raises(StateError) as login:
        build_projection_plan(
            snapshot,
            state,
            wrong_login,
            account="pradeeptathineni",
            created_at=NOW,
        )
    assert login.value.code == "github_account_mismatch"

    wrong_node = _capability().model_copy(update={"node_id": "U_other"})
    with pytest.raises(StateError) as node:
        build_projection_plan(
            snapshot,
            state,
            wrong_node,
            account="pradeeptathineni",
            created_at=NOW,
        )
    assert node.value.code == "github_account_identity_mismatch"

    preview_changed = _capability().model_copy(
        update={"state": GitHubCapabilityState.PREVIEW_CHANGED}
    )
    with pytest.raises(StateError) as preview:
        build_projection_plan(
            snapshot,
            state,
            preview_changed,
            account="pradeeptathineni",
            created_at=NOW,
        )
    assert preview.value.code == "github_capability_unavailable"


def test_noop_and_missing_scope_human_renderings_are_actionable() -> None:
    snapshot = _projection_snapshot()
    noop = build_projection_plan(
        snapshot,
        _github_state(starred=True, lists=_satisfied_lists()),
        _capability(),
        account="pradeeptathineni",
        created_at=NOW,
    )
    assert "semantic-no-op" in render(noop, OutputFormat.TABLE)
    assert "semantic-no-op" in render(noop, OutputFormat.MARKDOWN)

    missing_scope = build_projection_plan(
        snapshot,
        _github_state(),
        _capability(GitHubCapabilityState.MISSING_SCOPE),
        account="pradeeptathineni",
        created_at=NOW,
    )
    assert "Operator action required: gh auth refresh" in render(missing_scope, OutputFormat.TABLE)
    assert "Operator action required" in render(missing_scope, OutputFormat.MARKDOWN)
