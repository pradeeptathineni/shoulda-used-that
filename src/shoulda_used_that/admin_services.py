"""Maintainer-only catalog publication and additive GitHub curation workflows."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from shoulda_used_that.canonical import digest
from shoulda_used_that.curation import CurationSnapshot, compile_profile, load_profile
from shoulda_used_that.errors import GitHubError, GitHubSchemaError, ShouldaError, StateError
from shoulda_used_that.github import GhClient
from shoulda_used_that.github_apply import (
    ApplyOperationOutcome,
    ApplyOperationReceipt,
    ApplyReceipt,
    ApplyStatus,
    VerifyConditionState,
    VerifyPostcondition,
    VerifyReceipt,
    assert_allowed_progress,
    client_mutation_id,
    make_apply_receipt,
    make_operation_receipt,
    make_verify_receipt,
    operation_satisfied,
    pending_operations,
    requested_membership_union,
    unavailable_plan_postconditions,
    verify_postconditions,
)
from shoulda_used_that.github_lists import (
    GitHubCapabilityState,
    GitHubCurationState,
    GitHubListMember,
    GitHubReadClient,
    probe_capabilities,
    read_curation_state,
)
from shoulda_used_that.github_mutations import GhMutationClient, GitHubApplyClient
from shoulda_used_that.models import utc_now
from shoulda_used_that.projection import (
    GitHubProjectionOperation,
    GitHubProjectionPlan,
    build_projection_plan,
    desired_projection_repositories,
)
from shoulda_used_that.public_export import PublicCatalogExport, write_public_catalog
from shoulda_used_that.state import StateStore


def curated(store: StateStore, *, profile_path: Path) -> CurationSnapshot:
    """Compile a versioned public profile without refreshing any external source."""

    profile = load_profile(profile_path)
    previous = store.latest_curation(profile.profile_id)
    snapshot = compile_profile(profile_path, previous=previous)
    store.write_curation_profile(profile)
    store.write_curation(snapshot)
    return snapshot


def exported(
    store: StateStore,
    *,
    curation_snapshot_id: str,
    output: Path,
) -> PublicCatalogExport:
    """Write a staged allowlisted public catalog; private export is unsupported."""

    snapshot = store.read_curation(curation_snapshot_id)
    profile = store.read_curation_profile(snapshot.profile_fingerprint)
    receipt, _ = write_public_catalog(snapshot, profile, output)
    return receipt


def projected(
    store: StateStore,
    *,
    curation_snapshot_id: str,
    account: str,
    github: GitHubReadClient | None = None,
    planned_at: datetime | None = None,
) -> GitHubProjectionPlan:
    """Read exact GitHub state and seal an additive-only plan without mutation."""

    snapshot = store.read_curation(curation_snapshot_id)
    expected_account = snapshot.projection_policy.account
    if expected_account is None or expected_account.casefold() != account.casefold():
        raise StateError(
            code="github_account_mismatch",
            message="Requested account does not match the curation profile's exact account.",
        )
    timestamp = planned_at or utc_now()
    client = github or GhClient()
    capability = probe_capabilities(client, observed_at=timestamp)
    if capability.state not in {
        GitHubCapabilityState.AVAILABLE,
        GitHubCapabilityState.MISSING_SCOPE,
    }:
        raise StateError(
            code="github_capability_unavailable",
            message=(
                f"GitHub Lists capability is {capability.state.value}; "
                "no projection plan was written."
            ),
            details={"error_code": capability.error_code},
        )
    if capability.login.casefold() != account.casefold():
        raise StateError(
            code="github_account_mismatch",
            message="Requested and authenticated GitHub accounts must match.",
        )
    state = read_curation_state(
        client,
        account=account,
        desired_repositories=desired_projection_repositories(snapshot),
        observed_at=timestamp,
    )
    plan = build_projection_plan(
        snapshot,
        state,
        capability,
        account=account,
        created_at=timestamp,
    )
    store.write_github_state(state)
    store.write_github_projection(plan)
    return plan


def applied(
    store: StateStore,
    *,
    plan_id: str,
    fingerprint: str,
    github: GitHubApplyClient | None = None,
    environment: Mapping[str, str] | None = None,
    stdin_isatty: bool,
    clock: Callable[[], datetime] = utc_now,
) -> ApplyReceipt:
    """Apply only sealed additive GitHub operations with append-only receipts."""

    plan, started_at = _validated_apply_plan(
        store,
        plan_id=plan_id,
        fingerprint=fingerprint,
        environment=environment,
        stdin_isatty=stdin_isatty,
        clock=clock,
    )
    client = github or GhMutationClient()
    _validate_live_apply_capability(client, plan, observed_at=started_at)

    baseline = store.read_github_state(plan.github_state_fingerprint)
    current = read_curation_state(
        client,
        account=plan.target_account,
        desired_repositories=tuple(item.repository for item in plan.projected_repositories),
        observed_at=started_at,
    )
    assert_allowed_progress(plan, baseline, current)
    previous = store.latest_apply(plan.plan_id)
    if previous is not None and previous.plan_fingerprint != fingerprint:
        raise StateError(
            code="github_apply_receipt_mismatch",
            message="Prior apply receipt does not belong to the exact sealed plan.",
        )
    prior_operations = previous.operation_receipts if previous else ()
    session_started_at = previous.started_at if previous else started_at
    pending = pending_operations(plan, current)
    if not pending:
        if previous and previous.status is ApplyStatus.COMPLETE:
            return previous
        receipt = make_apply_receipt(
            plan,
            started_at=session_started_at,
            completed_at=clock(),
            before_state_fingerprint=baseline.state_fingerprint,
            operation_receipts=prior_operations,
            status=ApplyStatus.COMPLETE,
            resume_cursor=None,
            failure_code=None,
            readback_state_fingerprint=current.state_fingerprint,
        )
        store.write_github_state(current)
        store.write_apply(receipt)
        return receipt

    _refuse_uncertain_create_retry(pending, prior_operations)
    operation_receipts = list(prior_operations)
    for kind in ("create-list", "star-repository"):
        for operation in plan.operations:
            if operation.kind != kind or operation_satisfied(operation, plan, current):
                continue
            result = _attempt_operation(
                store,
                plan,
                operation,
                client=client,
                state=current,
                prior_receipts=tuple(operation_receipts),
                clock=clock,
            )
            operation_receipts.append(result)
            _write_apply_progress(
                store,
                plan,
                baseline=baseline.state_fingerprint,
                session_started_at=session_started_at,
                operations=tuple(operation_receipts),
                cursor=operation.operation_id,
                failure_code="readback_pending",
                readback=current.state_fingerprint,
                completed_at=clock(),
            )
            if result.outcome is not ApplyOperationOutcome.SUCCEEDED:
                return _finish_failed_attempt(
                    store,
                    plan,
                    baseline=baseline,
                    client=client,
                    session_started_at=session_started_at,
                    operations=tuple(operation_receipts),
                    failed_operation=operation,
                    failure_code=result.error_code or "github_mutation_failed",
                    clock=clock,
                )

        readback = _readback_or_partial(
            store,
            plan,
            baseline=baseline,
            client=client,
            session_started_at=session_started_at,
            operations=tuple(operation_receipts),
            fallback_cursor=_first_pending_id(plan, current),
            clock=clock,
        )
        if isinstance(readback, ApplyReceipt):
            return readback
        current = readback
        remaining_for_kind = tuple(
            item for item in pending_operations(plan, current) if item.kind == kind
        )
        if remaining_for_kind:
            return _write_apply_progress(
                store,
                plan,
                baseline=baseline.state_fingerprint,
                session_started_at=session_started_at,
                operations=tuple(operation_receipts),
                cursor=remaining_for_kind[0].operation_id,
                failure_code="github_apply_readback_mismatch",
                readback=current.state_fingerprint,
                completed_at=clock(),
            )

    for operation in plan.operations:
        if operation.kind != "add-membership" or operation_satisfied(operation, plan, current):
            continue
        result = _attempt_operation(
            store,
            plan,
            operation,
            client=client,
            state=current,
            prior_receipts=tuple(operation_receipts),
            clock=clock,
        )
        operation_receipts.append(result)
        _write_apply_progress(
            store,
            plan,
            baseline=baseline.state_fingerprint,
            session_started_at=session_started_at,
            operations=tuple(operation_receipts),
            cursor=operation.operation_id,
            failure_code="readback_pending",
            readback=current.state_fingerprint,
            completed_at=clock(),
        )
        if result.outcome is not ApplyOperationOutcome.SUCCEEDED:
            return _finish_failed_attempt(
                store,
                plan,
                baseline=baseline,
                client=client,
                session_started_at=session_started_at,
                operations=tuple(operation_receipts),
                failed_operation=operation,
                failure_code=result.error_code or "github_mutation_failed",
                clock=clock,
            )
        current = _materialize_membership_response(
            current,
            operation,
            requested_list_ids=result.requested_list_ids,
            observed_at=clock(),
        )
        store.write_github_state(current)
        if not operation_satisfied(operation, plan, current):
            return _write_apply_progress(
                store,
                plan,
                baseline=baseline.state_fingerprint,
                session_started_at=session_started_at,
                operations=tuple(operation_receipts),
                cursor=operation.operation_id,
                failure_code="github_apply_readback_mismatch",
                readback=current.state_fingerprint,
                completed_at=clock(),
            )

    final_readback = _readback_or_partial(
        store,
        plan,
        baseline=baseline,
        client=client,
        session_started_at=session_started_at,
        operations=tuple(operation_receipts),
        fallback_cursor=_first_pending_id(plan, current),
        clock=clock,
    )
    if isinstance(final_readback, ApplyReceipt):
        return final_readback
    current = final_readback
    remaining = pending_operations(plan, current)
    if remaining:
        return _write_apply_progress(
            store,
            plan,
            baseline=baseline.state_fingerprint,
            session_started_at=session_started_at,
            operations=tuple(operation_receipts),
            cursor=remaining[0].operation_id,
            failure_code="github_apply_readback_mismatch",
            readback=current.state_fingerprint,
            completed_at=clock(),
        )
    receipt = make_apply_receipt(
        plan,
        started_at=session_started_at,
        completed_at=clock(),
        before_state_fingerprint=baseline.state_fingerprint,
        operation_receipts=tuple(operation_receipts),
        status=ApplyStatus.COMPLETE,
        resume_cursor=None,
        failure_code=None,
        readback_state_fingerprint=current.state_fingerprint,
    )
    store.write_github_state(current)
    store.write_apply(receipt)
    return receipt


def _validated_apply_plan(
    store: StateStore,
    *,
    plan_id: str,
    fingerprint: str,
    environment: Mapping[str, str] | None,
    stdin_isatty: bool,
    clock: Callable[[], datetime],
) -> tuple[GitHubProjectionPlan, datetime]:
    if not plan_id.startswith("gcp_"):
        raise StateError(
            code="unsupported_plan_kind",
            message="v0.3.0 apply supports only a github-curation plan ID.",
        )
    plan = store.read_github_projection(plan_id)
    if fingerprint != plan.canonical_plan_fingerprint:
        raise StateError(
            code="github_plan_fingerprint_mismatch",
            message="The supplied plan fingerprint does not match the sealed plan.",
        )
    active_environment = environment or {}
    forbidden_environment = sorted(
        key for key in ("CI", "GITHUB_ACTIONS") if key in active_environment
    )
    if forbidden_environment:
        raise StateError(
            code="github_apply_ci_refused",
            message="GitHub curation apply is forbidden in CI and GitHub Actions.",
            details={"environment_markers": forbidden_environment},
        )
    if not stdin_isatty:
        raise StateError(
            code="github_apply_tty_required",
            message="GitHub curation apply requires an interactive terminal.",
        )
    started_at = clock()
    if started_at >= plan.expires_at:
        raise StateError(
            code="github_plan_expired",
            message="The sealed GitHub projection plan has expired; project it again.",
        )
    _enforce_apply_caps(plan)
    if not plan.apply_ready or plan.capability.state is not GitHubCapabilityState.AVAILABLE:
        raise StateError(
            code="github_plan_not_apply_ready",
            message="The sealed plan did not pass the mutation scope/capability probe.",
            details={"operator_command": plan.capability.operator_command},
        )
    return plan, started_at


def _validate_live_apply_capability(
    client: GitHubApplyClient,
    plan: GitHubProjectionPlan,
    *,
    observed_at: datetime,
) -> None:
    capability = probe_capabilities(client, observed_at=observed_at)
    if capability.state is not GitHubCapabilityState.AVAILABLE:
        raise StateError(
            code="github_apply_capability_unavailable",
            message=(
                "GitHub mutation capability is not currently available; no operation was attempted."
            ),
            details={
                "state": capability.state.value,
                "error_code": capability.error_code,
                "operator_command": capability.operator_command,
            },
        )
    if (
        capability.login.casefold() != plan.target_account.casefold()
        or capability.node_id != plan.observed_account_node_id
    ):
        raise StateError(
            code="github_apply_identity_mismatch",
            message="Authenticated GitHub identity does not match the sealed plan.",
        )


def verified(
    store: StateStore,
    *,
    apply_receipt_id: str,
    github: GitHubReadClient | None = None,
    verified_at: datetime | None = None,
) -> VerifyReceipt:
    """Independently read every expected GitHub postcondition."""

    timestamp = verified_at or utc_now()
    apply_receipt = store.read_apply(apply_receipt_id)
    plan = store.read_github_projection(apply_receipt.plan_id)
    baseline = store.read_github_state(plan.github_state_fingerprint)
    client = github or GhClient()
    postconditions: tuple[VerifyPostcondition, ...]
    capability = probe_capabilities(client, observed_at=timestamp)
    observed_login = capability.login or None
    observed_node_id = capability.node_id
    if capability.state not in {
        GitHubCapabilityState.AVAILABLE,
        GitHubCapabilityState.MISSING_SCOPE,
    }:
        identity_state = (
            VerifyConditionState.MISMATCH
            if observed_node_id is not None
            and (
                capability.login.casefold() != plan.target_account.casefold()
                or observed_node_id != plan.observed_account_node_id
            )
            else VerifyConditionState.VERIFIED
            if observed_node_id is not None
            else VerifyConditionState.UNAVAILABLE
        )
        postconditions = (
            VerifyPostcondition(
                kind="capability",
                subject="github-readback",
                expected="readback-capable",
                actual=capability.state.value,
                state=VerifyConditionState.UNAVAILABLE,
                error_code=capability.error_code or capability.state.value,
            ),
            VerifyPostcondition(
                kind="target-identity",
                subject=plan.target_account,
                expected=plan.observed_account_node_id,
                actual=observed_node_id,
                state=identity_state,
                error_code=(
                    "github_verify_identity_mismatch"
                    if identity_state is VerifyConditionState.MISMATCH
                    else capability.error_code
                ),
            ),
            *unavailable_plan_postconditions(
                plan,
                capability.error_code or capability.state.value,
                include_identity=False,
            ),
        )
        receipt = make_verify_receipt(
            apply_receipt,
            verified_at=timestamp,
            observed_login=observed_login,
            observed_account_node_id=observed_node_id,
            observed_state_fingerprint=None,
            postconditions=postconditions,
        )
        store.write_verify(receipt)
        return receipt
    if (
        capability.login.casefold() != plan.target_account.casefold()
        or capability.node_id != plan.observed_account_node_id
    ):
        postconditions = (
            VerifyPostcondition(
                kind="capability",
                subject="github-readback",
                expected="readback-capable",
                actual=capability.state.value,
                state=VerifyConditionState.VERIFIED,
            ),
            VerifyPostcondition(
                kind="target-identity",
                subject=plan.target_account,
                expected=plan.observed_account_node_id,
                actual=capability.node_id,
                state=VerifyConditionState.MISMATCH,
                error_code="github_verify_identity_mismatch",
            ),
            *unavailable_plan_postconditions(
                plan,
                "github_verify_identity_mismatch",
                include_identity=False,
            ),
        )
        receipt = make_verify_receipt(
            apply_receipt,
            verified_at=timestamp,
            observed_login=observed_login,
            observed_account_node_id=observed_node_id,
            observed_state_fingerprint=None,
            postconditions=postconditions,
        )
        store.write_verify(receipt)
        return receipt
    try:
        state = read_curation_state(
            client,
            account=plan.target_account,
            desired_repositories=tuple(item.repository for item in plan.projected_repositories),
            observed_at=timestamp,
        )
        postconditions = (
            VerifyPostcondition(
                kind="capability",
                subject="github-readback",
                expected="readback-capable",
                actual=capability.state.value,
                state=VerifyConditionState.VERIFIED,
            ),
            *verify_postconditions(plan, baseline, state),
        )
        state_fingerprint = state.state_fingerprint
        observed_login = state.account
        observed_node_id = state.account_node_id
        store.write_github_state(state)
    except ShouldaError as exc:
        identity_mismatch = exc.code in {
            "github_account_mismatch",
            "github_identity_drift",
            "github_identity_mismatch",
        }
        postconditions = (
            VerifyPostcondition(
                kind="capability",
                subject="github-readback",
                expected="readback-capable",
                actual=capability.state.value,
                state=VerifyConditionState.VERIFIED,
            ),
            VerifyPostcondition(
                kind="target-identity",
                subject=plan.target_account,
                expected=plan.observed_account_node_id,
                actual=(
                    f"capability:{observed_node_id};readback:{exc.code}"
                    if identity_mismatch
                    else observed_node_id
                ),
                state=(
                    VerifyConditionState.MISMATCH
                    if identity_mismatch
                    else VerifyConditionState.VERIFIED
                ),
                error_code=exc.code if identity_mismatch else None,
            ),
            *unavailable_plan_postconditions(plan, exc.code, include_identity=False),
        )
        state_fingerprint = None
    receipt = make_verify_receipt(
        apply_receipt,
        verified_at=timestamp,
        observed_login=observed_login,
        observed_account_node_id=observed_node_id,
        observed_state_fingerprint=state_fingerprint,
        postconditions=postconditions,
    )
    store.write_verify(receipt)
    return receipt


def _attempt_operation(
    store: StateStore,
    plan: GitHubProjectionPlan,
    operation: GitHubProjectionOperation,
    *,
    client: GitHubApplyClient,
    state: GitHubCurationState,
    prior_receipts: tuple[ApplyOperationReceipt, ...],
    clock: Callable[[], datetime],
) -> ApplyOperationReceipt:
    attempt = 1 + sum(item.operation_id == operation.operation_id for item in prior_receipts)
    started_at = clock()
    requested_list_ids: tuple[str, ...] = ()
    try:
        if operation.kind == "create-list":
            if not operation.list_name or not operation.list_description:
                raise StateError(
                    code="github_plan_operation_invalid",
                    message="List-create operation omitted exact public metadata.",
                )
            client.create_user_list(
                name=operation.list_name,
                description=operation.list_description,
                client_mutation_id=client_mutation_id(plan, operation.operation_id),
            )
        elif operation.kind == "star-repository":
            if not operation.repository:
                raise StateError(
                    code="github_plan_operation_invalid",
                    message="Star operation omitted its repository.",
                )
            client.star_repository(operation.repository)
        else:
            if not operation.repository_node_id:
                raise StateError(
                    code="github_plan_operation_invalid",
                    message="Membership operation omitted its repository node ID.",
                )
            requested_list_ids = requested_membership_union(operation, plan, state)
            result = client.update_user_lists_for_item(
                repository_node_id=operation.repository_node_id,
                list_ids=requested_list_ids,
                client_mutation_id=client_mutation_id(plan, operation.operation_id),
            )
            if (
                result.repository_node_id != operation.repository_node_id
                or result.repository != operation.repository
                or result.list_ids != requested_list_ids
            ):
                raise GitHubSchemaError(
                    code="github_mutation_postcondition_mismatch",
                    message=(
                        "GitHub membership response did not match the sealed repository "
                        "identity and complete requested List union."
                    ),
                )
    except GitHubError as exc:
        outcome = (
            ApplyOperationOutcome.INDETERMINATE
            if exc.code
            in {
                "github_timeout",
                "github_transport_failed",
                "github_invalid_json",
                "github_schema_mismatch",
                "github_response_too_large",
                "github_graphql_error",
                "github_mutation_schema_invalid",
                "github_mutation_identity_mismatch",
                "github_mutation_postcondition_mismatch",
                "github_mutation_response_too_large",
            }
            else ApplyOperationOutcome.FAILED
        )
        receipt = make_operation_receipt(
            plan,
            operation,
            attempt=attempt,
            started_at=started_at,
            completed_at=clock(),
            outcome=outcome,
            requested_list_ids=requested_list_ids,
            error_code=exc.code,
            error_message=exc.message,
        )
    else:
        receipt = make_operation_receipt(
            plan,
            operation,
            attempt=attempt,
            started_at=started_at,
            completed_at=clock(),
            outcome=ApplyOperationOutcome.SUCCEEDED,
            requested_list_ids=requested_list_ids,
        )
    store.write_apply_operation(receipt)
    return receipt


def _finish_failed_attempt(
    store: StateStore,
    plan: GitHubProjectionPlan,
    *,
    baseline: GitHubCurationState,
    client: GitHubApplyClient,
    session_started_at: datetime,
    operations: tuple[ApplyOperationReceipt, ...],
    failed_operation: GitHubProjectionOperation,
    failure_code: str,
    clock: Callable[[], datetime],
) -> ApplyReceipt:
    try:
        current = read_curation_state(
            client,
            account=plan.target_account,
            desired_repositories=tuple(item.repository for item in plan.projected_repositories),
            observed_at=clock(),
        )
        assert_allowed_progress(plan, baseline, current)
    except ShouldaError:
        current = None
    if current is not None:
        store.write_github_state(current)
        remaining = pending_operations(plan, current)
        cursor = remaining[0].operation_id if remaining else failed_operation.operation_id
        readback = current.state_fingerprint
    else:
        cursor = failed_operation.operation_id
        readback = None
    return _write_apply_progress(
        store,
        plan,
        baseline=baseline.state_fingerprint,
        session_started_at=session_started_at,
        operations=operations,
        cursor=cursor,
        failure_code=failure_code,
        readback=readback,
        completed_at=clock(),
    )


def _readback_or_partial(
    store: StateStore,
    plan: GitHubProjectionPlan,
    *,
    baseline: GitHubCurationState,
    client: GitHubApplyClient,
    session_started_at: datetime,
    operations: tuple[ApplyOperationReceipt, ...],
    fallback_cursor: str,
    clock: Callable[[], datetime],
) -> GitHubCurationState | ApplyReceipt:
    try:
        observed = read_curation_state(
            client,
            account=plan.target_account,
            desired_repositories=tuple(item.repository for item in plan.projected_repositories),
            observed_at=clock(),
        )
        assert_allowed_progress(plan, baseline, observed)
    except ShouldaError as exc:
        return _write_apply_progress(
            store,
            plan,
            baseline=baseline.state_fingerprint,
            session_started_at=session_started_at,
            operations=operations,
            cursor=fallback_cursor,
            failure_code=exc.code,
            readback=None,
            completed_at=clock(),
        )
    store.write_github_state(observed)
    return observed


def _materialize_membership_response(
    state: GitHubCurationState,
    operation: GitHubProjectionOperation,
    *,
    requested_list_ids: tuple[str, ...],
    observed_at: datetime,
) -> GitHubCurationState:
    """Advance local state from a strictly validated membership mutation response.

    GitHub's mutation returns the complete resulting List-ID set and the adapter
    rejects any response that differs from the requested union. Materializing
    that exact response avoids treating the eventually consistent Lists query as
    an immediate write acknowledgement. A complete remote Star-and-List replay
    still gates the final apply receipt and the independent verify receipt.
    """

    if not operation.repository or not operation.repository_node_id:
        raise StateError(
            code="github_plan_operation_invalid",
            message="Membership operation omitted repository identity.",
        )
    requested = set(requested_list_ids)
    known = {item.node_id for item in state.lists}
    if not requested or not requested <= known:
        raise StateError(
            code="github_membership_response_invalid",
            message="Membership mutation returned an unknown or empty List union.",
        )
    repository = next(
        (
            item
            for item in state.relevant_repositories
            if item.node_id == operation.repository_node_id
            and item.repository == operation.repository
        ),
        None,
    )
    if repository is None:
        raise StateError(
            code="github_membership_response_invalid",
            message="Membership mutation repository was absent from current state.",
        )
    member = GitHubListMember(
        node_id=repository.node_id,
        repository=repository.repository,
        is_private=repository.is_private,
        is_archived=repository.is_archived,
        url=repository.url,
    )
    current_ids = {
        github_list.node_id
        for github_list in state.lists
        if repository.node_id in {item.node_id for item in github_list.members}
    }
    if not current_ids <= requested:
        raise StateError(
            code="github_membership_response_invalid",
            message="Membership mutation response would remove an observed List membership.",
        )
    lists = []
    for github_list in state.lists:
        members = {item.repository: item for item in github_list.members}
        if github_list.node_id in requested:
            members[member.repository] = member
        lists.append(
            github_list.model_copy(
                update={"members": tuple(members[key] for key in sorted(members))}
            )
        )
    semantic = {
        "account": state.account,
        "account_node_id": state.account_node_id,
        "relevant_repositories": [
            item.model_dump(mode="json") for item in state.relevant_repositories
        ],
        "lists": [item.model_dump(mode="json") for item in lists],
    }
    return GitHubCurationState(
        account=state.account,
        account_node_id=state.account_node_id,
        observed_at=observed_at,
        total_starred_count=state.total_starred_count,
        relevant_repositories=state.relevant_repositories,
        lists=tuple(lists),
        state_fingerprint=digest(semantic, prefix="github"),
    )


def _write_apply_progress(
    store: StateStore,
    plan: GitHubProjectionPlan,
    *,
    baseline: str,
    session_started_at: datetime,
    operations: tuple[ApplyOperationReceipt, ...],
    cursor: str,
    failure_code: str,
    readback: str | None,
    completed_at: datetime,
) -> ApplyReceipt:
    had_possible_effect = any(
        item.outcome in {ApplyOperationOutcome.SUCCEEDED, ApplyOperationOutcome.INDETERMINATE}
        for item in operations
    )
    receipt = make_apply_receipt(
        plan,
        started_at=session_started_at,
        completed_at=completed_at,
        before_state_fingerprint=baseline,
        operation_receipts=operations,
        status=ApplyStatus.PARTIAL if had_possible_effect else ApplyStatus.FAILED,
        resume_cursor=cursor,
        failure_code=failure_code,
        readback_state_fingerprint=readback,
    )
    store.write_apply(receipt)
    return receipt


def _first_pending_id(plan: GitHubProjectionPlan, state: GitHubCurationState) -> str:
    remaining = pending_operations(plan, state)
    return remaining[0].operation_id if remaining else plan.operations[-1].operation_id


def _refuse_uncertain_create_retry(
    pending: tuple[GitHubProjectionOperation, ...],
    receipts: tuple[ApplyOperationReceipt, ...],
) -> None:
    pending_ids = {item.operation_id for item in pending if item.kind == "create-list"}
    uncertain = [
        item.operation_id
        for item in receipts
        if item.request_kind == "create-list"
        and item.outcome in {ApplyOperationOutcome.SUCCEEDED, ApplyOperationOutcome.INDETERMINATE}
        and item.operation_id in pending_ids
    ]
    if uncertain:
        raise StateError(
            code="github_indeterminate_create_requires_reconciliation",
            message=(
                "An uncertain List create is still not visible; automatic retry is "
                "refused to prevent a duplicate List."
            ),
            details={"operation_ids": uncertain},
        )


def _enforce_apply_caps(plan: GitHubProjectionPlan) -> None:
    counts = plan.operation_counts
    caps = plan.caps
    violations = {
        name: {"operations": operations, "cap": cap}
        for name, operations, cap in (
            ("total", counts.total, caps.total),
            ("create_lists", counts.create_lists, caps.create_lists),
            ("star_repositories", counts.star_repositories, caps.star_repositories),
            ("add_memberships", counts.add_memberships, caps.add_memberships),
        )
        if operations > cap
    }
    if violations:
        raise StateError(
            code="github_operation_cap_exceeded",
            message="The sealed plan exceeds its operation caps.",
            details={"violations": violations},
        )
