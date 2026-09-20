from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from shoulda_used_that.admin_services import applied, verified
from shoulda_used_that.errors import GitHubError, GitHubRateLimitError, StateError
from shoulda_used_that.github import GhAuthStatus, GhResult
from shoulda_used_that.github_apply import (
    ApplyOperationOutcome,
    ApplyStatus,
    VerifyStatus,
    assert_allowed_progress,
    make_operation_receipt,
    requested_membership_union,
)
from shoulda_used_that.github_lists import (
    GitHubCapabilityState,
    GitHubCurationState,
    GitHubListMember,
    GitHubListState,
    GitHubRelevantRepository,
)
from shoulda_used_that.github_mutations import (
    CreatedUserList,
    MembershipMutationResult,
)
from shoulda_used_that.projection import build_projection_plan
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.state import StateStore
from tests.test_projection import (
    NOW,
    _capability,
    _github_state,
    _node,
    _projection_snapshot,
)


class TickClock:
    def __init__(self, start: datetime = NOW + timedelta(minutes=1)) -> None:
        self.current = start

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        return value


class FixtureApplyClient:
    def __init__(self, baseline: GitHubCurationState) -> None:
        self.login = baseline.account
        self.node_id = baseline.account_node_id
        self.scopes = ("repo", "user")
        self.preview_exact = True
        self.repositories = {item.repository: item for item in baseline.relevant_repositories}
        self.lists = {item.node_id: item for item in baseline.lists}
        self.calls: list[tuple[str, Any]] = []
        self.mutation_count = 0
        self.fail_at: int | None = None
        self.failure: GitHubError = GitHubRateLimitError(
            "github_rate_limited", "fixture rate limit"
        )
        self.effect_before_failure = False
        self.suppress_effect_at: int | None = None
        self.membership_response_repository: str | None = None
        self.membership_response_list_ids: tuple[str, ...] | None = None

    def auth_status(self) -> GhAuthStatus:
        self.calls.append(("auth-status", None))
        return GhAuthStatus(
            self.login,
            "github.com",
            self.scopes,
            "fixture",
            "2.test",
        )

    def api_version_probe(self) -> GhResult:
        self.calls.append(("api-version", None))
        return _result({})

    def graphql(
        self,
        query: str,
        *,
        variables: dict[str, str] | None = None,
        maximum_output_bytes: int = 20 * 1024 * 1024,
    ) -> GhResult:
        del maximum_output_bytes
        if "userType:" in query:
            self.calls.append(("capability", None))
            possible_types = (
                [{"name": "Repository"}]
                if self.preview_exact
                else [{"name": "Repository"}, {"name": "FutureItem"}]
            )
            return _result(
                {
                    "data": {
                        "viewer": {"login": self.login, "id": self.node_id},
                        "userType": {"fields": [{"name": "lists"}]},
                        "itemType": {
                            "kind": "UNION",
                            "possibleTypes": possible_types,
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
                        "membershipInput": {
                            "inputFields": [
                                {"name": "itemId"},
                                {"name": "listIds"},
                            ]
                        },
                    }
                }
            )
        self.calls.append(("read-lists", variables or {}))
        nodes = [self._list_payload(item) for item in self.lists.values()]
        return _result(
            {
                "data": {
                    "viewer": {
                        "login": self.login,
                        "id": self.node_id,
                        "lists": {
                            "totalCount": len(nodes),
                            "nodes": nodes,
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                        },
                    }
                }
            }
        )

    def starred(self) -> GhResult:
        self.calls.append(("read-stars", None))
        return _result(
            [
                {
                    "starred_at": "2026-09-17T12:01:00Z",
                    "repo": self._rest_repository(item),
                }
                for item in self.repositories.values()
                if item.starred
            ]
        )

    def user_starred(self, login: str) -> GhResult:
        raise AssertionError(f"unexpected public-star read for {login}")

    def repository(self, repository: str) -> GhResult:
        self.calls.append(("read-repository", repository))
        return _result(self._rest_repository(self.repositories[repository]))

    def create_user_list(
        self,
        *,
        name: str,
        description: str,
        client_mutation_id: str,
    ) -> CreatedUserList:
        node_id = f"L{1 + len(self.lists)}"

        def effect() -> None:
            self.lists[node_id] = GitHubListState(
                node_id=node_id,
                name=name,
                description=description,
                is_private=False,
                slug=name.casefold().replace(" ", "-").replace("&", "and"),
                members=(),
            )

        self._mutation("create-list", (name, description, client_mutation_id), effect)
        return CreatedUserList(
            node_id=node_id,
            name=name,
            description=description,
            is_private=False,
            slug=name.casefold().replace(" ", "-"),
            client_mutation_id=client_mutation_id,
        )

    def star_repository(self, repository: str) -> None:
        def effect() -> None:
            current = self.repositories[repository]
            self.repositories[repository] = current.model_copy(
                update={"starred": True, "starred_at": NOW + timedelta(minutes=1)}
            )

        self._mutation("star-repository", repository, effect)

    def update_user_lists_for_item(
        self,
        *,
        repository_node_id: str,
        list_ids: tuple[str, ...],
        client_mutation_id: str,
    ) -> MembershipMutationResult:
        repository = next(
            item for item in self.repositories.values() if item.node_id == repository_node_id
        )

        def effect() -> None:
            member = GitHubListMember(
                node_id=repository.node_id,
                repository=repository.repository,
                is_private=repository.is_private,
                is_archived=repository.is_archived,
                url=repository.url,
            )
            for node_id, github_list in tuple(self.lists.items()):
                members = {
                    item.node_id: item
                    for item in github_list.members
                    if item.node_id != repository_node_id
                }
                if node_id in list_ids:
                    members[repository_node_id] = member
                self.lists[node_id] = github_list.model_copy(
                    update={"members": tuple(members[key] for key in sorted(members))}
                )

        self._mutation(
            "add-membership",
            (repository.repository, list_ids, client_mutation_id),
            effect,
        )
        return MembershipMutationResult(
            repository_node_id=repository_node_id,
            repository=self.membership_response_repository or repository.repository,
            list_ids=self.membership_response_list_ids or tuple(sorted(list_ids)),
            client_mutation_id=client_mutation_id,
        )

    def _mutation(self, kind: str, detail: Any, effect: Callable[[], None]) -> None:
        self.mutation_count += 1
        index = self.mutation_count
        self.calls.append((kind, detail))
        if self.fail_at == index:
            self.fail_at = None
            if self.effect_before_failure:
                effect()
            raise self.failure
        if self.suppress_effect_at != index:
            effect()

    @staticmethod
    def _rest_repository(item: GitHubRelevantRepository) -> dict[str, Any]:
        return {
            "node_id": item.node_id,
            "full_name": item.repository,
            "private": item.is_private,
            "archived": item.is_archived,
            "html_url": item.url,
        }

    @staticmethod
    def _list_payload(item: GitHubListState) -> dict[str, Any]:
        return {
            "id": item.node_id,
            "name": item.name,
            "description": item.description,
            "isPrivate": item.is_private,
            "slug": item.slug,
            "items": {
                "totalCount": len(item.members),
                "nodes": [
                    {
                        "__typename": "Repository",
                        "id": member.node_id,
                        "nameWithOwner": member.repository,
                        "isPrivate": member.is_private,
                        "isArchived": member.is_archived,
                        "url": member.url,
                    }
                    for member in item.members
                ],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            },
        }


def _result(payload: Any) -> GhResult:
    return GhResult(payload, "2.test", "fixture", False)


def _sealed_store(
    tmp_path: Path,
    *,
    baseline: GitHubCurationState | None = None,
    capability_state: GitHubCapabilityState = GitHubCapabilityState.AVAILABLE,
) -> tuple[StateStore, Any, GitHubCurationState]:
    source_state = baseline or _github_state()
    snapshot = _projection_snapshot()
    plan = build_projection_plan(
        snapshot,
        source_state,
        _capability(capability_state),
        account="pradeeptathineni",
        created_at=NOW,
    )
    store = StateStore(tmp_path / "state")
    store.write_github_state(source_state)
    store.write_github_projection(plan)
    return store, plan, source_state


def _mutation_kinds(client: FixtureApplyClient) -> list[str]:
    return [
        kind
        for kind, _ in client.calls
        if kind in {"create-list", "star-repository", "add-membership"}
    ]


def test_apply_then_verify_full_readback_and_idempotent_replay(tmp_path: Path) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)

    receipt = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )

    assert receipt.status is ApplyStatus.COMPLETE
    assert len(receipt.operation_receipts) == plan.operation_counts.total
    assert _mutation_kinds(client) == [item.kind for item in plan.operations]
    assert all(
        item.outcome is ApplyOperationOutcome.SUCCEEDED for item in receipt.operation_receipts
    )
    assert store.read_apply(receipt.apply_receipt_id) == receipt

    verification = verified(
        store,
        apply_receipt_id=receipt.apply_receipt_id,
        github=client,
        verified_at=NOW + timedelta(minutes=10),
    )
    assert verification.status is VerifyStatus.VERIFIED
    assert verification.mismatches == ()
    assert verification.observed_login == "pradeeptathineni"
    assert verification.observed_account_node_id == "U_owner"
    assert all(item.state.value == "verified" for item in verification.postconditions)
    assert store.read_verify(verification.verify_receipt_id) == verification
    assert sum(kind == "read-stars" for kind, _ in client.calls) == 5
    assert sum(kind == "read-lists" for kind, _ in client.calls) == 5

    for output_format in (OutputFormat.TABLE, OutputFormat.MARKDOWN):
        apply_output = render(receipt, output_format)
        verify_output = render(verification, output_format)
        assert receipt.apply_receipt_id in apply_output
        assert receipt.status.value in apply_output
        assert verification.verify_receipt_id in verify_output
        assert verification.status.value in verify_output

    tampered_verification = verification.model_dump(mode="json")
    tampered_verification["observed_login"] = "different-account"
    with pytest.raises(ValidationError, match="fresh observed identity"):
        type(verification).model_validate(tampered_verification)

    mutation_count = len(_mutation_kinds(client))
    replay = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(NOW + timedelta(minutes=20)),
    )
    assert replay == receipt
    assert len(_mutation_kinds(client)) == mutation_count


@pytest.mark.parametrize("environment", [{"CI": "true"}, {"GITHUB_ACTIONS": "false"}])
def test_apply_refuses_ci_before_any_live_call(tmp_path: Path, environment: dict[str, str]) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)
    with pytest.raises(StateError) as raised:
        applied(
            store,
            plan_id=plan.plan_id,
            fingerprint=plan.canonical_plan_fingerprint,
            github=client,
            environment=environment,
            stdin_isatty=True,
            clock=TickClock(),
        )
    assert raised.value.code == "github_apply_ci_refused"
    assert client.calls == []


def test_apply_refuses_non_tty_fingerprint_expiry_and_nonready_plan(
    tmp_path: Path,
) -> None:
    store, plan, baseline = _sealed_store(tmp_path / "normal")
    client = FixtureApplyClient(baseline)
    with pytest.raises(StateError) as fingerprint:
        applied(
            store,
            plan_id=plan.plan_id,
            fingerprint="plan_" + ("0" * 64),
            github=client,
            environment={},
            stdin_isatty=True,
            clock=TickClock(),
        )
    assert fingerprint.value.code == "github_plan_fingerprint_mismatch"
    with pytest.raises(StateError) as tty:
        applied(
            store,
            plan_id=plan.plan_id,
            fingerprint=plan.canonical_plan_fingerprint,
            github=client,
            environment={},
            stdin_isatty=False,
            clock=TickClock(),
        )
    assert tty.value.code == "github_apply_tty_required"
    with pytest.raises(StateError) as expired:
        applied(
            store,
            plan_id=plan.plan_id,
            fingerprint=plan.canonical_plan_fingerprint,
            github=client,
            environment={},
            stdin_isatty=True,
            clock=TickClock(NOW + timedelta(days=2)),
        )
    assert expired.value.code == "github_plan_expired"

    missing_store, missing_plan, missing_baseline = _sealed_store(
        tmp_path / "missing",
        capability_state=GitHubCapabilityState.MISSING_SCOPE,
    )
    with pytest.raises(StateError) as not_ready:
        applied(
            missing_store,
            plan_id=missing_plan.plan_id,
            fingerprint=missing_plan.canonical_plan_fingerprint,
            github=FixtureApplyClient(missing_baseline),
            environment={},
            stdin_isatty=True,
            clock=TickClock(),
        )
    assert not_ready.value.code == "github_plan_not_apply_ready"
    assert client.calls == []


def test_capability_and_material_drift_block_before_mutation(tmp_path: Path) -> None:
    store, plan, baseline = _sealed_store(tmp_path / "capability")
    unavailable = FixtureApplyClient(baseline)
    unavailable.preview_exact = False
    with pytest.raises(StateError) as capability:
        applied(
            store,
            plan_id=plan.plan_id,
            fingerprint=plan.canonical_plan_fingerprint,
            github=unavailable,
            environment={},
            stdin_isatty=True,
            clock=TickClock(),
        )
    assert capability.value.code == "github_apply_capability_unavailable"
    assert _mutation_kinds(unavailable) == []

    drift_store, drift_plan, drift_baseline = _sealed_store(tmp_path / "drift")
    drifted = FixtureApplyClient(drift_baseline)
    drifted.lists["L_unplanned"] = GitHubListState(
        node_id="L_unplanned",
        name="User change",
        description="Created after planning",
        is_private=False,
        slug="user-change",
        members=(),
    )
    with pytest.raises(StateError) as drift:
        applied(
            drift_store,
            plan_id=drift_plan.plan_id,
            fingerprint=drift_plan.canonical_plan_fingerprint,
            github=drifted,
            environment={},
            stdin_isatty=True,
            clock=TickClock(),
        )
    assert drift.value.code == "github_apply_unplanned_drift"
    assert _mutation_kinds(drifted) == []


@pytest.mark.parametrize("failure_at", [1, 2, 5, 10])
def test_partial_failures_resume_without_duplicate_effects(tmp_path: Path, failure_at: int) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)
    client.fail_at = failure_at

    partial = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )
    assert partial.status in {ApplyStatus.FAILED, ApplyStatus.PARTIAL}
    assert partial.failure_code == "github_rate_limited"
    before_resume = list(_mutation_kinds(client))

    complete = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(NOW + timedelta(minutes=20)),
    )
    assert complete.status is ApplyStatus.COMPLETE
    if failure_at == 2:
        assert _mutation_kinds(client).count("create-list") == (
            plan.operation_counts.create_lists + 1
        )
    assert len(client.lists) == len(plan.projected_lists)
    assert all(item.starred for item in client.repositories.values())
    assert len(_mutation_kinds(client)) > len(before_resume)


def test_timeout_after_effect_reconciles_and_timeout_without_effect_blocks_retry(
    tmp_path: Path,
) -> None:
    store, plan, baseline = _sealed_store(tmp_path / "effect")
    client = FixtureApplyClient(baseline)
    client.fail_at = 1
    client.failure = GitHubError("github_timeout", "uncertain timeout")
    client.effect_before_failure = True
    partial = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )
    assert partial.status is ApplyStatus.PARTIAL
    assert partial.operation_receipts[-1].outcome is ApplyOperationOutcome.INDETERMINATE
    assert len(client.lists) == 1
    complete = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(NOW + timedelta(minutes=20)),
    )
    assert complete.status is ApplyStatus.COMPLETE
    assert len(client.lists) == len(plan.projected_lists)

    blocked_store, blocked_plan, blocked_baseline = _sealed_store(tmp_path / "blocked")
    blocked = FixtureApplyClient(blocked_baseline)
    blocked.fail_at = 1
    blocked.failure = GitHubError("github_timeout", "uncertain timeout")
    first = applied(
        blocked_store,
        plan_id=blocked_plan.plan_id,
        fingerprint=blocked_plan.canonical_plan_fingerprint,
        github=blocked,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )
    assert first.status is ApplyStatus.PARTIAL
    with pytest.raises(StateError) as uncertain:
        applied(
            blocked_store,
            plan_id=blocked_plan.plan_id,
            fingerprint=blocked_plan.canonical_plan_fingerprint,
            github=blocked,
            environment={},
            stdin_isatty=True,
            clock=TickClock(NOW + timedelta(minutes=20)),
        )
    assert uncertain.value.code == "github_indeterminate_create_requires_reconciliation"
    assert _mutation_kinds(blocked) == ["create-list"]


@pytest.mark.parametrize(
    "error_code",
    [
        "github_response_too_large",
        "github_graphql_error",
        "github_mutation_response_too_large",
    ],
)
def test_ambiguous_post_write_responses_are_indeterminate(tmp_path: Path, error_code: str) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)
    client.fail_at = 1
    client.failure = GitHubError(error_code, "ambiguous response after write")

    receipt = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )

    assert receipt.status is ApplyStatus.PARTIAL
    assert receipt.operation_receipts[-1].outcome is ApplyOperationOutcome.INDETERMINATE


@pytest.mark.parametrize("response_drift", ["repository", "list-union"])
def test_membership_response_identity_and_union_are_revalidated(
    tmp_path: Path, response_drift: str
) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)
    if response_drift == "repository":
        client.membership_response_repository = "different/repository"
    else:
        client.membership_response_list_ids = ("L_unknown",)

    receipt = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )

    assert receipt.status is ApplyStatus.PARTIAL
    assert receipt.failure_code == "github_mutation_postcondition_mismatch"
    assert receipt.operation_receipts[-1].request_kind == "add-membership"
    assert receipt.operation_receipts[-1].outcome is ApplyOperationOutcome.INDETERMINATE


def test_success_without_readback_is_partial_and_create_retry_is_refused(
    tmp_path: Path,
) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)
    client.suppress_effect_at = 1
    receipt = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )
    assert receipt.status is ApplyStatus.PARTIAL
    assert receipt.failure_code == "github_apply_readback_mismatch"
    with pytest.raises(StateError) as retry:
        applied(
            store,
            plan_id=plan.plan_id,
            fingerprint=plan.canonical_plan_fingerprint,
            github=client,
            environment={},
            stdin_isatty=True,
            clock=TickClock(NOW + timedelta(minutes=20)),
        )
    assert retry.value.code == "github_indeterminate_create_requires_reconciliation"


def test_membership_union_preserves_unrelated_private_list(tmp_path: Path) -> None:
    repository = "addyosmani/agent-skills"
    unrelated = GitHubListState(
        node_id="L_private",
        name="Private notes",
        description="Unrelated user state",
        is_private=True,
        slug="private-notes",
        members=(
            GitHubListMember(
                node_id=_node(repository),
                repository=repository,
                is_private=False,
                is_archived=False,
                url=f"https://github.com/{repository}",
            ),
        ),
    )
    baseline = _github_state(lists=(unrelated,))
    store, plan, _ = _sealed_store(tmp_path, baseline=baseline)
    client = FixtureApplyClient(baseline)
    receipt = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )
    assert receipt.status is ApplyStatus.COMPLETE
    membership_call = next(
        detail
        for kind, detail in client.calls
        if kind == "add-membership" and detail[0] == repository
    )
    assert "L_private" in membership_call[1]
    assert _node(repository) in {item.node_id for item in client.lists["L_private"].members}


def test_verification_reports_mismatch_and_unavailable_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    client = FixtureApplyClient(baseline)
    receipt = applied(
        store,
        plan_id=plan.plan_id,
        fingerprint=plan.canonical_plan_fingerprint,
        github=client,
        environment={},
        stdin_isatty=True,
        clock=TickClock(),
    )
    first_repository = next(iter(client.repositories))
    client.repositories[first_repository] = client.repositories[first_repository].model_copy(
        update={"starred": False, "starred_at": None}
    )
    failed = verified(
        store,
        apply_receipt_id=receipt.apply_receipt_id,
        github=client,
        verified_at=NOW + timedelta(minutes=10),
    )
    assert failed.status is VerifyStatus.FAILED
    assert first_repository in failed.mismatches

    client.preview_exact = False
    partial = verified(
        store,
        apply_receipt_id=receipt.apply_receipt_id,
        github=client,
        verified_at=NOW + timedelta(minutes=11),
    )
    assert partial.status is VerifyStatus.PARTIAL
    assert partial.postconditions[0].state.value == "unavailable"
    assert len(partial.postconditions) == len(failed.postconditions)
    assert all(
        condition.actual is None
        for condition in partial.postconditions
        if condition.kind not in {"capability", "target-identity"}
    )

    client.preview_exact = True
    client.node_id = "U_other"
    identity_failed = verified(
        store,
        apply_receipt_id=receipt.apply_receipt_id,
        github=client,
        verified_at=NOW + timedelta(minutes=12),
    )
    assert identity_failed.status is VerifyStatus.FAILED
    assert identity_failed.observed_login == "pradeeptathineni"
    assert identity_failed.observed_account_node_id == "U_other"
    assert any(
        item.kind == "target-identity" and item.state.value == "mismatch"
        for item in identity_failed.postconditions
    )
    assert any(item.state.value == "unavailable" for item in identity_failed.postconditions)

    client.node_id = "U_owner"

    def unavailable_stars() -> GhResult:
        raise GitHubError("github_transport_failed", "fixture readback unavailable")

    monkeypatch.setattr(client, "starred", unavailable_stars)
    readback_partial = verified(
        store,
        apply_receipt_id=receipt.apply_receipt_id,
        github=client,
        verified_at=NOW + timedelta(minutes=13),
    )
    assert readback_partial.status is VerifyStatus.PARTIAL
    assert readback_partial.observed_account_node_id == "U_owner"
    assert readback_partial.postconditions[0].state.value == "verified"
    assert all(
        item.state.value == "unavailable"
        for item in readback_partial.postconditions
        if item.kind not in {"capability", "target-identity"}
    )


def test_receipt_fingerprints_and_transition_guards_fail_closed(tmp_path: Path) -> None:
    store, plan, baseline = _sealed_store(tmp_path)
    operation = plan.operations[0]
    receipt = make_operation_receipt(
        plan,
        operation,
        attempt=1,
        started_at=NOW,
        completed_at=NOW,
        outcome=ApplyOperationOutcome.SUCCEEDED,
    )
    payload = receipt.model_dump(mode="json")
    payload["attempt"] = 2
    with pytest.raises(ValidationError):
        type(receipt).model_validate(payload)

    current = baseline.model_copy(
        update={
            "relevant_repositories": tuple(
                item.model_copy(update={"starred": False, "starred_at": None})
                for item in baseline.relevant_repositories
            )
        }
    )
    assert_allowed_progress(plan, baseline, current)
    with pytest.raises(ValueError, match="membership union"):
        requested_membership_union(operation, plan, baseline)

    assert store.latest_apply(plan.plan_id) is None
