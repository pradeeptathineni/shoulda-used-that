"""Typed additive GitHub apply receipts and pure readback reconciliation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.errors import StateError
from shoulda_used_that.github_lists import GitHubCurationState, GitHubListState
from shoulda_used_that.models import FrozenModel
from shoulda_used_that.projection import GitHubProjectionOperation, GitHubProjectionPlan

APPLY_SCHEMA_VERSION: Literal["2.0"] = "2.0"


class ApplyOperationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


class ApplyStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class VerifyConditionState(StrEnum):
    VERIFIED = "verified"
    MISMATCH = "mismatch"
    UNAVAILABLE = "unavailable"


class VerifyStatus(StrEnum):
    VERIFIED = "verified"
    PARTIAL = "partial"
    FAILED = "failed"


class ApplyOperationReceipt(FrozenModel):
    schema_version: Literal["2.0"] = APPLY_SCHEMA_VERSION
    operation_receipt_id: str = Field(pattern=r"^apo_[0-9a-f]{24}$")
    plan_id: str = Field(pattern=r"^gcp_[0-9a-f]{24}$")
    operation_id: str = Field(pattern=r"^op_[0-9a-f]{24}$")
    request_kind: Literal["create-list", "star-repository", "add-membership"]
    client_mutation_id: str = Field(pattern=r"^cmid_[0-9a-f]{24}$")
    attempt: int = Field(ge=1)
    started_at: datetime
    completed_at: datetime
    outcome: ApplyOperationOutcome
    requested_list_ids: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = Field(default=None, max_length=500)
    readback_satisfied: bool | None = None
    canonical_fingerprint: str = Field(pattern=r"^applyop_[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_coherent(self) -> ApplyOperationReceipt:
        if self.completed_at < self.started_at:
            raise ValueError("operation completion cannot precede its start")
        if self.outcome is ApplyOperationOutcome.SUCCEEDED and self.error_code:
            raise ValueError("a successful operation cannot carry an error")
        if self.outcome is not ApplyOperationOutcome.SUCCEEDED and not self.error_code:
            raise ValueError("a failed or indeterminate operation requires an error code")
        semantic = self.model_dump(
            mode="json", exclude={"operation_receipt_id", "canonical_fingerprint"}
        )
        if self.canonical_fingerprint != digest(semantic, prefix="applyop"):
            raise ValueError("operation receipt fingerprint does not match its content")
        if self.operation_receipt_id != short_id(semantic, prefix="apo"):
            raise ValueError("operation receipt ID does not match its content")
        return self


class ApplyReceipt(FrozenModel):
    schema_version: Literal["2.0"] = APPLY_SCHEMA_VERSION
    apply_receipt_id: str = Field(pattern=r"^app_[0-9a-f]{24}$")
    plan_id: str = Field(pattern=r"^gcp_[0-9a-f]{24}$")
    plan_fingerprint: str = Field(pattern=r"^plan_[0-9a-f]{64}$")
    target_login: str
    started_at: datetime
    completed_at: datetime
    before_state_fingerprint: str = Field(pattern=r"^github_[0-9a-f]{64}$")
    operation_receipts: tuple[ApplyOperationReceipt, ...]
    status: ApplyStatus
    resume_cursor: str | None = None
    failure_code: str | None = None
    readback_state_fingerprint: str | None = Field(default=None, pattern=r"^github_[0-9a-f]{64}$")
    readback_snapshot_reference: str | None = Field(default=None, pattern=r"^github_[0-9a-f]{64}$")
    canonical_fingerprint: str = Field(pattern=r"^apply_[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_coherent(self) -> ApplyReceipt:
        if self.completed_at < self.started_at:
            raise ValueError("apply completion cannot precede its start")
        if any(item.plan_id != self.plan_id for item in self.operation_receipts):
            raise ValueError("every operation receipt must belong to the apply plan")
        if self.status is ApplyStatus.COMPLETE:
            if self.resume_cursor or self.failure_code or not self.readback_state_fingerprint:
                raise ValueError("complete apply receipt has partial-state fields")
        elif not self.resume_cursor or not self.failure_code:
            raise ValueError("incomplete apply receipt requires a cursor and failure code")
        if self.readback_state_fingerprint != self.readback_snapshot_reference:
            raise ValueError("readback fingerprint and snapshot reference must agree")
        semantic = self.model_dump(
            mode="json", exclude={"apply_receipt_id", "canonical_fingerprint"}
        )
        if self.canonical_fingerprint != digest(semantic, prefix="apply"):
            raise ValueError("apply receipt fingerprint does not match its content")
        if self.apply_receipt_id != short_id(semantic, prefix="app"):
            raise ValueError("apply receipt ID does not match its content")
        return self


class VerifyPostcondition(FrozenModel):
    kind: Literal[
        "target-identity",
        "target-state-integrity",
        "public-list",
        "star",
        "membership",
        "preserved-membership",
        "capability",
    ]
    subject: str
    expected: str
    actual: str | None = None
    state: VerifyConditionState
    error_code: str | None = None


class VerifyReceipt(FrozenModel):
    schema_version: Literal["2.0"] = APPLY_SCHEMA_VERSION
    verify_receipt_id: str = Field(pattern=r"^vfy_[0-9a-f]{24}$")
    apply_receipt_id: str = Field(pattern=r"^app_[0-9a-f]{24}$")
    apply_fingerprint: str = Field(pattern=r"^apply_[0-9a-f]{64}$")
    plan_id: str = Field(pattern=r"^gcp_[0-9a-f]{24}$")
    target_login: str
    observed_login: str | None
    observed_account_node_id: str | None
    verified_at: datetime
    observed_state_fingerprint: str | None = Field(default=None, pattern=r"^github_[0-9a-f]{64}$")
    postconditions: tuple[VerifyPostcondition, ...]
    mismatches: tuple[str, ...]
    status: VerifyStatus
    canonical_fingerprint: str = Field(pattern=r"^verify_[0-9a-f]{64}$")

    @model_validator(mode="after")
    def receipt_is_coherent(self) -> VerifyReceipt:
        identity_conditions = tuple(
            item for item in self.postconditions if item.kind == "target-identity"
        )
        if len(identity_conditions) != 1:
            raise ValueError("verify receipt requires exactly one target identity postcondition")
        identity = identity_conditions[0]
        if identity.state is VerifyConditionState.VERIFIED and (
            self.observed_login is None
            or self.observed_account_node_id is None
            or self.observed_login.casefold() != self.target_login.casefold()
            or identity.actual != self.observed_account_node_id
        ):
            raise ValueError("verified target identity does not match fresh observed identity")
        if self.observed_state_fingerprint is not None and (
            self.observed_login is None or self.observed_account_node_id is None
        ):
            raise ValueError("an observed state requires a fresh target identity")
        expected_mismatches = tuple(
            item.subject
            for item in self.postconditions
            if item.state is VerifyConditionState.MISMATCH
        )
        if self.mismatches != expected_mismatches:
            raise ValueError("verify mismatch index does not match postconditions")
        expected_status = _verify_status(self.postconditions)
        if self.status is not expected_status:
            raise ValueError("verify status does not match postconditions")
        semantic = self.model_dump(
            mode="json", exclude={"verify_receipt_id", "canonical_fingerprint"}
        )
        if self.canonical_fingerprint != digest(semantic, prefix="verify"):
            raise ValueError("verify receipt fingerprint does not match its content")
        if self.verify_receipt_id != short_id(semantic, prefix="vfy"):
            raise ValueError("verify receipt ID does not match its content")
        return self


def client_mutation_id(plan: GitHubProjectionPlan, operation_id: str) -> str:
    """Return a stable audit/client ID for one sealed operation across retries."""

    return short_id(
        {
            "plan_id": plan.plan_id,
            "plan_fingerprint": plan.canonical_plan_fingerprint,
            "operation_id": operation_id,
        },
        prefix="cmid",
    )


def make_operation_receipt(
    plan: GitHubProjectionPlan,
    operation: GitHubProjectionOperation,
    *,
    attempt: int,
    started_at: datetime,
    completed_at: datetime,
    outcome: ApplyOperationOutcome,
    requested_list_ids: tuple[str, ...] = (),
    error_code: str | None = None,
    error_message: str | None = None,
    readback_satisfied: bool | None = None,
) -> ApplyOperationReceipt:
    semantic = {
        "schema_version": APPLY_SCHEMA_VERSION,
        "plan_id": plan.plan_id,
        "operation_id": operation.operation_id,
        "request_kind": operation.kind,
        "client_mutation_id": client_mutation_id(plan, operation.operation_id),
        "attempt": attempt,
        "started_at": _json_timestamp(started_at),
        "completed_at": _json_timestamp(completed_at),
        "outcome": outcome.value,
        "requested_list_ids": list(requested_list_ids),
        "error_code": error_code,
        "error_message": error_message,
        "readback_satisfied": readback_satisfied,
    }
    return ApplyOperationReceipt(
        operation_receipt_id=short_id(semantic, prefix="apo"),
        plan_id=plan.plan_id,
        operation_id=operation.operation_id,
        request_kind=operation.kind,
        client_mutation_id=client_mutation_id(plan, operation.operation_id),
        attempt=attempt,
        started_at=started_at,
        completed_at=completed_at,
        outcome=outcome,
        requested_list_ids=requested_list_ids,
        error_code=error_code,
        error_message=error_message,
        readback_satisfied=readback_satisfied,
        canonical_fingerprint=digest(semantic, prefix="applyop"),
    )


def make_apply_receipt(
    plan: GitHubProjectionPlan,
    *,
    started_at: datetime,
    completed_at: datetime,
    before_state_fingerprint: str,
    operation_receipts: tuple[ApplyOperationReceipt, ...],
    status: ApplyStatus,
    resume_cursor: str | None,
    failure_code: str | None,
    readback_state_fingerprint: str | None,
) -> ApplyReceipt:
    semantic = {
        "schema_version": APPLY_SCHEMA_VERSION,
        "plan_id": plan.plan_id,
        "plan_fingerprint": plan.canonical_plan_fingerprint,
        "target_login": plan.target_account,
        "started_at": _json_timestamp(started_at),
        "completed_at": _json_timestamp(completed_at),
        "before_state_fingerprint": before_state_fingerprint,
        "operation_receipts": [item.model_dump(mode="json") for item in operation_receipts],
        "status": status.value,
        "resume_cursor": resume_cursor,
        "failure_code": failure_code,
        "readback_state_fingerprint": readback_state_fingerprint,
        "readback_snapshot_reference": readback_state_fingerprint,
    }
    return ApplyReceipt(
        apply_receipt_id=short_id(semantic, prefix="app"),
        plan_id=plan.plan_id,
        plan_fingerprint=plan.canonical_plan_fingerprint,
        target_login=plan.target_account,
        started_at=started_at,
        completed_at=completed_at,
        before_state_fingerprint=before_state_fingerprint,
        operation_receipts=operation_receipts,
        status=status,
        resume_cursor=resume_cursor,
        failure_code=failure_code,
        readback_state_fingerprint=readback_state_fingerprint,
        readback_snapshot_reference=readback_state_fingerprint,
        canonical_fingerprint=digest(semantic, prefix="apply"),
    )


def make_verify_receipt(
    apply_receipt: ApplyReceipt,
    *,
    verified_at: datetime,
    observed_login: str | None,
    observed_account_node_id: str | None,
    observed_state_fingerprint: str | None,
    postconditions: tuple[VerifyPostcondition, ...],
) -> VerifyReceipt:
    mismatches = tuple(
        item.subject for item in postconditions if item.state is VerifyConditionState.MISMATCH
    )
    status = _verify_status(postconditions)
    semantic = {
        "schema_version": APPLY_SCHEMA_VERSION,
        "apply_receipt_id": apply_receipt.apply_receipt_id,
        "apply_fingerprint": apply_receipt.canonical_fingerprint,
        "plan_id": apply_receipt.plan_id,
        "target_login": apply_receipt.target_login,
        "observed_login": observed_login,
        "observed_account_node_id": observed_account_node_id,
        "verified_at": _json_timestamp(verified_at),
        "observed_state_fingerprint": observed_state_fingerprint,
        "postconditions": [item.model_dump(mode="json") for item in postconditions],
        "mismatches": list(mismatches),
        "status": status.value,
    }
    return VerifyReceipt(
        verify_receipt_id=short_id(semantic, prefix="vfy"),
        apply_receipt_id=apply_receipt.apply_receipt_id,
        apply_fingerprint=apply_receipt.canonical_fingerprint,
        plan_id=apply_receipt.plan_id,
        target_login=apply_receipt.target_login,
        observed_login=observed_login,
        observed_account_node_id=observed_account_node_id,
        verified_at=verified_at,
        observed_state_fingerprint=observed_state_fingerprint,
        postconditions=postconditions,
        mismatches=mismatches,
        status=status,
        canonical_fingerprint=digest(semantic, prefix="verify"),
    )


def assert_allowed_progress(
    plan: GitHubProjectionPlan,
    baseline: GitHubCurationState,
    current: GitHubCurationState,
) -> None:
    """Reject every state change except a subset of the plan's additive effects."""

    if (
        baseline.account != current.account
        or baseline.account_node_id != current.account_node_id
        or current.account.casefold() != plan.target_account.casefold()
    ):
        raise StateError(
            code="github_apply_identity_drift",
            message="GitHub target identity changed after the plan was sealed.",
        )
    baseline_repositories = {item.repository: item for item in baseline.relevant_repositories}
    current_repositories = {item.repository: item for item in current.relevant_repositories}
    if set(baseline_repositories) != set(current_repositories):
        raise StateError(
            code="github_apply_repository_drift",
            message="The plan's relevant repository set changed.",
        )
    star_operations = {
        item.repository for item in plan.operations if item.kind == "star-repository"
    }
    for repository, before_repository in baseline_repositories.items():
        after_repository = current_repositories[repository]
        immutable_before = before_repository.model_dump(
            mode="json", exclude={"starred", "starred_at"}
        )
        immutable_after = after_repository.model_dump(
            mode="json", exclude={"starred", "starred_at"}
        )
        if immutable_before != immutable_after:
            raise StateError(
                code="github_apply_repository_drift",
                message=f"Repository identity or safety fields changed for {repository}.",
            )
        if before_repository.starred and not after_repository.starred:
            raise StateError(
                code="github_apply_destructive_drift",
                message=f"Previously starred repository {repository} is no longer starred.",
            )
        if (
            not before_repository.starred
            and after_repository.starred
            and repository not in star_operations
        ):
            raise StateError(
                code="github_apply_unplanned_drift",
                message=f"Repository {repository} changed outside the sealed star operations.",
            )

    baseline_lists = {item.node_id: item for item in baseline.lists}
    current_lists = {item.node_id: item for item in current.lists}
    projected_by_name = {item.name.casefold(): item for item in plan.projected_lists}
    for node_id, before_list in baseline_lists.items():
        after_list = current_lists.get(node_id)
        if after_list is None:
            raise StateError(
                code="github_apply_destructive_drift",
                message=f"Existing GitHub List {before_list.name!r} disappeared.",
            )
        if _list_metadata(before_list) != _list_metadata(after_list):
            raise StateError(
                code="github_apply_list_drift",
                message=f"Existing GitHub List {before_list.name!r} changed metadata.",
            )
    for node_id, current_list in current_lists.items():
        if node_id in baseline_lists:
            continue
        projected_list = projected_by_name.get(current_list.name.casefold())
        if (
            projected_list is None
            or projected_list.existing_node_id is not None
            or current_list.is_private
            or (current_list.description or "") != projected_list.description
        ):
            raise StateError(
                code="github_apply_unplanned_drift",
                message=f"Unplanned GitHub List {current_list.name!r} appeared.",
            )

    target_lists = _target_lists(plan, current.lists, fail_on_missing=False)
    allowed_members: dict[str, set[str]] = {}
    repository_nodes = {item.repository: item.node_id for item in current.relevant_repositories}
    for projected_repository in plan.projected_repositories:
        for slug in projected_repository.desired_collection_slugs:
            target = target_lists.get(slug)
            if target is not None:
                allowed_members.setdefault(target.node_id, set()).add(
                    repository_nodes[projected_repository.repository]
                )
    for node_id, observed_list in current_lists.items():
        if observed_list.unknown_item_types:
            raise StateError(
                code="github_preview_changed",
                message="GitHub Lists returned an unknown item type during apply.",
            )
        before_nodes = {item.node_id for item in baseline_lists.get(node_id, _empty_list()).members}
        after_nodes = {item.node_id for item in observed_list.members}
        if not before_nodes <= after_nodes:
            raise StateError(
                code="github_apply_destructive_drift",
                message=(f"GitHub List {observed_list.name!r} lost an existing membership."),
            )
        if not (after_nodes - before_nodes) <= allowed_members.get(node_id, set()):
            raise StateError(
                code="github_apply_unplanned_drift",
                message=(f"GitHub List {observed_list.name!r} gained an unplanned membership."),
            )


def operation_satisfied(
    operation: GitHubProjectionOperation,
    plan: GitHubProjectionPlan,
    state: GitHubCurationState,
) -> bool:
    repositories = {item.repository: item for item in state.relevant_repositories}
    if operation.kind == "star-repository":
        return bool(operation.repository and repositories[operation.repository].starred)
    target = _operation_target_list(operation, plan, state.lists)
    if operation.kind == "create-list":
        return target is not None
    if target is None or not operation.repository:
        return False
    repository = repositories[operation.repository]
    return repository.node_id in {item.node_id for item in target.members}


def pending_operations(
    plan: GitHubProjectionPlan, state: GitHubCurationState
) -> tuple[GitHubProjectionOperation, ...]:
    return tuple(
        operation
        for operation in plan.operations
        if not operation_satisfied(operation, plan, state)
    )


def requested_membership_union(
    operation: GitHubProjectionOperation,
    plan: GitHubProjectionPlan,
    state: GitHubCurationState,
) -> tuple[str, ...]:
    if operation.kind != "add-membership" or not operation.repository:
        raise ValueError("membership union requires an add-membership operation")
    target = _operation_target_list(operation, plan, state.lists)
    if target is None:
        raise StateError(
            code="github_apply_list_missing",
            message=f"Target List {operation.list_name!r} does not exist.",
        )
    repository = next(
        item for item in state.relevant_repositories if item.repository == operation.repository
    )
    current_ids = {
        github_list.node_id
        for github_list in state.lists
        if repository.node_id in {item.node_id for item in github_list.members}
    }
    return tuple(sorted({*current_ids, target.node_id}))


def verify_postconditions(
    plan: GitHubProjectionPlan,
    baseline: GitHubCurationState,
    current: GitHubCurationState,
) -> tuple[VerifyPostcondition, ...]:
    conditions: list[VerifyPostcondition] = []
    identity_ok = (
        current.account.casefold() == plan.target_account.casefold()
        and current.account_node_id == plan.observed_account_node_id
    )
    conditions.append(
        VerifyPostcondition(
            kind="target-identity",
            subject=plan.target_account,
            expected=plan.observed_account_node_id,
            actual=current.account_node_id,
            state=(VerifyConditionState.VERIFIED if identity_ok else VerifyConditionState.MISMATCH),
        )
    )
    try:
        assert_allowed_progress(plan, baseline, current)
    except StateError as exc:
        conditions.append(
            VerifyPostcondition(
                kind="target-state-integrity",
                subject="sealed additive-only transition",
                expected="only sealed additive effects",
                actual=exc.message,
                state=VerifyConditionState.MISMATCH,
                error_code=exc.code,
            )
        )
    else:
        conditions.append(
            VerifyPostcondition(
                kind="target-state-integrity",
                subject="sealed additive-only transition",
                expected="only sealed additive effects",
                actual="only sealed additive effects",
                state=VerifyConditionState.VERIFIED,
            )
        )

    targets = _target_lists(plan, current.lists, fail_on_missing=False)
    repositories = {item.repository: item for item in current.relevant_repositories}
    for projected_list in plan.projected_lists:
        observed = targets.get(projected_list.collection_slug)
        valid = (
            observed is not None
            and not observed.is_private
            and (observed.description or "") == projected_list.description
        )
        conditions.append(
            VerifyPostcondition(
                kind="public-list",
                subject=projected_list.collection_slug,
                expected=f"public:{projected_list.name}:{projected_list.description}",
                actual=(
                    f"{'private' if observed.is_private else 'public'}:"
                    f"{observed.name}:{observed.description or ''}"
                    if observed
                    else None
                ),
                state=(VerifyConditionState.VERIFIED if valid else VerifyConditionState.MISMATCH),
            )
        )
    for projected in plan.projected_repositories:
        repository = repositories.get(projected.repository)
        starred = repository is not None and repository.starred
        conditions.append(
            VerifyPostcondition(
                kind="star",
                subject=projected.repository,
                expected="starred",
                actual="starred" if starred else "not-starred",
                state=(VerifyConditionState.VERIFIED if starred else VerifyConditionState.MISMATCH),
            )
        )
        for slug in projected.desired_collection_slugs:
            target = targets.get(slug)
            member = bool(
                target
                and repository
                and repository.node_id in {item.node_id for item in target.members}
            )
            subject = f"{slug}:{projected.repository}"
            conditions.append(
                VerifyPostcondition(
                    kind="membership",
                    subject=subject,
                    expected="member",
                    actual="member" if member else "not-member",
                    state=(
                        VerifyConditionState.VERIFIED if member else VerifyConditionState.MISMATCH
                    ),
                )
            )
        current_memberships = {
            item.node_id
            for item in current.lists
            if repository and repository.node_id in {member.node_id for member in item.members}
        }
        for list_id in projected.preserved_existing_list_ids:
            preserved = list_id in current_memberships
            conditions.append(
                VerifyPostcondition(
                    kind="preserved-membership",
                    subject=f"{projected.repository}:{list_id}",
                    expected="preserved",
                    actual="preserved" if preserved else "missing",
                    state=(
                        VerifyConditionState.VERIFIED
                        if preserved
                        else VerifyConditionState.MISMATCH
                    ),
                )
            )
    return tuple(conditions)


def unavailable_plan_postconditions(
    plan: GitHubProjectionPlan,
    error_code: str,
    *,
    include_identity: bool,
) -> tuple[VerifyPostcondition, ...]:
    """Enumerate every plan postcondition when target state cannot be read."""

    conditions: list[VerifyPostcondition] = []
    if include_identity:
        conditions.append(
            VerifyPostcondition(
                kind="target-identity",
                subject=plan.target_account,
                expected=plan.observed_account_node_id,
                actual=None,
                state=VerifyConditionState.UNAVAILABLE,
                error_code=error_code,
            )
        )
    conditions.append(
        VerifyPostcondition(
            kind="target-state-integrity",
            subject="sealed additive-only transition",
            expected="only sealed additive effects",
            actual=None,
            state=VerifyConditionState.UNAVAILABLE,
            error_code=error_code,
        )
    )
    for projected_list in plan.projected_lists:
        conditions.append(
            VerifyPostcondition(
                kind="public-list",
                subject=projected_list.collection_slug,
                expected=(f"public:{projected_list.name}:{projected_list.description}"),
                actual=None,
                state=VerifyConditionState.UNAVAILABLE,
                error_code=error_code,
            )
        )
    for projected in plan.projected_repositories:
        conditions.append(
            VerifyPostcondition(
                kind="star",
                subject=projected.repository,
                expected="starred",
                actual=None,
                state=VerifyConditionState.UNAVAILABLE,
                error_code=error_code,
            )
        )
        conditions.extend(
            VerifyPostcondition(
                kind="membership",
                subject=f"{slug}:{projected.repository}",
                expected="member",
                actual=None,
                state=VerifyConditionState.UNAVAILABLE,
                error_code=error_code,
            )
            for slug in projected.desired_collection_slugs
        )
        conditions.extend(
            VerifyPostcondition(
                kind="preserved-membership",
                subject=f"{projected.repository}:{list_id}",
                expected="preserved",
                actual=None,
                state=VerifyConditionState.UNAVAILABLE,
                error_code=error_code,
            )
            for list_id in projected.preserved_existing_list_ids
        )
    return tuple(conditions)


def _operation_target_list(
    operation: GitHubProjectionOperation,
    plan: GitHubProjectionPlan,
    lists: tuple[GitHubListState, ...],
) -> GitHubListState | None:
    if not operation.collection_slug:
        return None
    projected = next(
        item for item in plan.projected_lists if item.collection_slug == operation.collection_slug
    )
    return _projected_target_list(projected.name, projected.description, lists)


def _projected_target_list(
    name: str,
    description: str,
    lists: tuple[GitHubListState, ...],
) -> GitHubListState | None:
    matches = [item for item in lists if item.name.casefold() == name.casefold()]
    if len(matches) > 1:
        raise StateError(
            code="github_list_name_ambiguous",
            message=f"Multiple GitHub Lists are named {name!r}.",
        )
    if not matches:
        return None
    observed = matches[0]
    if observed.is_private or (observed.description or "") != description:
        raise StateError(
            code="github_list_conflict",
            message=f"GitHub List {name!r} has conflicting public metadata.",
        )
    return observed


def _target_lists(
    plan: GitHubProjectionPlan,
    lists: tuple[GitHubListState, ...],
    *,
    fail_on_missing: bool = True,
) -> dict[str, GitHubListState]:
    result: dict[str, GitHubListState] = {}
    for projected in plan.projected_lists:
        target = _projected_target_list(
            projected.name,
            projected.description,
            lists,
        )
        if target is None:
            if fail_on_missing:
                raise StateError(
                    code="github_apply_list_missing",
                    message=f"Target List {projected.name!r} does not exist.",
                )
            continue
        result[projected.collection_slug] = target
    return result


def _list_metadata(value: GitHubListState) -> tuple[str, str, bool, str, tuple[str, ...]]:
    return (
        value.name,
        value.description or "",
        value.is_private,
        value.slug,
        value.unknown_item_types,
    )


def _empty_list() -> GitHubListState:
    return GitHubListState(
        node_id="empty",
        name="empty",
        description=None,
        is_private=False,
        slug="empty",
        members=(),
    )


def _verify_status(postconditions: tuple[VerifyPostcondition, ...]) -> VerifyStatus:
    if any(item.state is VerifyConditionState.MISMATCH for item in postconditions):
        return VerifyStatus.FAILED
    if any(item.state is VerifyConditionState.UNAVAILABLE for item in postconditions):
        return VerifyStatus.PARTIAL
    return VerifyStatus.VERIFIED


def _json_timestamp(value: datetime) -> str:
    rendered = value.isoformat()
    return f"{rendered.removesuffix('+00:00')}Z" if rendered.endswith("+00:00") else rendered
