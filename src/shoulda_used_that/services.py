"""End-to-end deterministic workflows behind the public CLI."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from shoulda_used_that import __version__
from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.curation import CurationSnapshot, compile_profile, load_profile
from shoulda_used_that.errors import (
    GitHubError,
    GitHubSchemaError,
    ShouldaError,
    SourceError,
    StateError,
)
from shoulda_used_that.filters import evaluate_candidates, normalized_predicate_tree
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
from shoulda_used_that.models import (
    AdoptionPlan,
    Candidate,
    CandidateEvaluation,
    CheckReceipt,
    DecisionReceipt,
    DiffMateriality,
    Disposition,
    EvidenceState,
    FieldDiff,
    FilterSpec,
    ProjectionOperation,
    ProjectionPlan,
    RecheckOutcome,
    RecheckReceipt,
    SavedItem,
    SaveReceipt,
    SourceObservation,
    SourceRequest,
    utc_now,
)
from shoulda_used_that.project_context import (
    ProjectGitHub,
    ProjectSnapshot,
    applicability_evidence,
    inspect_project,
)
from shoulda_used_that.projection import (
    GitHubProjectionOperation,
    GitHubProjectionPlan,
    build_projection_plan,
    desired_projection_repositories,
)
from shoulda_used_that.public_export import PublicCatalogExport, write_public_catalog
from shoulda_used_that.sources import SourceBatch, load_sources, merge_batches
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
    public: bool,
    output: Path,
) -> PublicCatalogExport:
    """Write a staged allowlisted public catalog; private export is unsupported."""

    if not public:
        raise StateError(
            code="public_export_flag_required",
            message="Catalog export requires the explicit --public boundary.",
        )
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

    if not plan_id.startswith("gcp_"):
        raise StateError(
            code="unsupported_plan_kind",
            message="v0.2.0 apply supports only a github-curation plan ID.",
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

    client = github or GhMutationClient()
    capability = probe_capabilities(client, observed_at=started_at)
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


def inspected(
    store: StateStore,
    *,
    target: str,
    sbom_path: Path | None = None,
    github: ProjectGitHub | None = None,
    observed_at: datetime | None = None,
) -> ProjectSnapshot:
    """Create and persist a bounded read-only snapshot of one explicit project."""

    snapshot = inspect_project(target, sbom_path=sbom_path, github=github, observed_at=observed_at)
    store.write_project(snapshot)
    return snapshot


def resolve_project_context(
    store: StateStore,
    value: str,
    *,
    github: ProjectGitHub | None = None,
    observed_at: datetime | None = None,
) -> ProjectSnapshot:
    """Resolve an immutable snapshot ID or inspect one explicit target."""

    if value.startswith("psn_"):
        return store.read_project(value)
    return inspected(store, target=value, github=github, observed_at=observed_at)


MATERIAL_FIELDS = {
    "role",
    "license",
    "archived",
    "disabled",
    "platforms",
    "runtimes",
    "network_boundary",
    "security_state",
}
IGNORED_DIFF_FIELDS = {"sources", "conflicts", "metadata", "schema_version"}


def checked(
    store: StateStore,
    *,
    need: str,
    source_requests: tuple[SourceRequest, ...],
    filter_spec: FilterSpec,
    project_snapshot: ProjectSnapshot | None = None,
    github: GhClient | None = None,
    observed_at: datetime | None = None,
) -> CheckReceipt:
    """Discover, deduplicate, gate, filter, fingerprint, and persist a check."""

    if not source_requests:
        raise SourceError(
            code="source_required",
            message="At least one explicit --source is required; no source is expanded implicitly.",
        )
    timestamp = observed_at or utc_now()
    batches = load_sources(source_requests, github=github, observed_at=timestamp)
    candidates, raw_count = merge_batches(batches)
    evaluations, visible, result_fingerprint, counts = evaluate_candidates(
        candidates, filter_spec, observed_at=timestamp, raw_count=raw_count
    )
    if project_snapshot is not None:
        evaluations = _with_project_context(evaluations, project_snapshot)
    source_fingerprint = _source_fingerprint(batches)
    seed = {
        "need": need,
        "profile": store.profile,
        "created_at": timestamp.isoformat(),
        "source_snapshot_fingerprint": source_fingerprint,
        "filter_spec": filter_spec.model_dump(mode="json"),
        "result_set_fingerprint": result_fingerprint,
        "project_snapshot_fingerprint": (
            project_snapshot.canonical_fingerprint if project_snapshot else None
        ),
    }
    receipt = CheckReceipt(
        check_id=short_id(seed, prefix="chk"),
        need=need,
        profile=store.profile,
        created_at=timestamp,
        normalizer_version=__version__,
        source_requests=source_requests,
        source_observations=tuple(batch.observation for batch in batches),
        source_snapshot_fingerprint=source_fingerprint,
        filter_spec=filter_spec,
        normalized_predicate_tree=normalized_predicate_tree(filter_spec),
        unknown_policy={
            "hard_gate": "unknown facts are excluded",
            "soft_evidence": "unknown facts remain unless explicitly filtered",
            **(
                {
                    "project_context": (
                        "visible evidence only; never an implicit need or popularity rank"
                    )
                }
                if project_snapshot
                else {}
            ),
        },
        evaluations=evaluations,
        result_repositories=tuple(candidate.repository for candidate in visible),
        result_set_fingerprint=result_fingerprint,
        ordering=(
            *(field for field in filter_spec.sort if field.removeprefix("-") != "repo"),
            "repo",
        ),
        counts=counts,
        project_snapshot_id=(project_snapshot.project_snapshot_id if project_snapshot else None),
        project_snapshot_fingerprint=(
            project_snapshot.canonical_fingerprint if project_snapshot else None
        ),
        project_target_identity=(project_snapshot.target_identity if project_snapshot else None),
    )
    store.write_check(receipt)
    return receipt


def saved(
    store: StateStore,
    *,
    repositories: Sequence[str],
    save_all: bool,
    from_check_id: str | None,
    disposition: Disposition | None,
    list_name: str | None,
    created_at: datetime | None = None,
) -> tuple[SaveReceipt, ProjectionPlan | None]:
    """Save exact local candidates without refreshing or mutating GitHub."""

    if save_all and repositories:
        raise StateError(
            code="save_scope_ambiguous",
            message="Use either explicit repositories or --all, not both.",
        )
    if not save_all and not repositories:
        raise StateError(
            code="save_scope_missing",
            message="Name at least one owner/repo or use --all.",
        )
    check: CheckReceipt | None = None
    candidates: dict[str, Candidate] = {}
    if save_all or from_check_id:
        check = store.read_check(from_check_id) if from_check_id else store.latest_check()
        visible = set(check.result_repositories)
        candidates = {
            evaluation.candidate.repository: evaluation.candidate
            for evaluation in check.evaluations
            if evaluation.included and evaluation.candidate.repository in visible
        }
        if set(candidates) != visible:
            raise StateError(
                code="check_result_drift",
                message=(
                    f"Stored check {check.check_id} no longer contains its exact "
                    "visible result set."
                ),
            )
        selected = list(check.result_repositories) if save_all else list(repositories)
    else:
        selected = list(repositories)
        try:
            latest = store.latest_check()
        except StateError:
            latest = None
        if latest:
            candidates = {
                evaluation.candidate.repository: evaluation.candidate
                for evaluation in latest.evaluations
            }

    normalized = tuple(dict.fromkeys(Candidate(repository=value).repository for value in selected))
    if check and not save_all:
        outside_scope = sorted(set(normalized) - set(check.result_repositories))
        if outside_scope:
            raise StateError(
                code="save_outside_check_scope",
                message=(
                    "Explicit repositories used with --from must belong to that "
                    "check's visible set."
                ),
                details={"repositories": outside_scope, "check_id": check.check_id},
            )

    timestamp = created_at or utc_now()
    projection = None
    if list_name:
        if check is None:
            raise StateError(
                code="projection_requires_check",
                message="A List projection must be bound to --all or --from <check_id>.",
            )
        # Construct and validate the complete plan before any saved item is
        # written, so invalid projection input cannot leave partial state.
        projection = _projection_plan(
            store,
            check=check,
            candidates=tuple(candidates[repository] for repository in normalized),
            list_name=list_name,
            created_at=timestamp,
        )

    created: list[str] = []
    already: list[str] = []
    for repository in normalized:
        if store.saved_item(repository) is not None:
            already.append(repository)
            continue
        candidate = candidates.get(repository, Candidate(repository=repository))
        item = SavedItem(
            repository=repository,
            candidate=candidate,
            saved_at=timestamp,
            disposition=disposition,
            source_check_id=check.check_id if check else None,
            source_result_fingerprint=check.result_set_fingerprint if check else None,
        )
        store.write_saved_item(item)
        created.append(repository)

    if projection:
        store.write_projection(projection)

    seed = {
        "profile": store.profile,
        "repositories": normalized,
        "disposition": disposition.value if disposition else None,
        "check": check.check_id if check else None,
        "result_fingerprint": check.result_set_fingerprint if check else None,
        "projection": projection.plan_id if projection else None,
        "created_at": timestamp.isoformat(),
        "created": created,
        "already_saved": already,
    }
    receipt = SaveReceipt(
        save_id=short_id(seed, prefix="sav"),
        created_at=timestamp,
        profile=store.profile,
        repositories=normalized,
        created=tuple(created),
        already_saved=tuple(already),
        disposition=disposition,
        source_check_id=check.check_id if check else None,
        source_result_fingerprint=check.result_set_fingerprint if check else None,
        projection_plan_id=projection.plan_id if projection else None,
    )
    store.write_save_receipt(receipt)
    return receipt, projection


def remembered(
    store: StateStore,
    *,
    repository: str,
    need: str,
    disposition: Disposition,
    rationale: Sequence[str],
    evidence_ids: Sequence[str],
    reconsider_when: Sequence[str],
    alternatives: Sequence[str] = (),
    unknowns: Sequence[str] = (),
    from_check_id: str | None = None,
    supersedes: str | None = None,
    created_at: datetime | None = None,
) -> DecisionReceipt:
    """Write an immutable decision or an explicit superseding revision."""

    if not rationale:
        raise StateError(code="rationale_required", message="At least one --because is required.")
    if not reconsider_when:
        raise StateError(
            code="reconsideration_required",
            message="At least one --reconsider-when trigger is required.",
        )
    candidate = Candidate(repository=repository)
    check = store.read_check(from_check_id) if from_check_id else None
    if check and candidate.repository not in {
        evaluation.candidate.repository for evaluation in check.evaluations
    }:
        raise StateError(
            code="decision_outside_check_scope",
            message=(
                "A decision bound with --from must concern a candidate observed in that check."
            ),
            details={"repository": candidate.repository, "check_id": check.check_id},
        )
    automatic_evidence = (
        tuple(observation.payload_fingerprint for observation in check.source_observations)
        if check
        else ()
    )
    timestamp = created_at or utc_now()
    combined_evidence = tuple(sorted({*automatic_evidence, *evidence_ids}))
    seed = {
        "profile": store.profile,
        "repository": candidate.repository,
        "need": need,
        "disposition": disposition.value,
        "rationale": list(rationale),
        "evidence_ids": combined_evidence,
        "alternatives": list(alternatives),
        "unknowns": list(unknowns),
        "reconsider_when": list(reconsider_when),
        "check": check.check_id if check else None,
        "supersedes": supersedes,
        "created_at": timestamp.isoformat(),
    }
    receipt = DecisionReceipt(
        decision_id=short_id(seed, prefix="dec"),
        created_at=timestamp,
        profile=store.profile,
        repository=candidate.repository,
        need=need,
        disposition=disposition,
        rationale=tuple(rationale),
        evidence_ids=combined_evidence,
        alternatives=tuple(alternatives),
        unknowns=tuple(unknowns),
        reconsider_when=tuple(reconsider_when),
        source_check_id=check.check_id if check else None,
        source_result_fingerprint=check.result_set_fingerprint if check else None,
        supersedes=supersedes,
    )
    if supersedes:
        previous = store.read_decision(supersedes)
        if previous.repository != receipt.repository:
            raise StateError(
                code="supersession_subject_mismatch",
                message=(
                    "A decision may supersede only a receipt for the same canonical repository."
                ),
            )
    store.write_decision(receipt)
    return receipt


def rechecked(
    store: StateStore,
    *,
    target_id: str,
    github: GhClient | None = None,
    checked_at: datetime | None = None,
) -> RecheckReceipt:
    """Replay bound sources, preserve LKG on failure, and classify typed differences."""

    prior, logical_target = store.resolve_check_for_target(target_id)
    timestamp = checked_at or utc_now()
    batches: list[SourceBatch] = []
    observations: list[SourceObservation] = []
    source_errors: list[str] = []
    prior_by_request = {
        (item.kind, item.locator, item.query): item for item in prior.source_observations
    }
    for request in prior.source_requests:
        try:
            batch = load_sources((request,), github=github, observed_at=timestamp)[0]
            batches.append(batch)
            observations.append(batch.observation)
        except ShouldaError as exc:
            previous = prior_by_request.get((request.kind, request.locator, request.query))
            observations.append(
                SourceObservation(
                    kind=request.kind,
                    locator=request.locator,
                    query=request.query,
                    observed_at=timestamp,
                    tool_version=previous.tool_version if previous else f"shoulda/{__version__}",
                    payload_fingerprint=(
                        previous.payload_fingerprint
                        if previous
                        else digest({"request": request.model_dump(mode="json")}, prefix="payload")
                    ),
                    candidate_count=previous.candidate_count if previous else 0,
                    state=EvidenceState.ERROR,
                    error_code=exc.code,
                    error_message=exc.message,
                )
            )
            source_errors.append(f"{request.kind.value}: {exc.code}: {exc.message}")

    if source_errors:
        outcome = RecheckOutcome.MATERIAL_REVIEW_REQUIRED
        current_fingerprint = prior.result_set_fingerprint
        diffs: tuple[FieldDiff, ...] = ()
        lkg_preserved = True
    else:
        candidates, raw_count = merge_batches(tuple(batches))
        evaluations, visible, current_fingerprint, counts = evaluate_candidates(
            candidates, prior.filter_spec, observed_at=timestamp, raw_count=raw_count
        )
        if prior.project_snapshot_id:
            project_snapshot = store.read_project(prior.project_snapshot_id)
            if project_snapshot.canonical_fingerprint != prior.project_snapshot_fingerprint:
                raise StateError(
                    code="project_snapshot_fingerprint_mismatch",
                    message="The check's bound project snapshot fingerprint does not match state.",
                )
            evaluations = _with_project_context(evaluations, project_snapshot)
        diffs = _diff_candidates(prior, visible)
        if any(item.materiality is DiffMateriality.MATERIAL_REVIEW for item in diffs):
            outcome = RecheckOutcome.MATERIAL_REVIEW_REQUIRED
        elif (
            diffs
            or _source_identity_from_observations(tuple(observations))
            != prior.source_snapshot_fingerprint
        ):
            outcome = RecheckOutcome.REFRESH_ONLY
        else:
            outcome = RecheckOutcome.SEMANTIC_NOOP
        lkg_preserved = outcome is RecheckOutcome.MATERIAL_REVIEW_REQUIRED
        source_fingerprint = _source_identity_from_observations(tuple(observations))
        snapshot_seed = {
            "need": prior.need,
            "profile": store.profile,
            "created_at": timestamp.isoformat(),
            "source_snapshot_fingerprint": source_fingerprint,
            "filter_spec": prior.filter_spec.model_dump(mode="json"),
            "result_set_fingerprint": current_fingerprint,
            "project_snapshot_fingerprint": prior.project_snapshot_fingerprint,
        }
        snapshot = prior.model_copy(
            update={
                "check_id": short_id(snapshot_seed, prefix="chk"),
                "created_at": timestamp,
                "source_observations": tuple(observations),
                "source_snapshot_fingerprint": source_fingerprint,
                "evaluations": evaluations,
                "result_repositories": tuple(item.repository for item in visible),
                "result_set_fingerprint": current_fingerprint,
                "counts": counts,
            }
        )
        store.write_check_snapshot(snapshot)
        if not lkg_preserved:
            store.update_baseline(logical_target, snapshot.check_id)

    seed = {
        "target": logical_target,
        "prior": prior.check_id,
        "checked_at": timestamp.isoformat(),
        "outcome": outcome.value,
        "current": current_fingerprint,
        "errors": source_errors,
        "diffs": [item.model_dump(mode="json") for item in diffs],
    }
    receipt = RecheckReceipt(
        recheck_id=short_id(seed, prefix="rck"),
        checked_at=timestamp,
        profile=store.profile,
        target_id=logical_target,
        prior_check_id=prior.check_id,
        outcome=outcome,
        last_known_good_fingerprint=prior.result_set_fingerprint,
        current_fingerprint=current_fingerprint,
        last_known_good_preserved=lkg_preserved,
        source_observations=tuple(observations),
        diffs=diffs,
        source_errors=tuple(source_errors),
    )
    store.write_recheck(receipt)
    return receipt


def used(
    store: StateStore,
    *,
    repository: str,
    need: str,
    target: str,
    proposed_files: Sequence[str],
    native_tools: Sequence[str],
    tests: Sequence[str],
    expected_postconditions: Sequence[str],
    rollback: Sequence[str],
    remaining_evidence: Sequence[str],
    created_at: datetime | None = None,
) -> AdoptionPlan:
    """Create a sealed planning-only adoption receipt without touching the target."""

    if not expected_postconditions:
        raise StateError(
            code="postcondition_required",
            message="At least one --postcondition is required for an adoption plan.",
        )
    if not rollback:
        raise StateError(
            code="rollback_required",
            message="At least one --rollback step is required for an adoption plan.",
        )
    timestamp = created_at or utc_now()
    normalized_repository = Candidate(repository=repository).repository
    semantic_seed = {
        "profile": store.profile,
        "repository": normalized_repository,
        "need": need,
        "target": target,
        "proposed_files": list(proposed_files),
        "native_tools": list(native_tools),
        "tests": list(tests),
        "postconditions": list(expected_postconditions),
        "rollback": list(rollback),
        "remaining_evidence": list(remaining_evidence),
    }
    fingerprint = digest(semantic_seed, prefix="plan")
    identity_seed = {**semantic_seed, "created_at": timestamp.isoformat()}
    plan = AdoptionPlan(
        plan_id=short_id(identity_seed, prefix="use"),
        plan_fingerprint=fingerprint,
        created_at=timestamp,
        profile=store.profile,
        repository=normalized_repository,
        need=need,
        target=target,
        proposed_files=tuple(proposed_files),
        native_tools=tuple(native_tools),
        tests=tuple(tests),
        expected_postconditions=tuple(expected_postconditions),
        rollback=tuple(rollback),
        remaining_evidence=tuple(remaining_evidence),
    )
    store.write_adoption(plan)
    return plan


def validate_unapplied_plan(store: StateStore, plan_id: str) -> AdoptionPlan | ProjectionPlan:
    """Resolve a legacy planning-only adoption or List projection receipt."""

    if plan_id.startswith("use_"):
        return store.read_adoption(plan_id)
    if plan_id.startswith("prj_"):
        return store.read_projection(plan_id)
    raise StateError(
        code="invalid_plan_id",
        message="Plan identifier must start with use_ or prj_.",
    )


def _projection_plan(
    store: StateStore,
    *,
    check: CheckReceipt,
    candidates: tuple[Candidate, ...],
    list_name: str,
    created_at: datetime,
) -> ProjectionPlan:
    operations: list[ProjectionOperation] = []
    for candidate in candidates:
        already_starred = candidate.is_starred is True
        operations.append(
            ProjectionOperation(
                repository=candidate.repository,
                classification="already_starred" if already_starred else "requires_star",
                status="planned" if already_starred else "blocked",
                operations=(
                    ("add_to_list",) if already_starred else ("star_repository", "add_to_list")
                ),
            )
        )
    semantic_seed = {
        "profile": store.profile,
        "list_name": list_name,
        "check": check.check_id,
        "result_fingerprint": check.result_set_fingerprint,
        "operations": [item.model_dump(mode="json") for item in operations],
    }
    fingerprint = digest(semantic_seed, prefix="plan")
    identity_seed = {**semantic_seed, "created_at": created_at.isoformat()}
    return ProjectionPlan(
        plan_id=short_id(identity_seed, prefix="prj"),
        plan_fingerprint=fingerprint,
        created_at=created_at,
        profile=store.profile,
        list_name=list_name,
        source_check_id=check.check_id,
        source_result_fingerprint=check.result_set_fingerprint,
        source_state_fingerprint=check.source_snapshot_fingerprint,
        operations=tuple(operations),
    )


def _source_fingerprint(batches: Sequence[SourceBatch]) -> str:
    return digest([batch.observation.identity_view() for batch in batches], prefix="srcset")


def _with_project_context(
    evaluations: tuple[CandidateEvaluation, ...], snapshot: ProjectSnapshot
) -> tuple[CandidateEvaluation, ...]:
    return tuple(
        evaluation.model_copy(
            update={"applicability": applicability_evidence(evaluation.candidate, snapshot)}
        )
        for evaluation in evaluations
    )


def _source_identity_from_observations(observations: tuple[SourceObservation, ...]) -> str:
    return digest([item.identity_view() for item in observations], prefix="srcset")


def _diff_candidates(prior: CheckReceipt, current: Sequence[Candidate]) -> tuple[FieldDiff, ...]:
    previous = {
        evaluation.candidate.repository: evaluation.candidate
        for evaluation in prior.evaluations
        if evaluation.included
    }
    now = {candidate.repository: candidate for candidate in current}
    diffs: list[FieldDiff] = []
    for repository in sorted(set(previous) | set(now)):
        before_candidate = previous.get(repository)
        after_candidate = now.get(repository)
        if before_candidate is None or after_candidate is None:
            diffs.append(
                FieldDiff(
                    repository=repository,
                    field="presence",
                    before=before_candidate is not None,
                    after=after_candidate is not None,
                    materiality=DiffMateriality.MATERIAL_REVIEW,
                    reason="candidate entered or left the exact post-filter result set",
                )
            )
            continue
        before = before_candidate.model_dump(mode="json")
        after = after_candidate.model_dump(mode="json")
        for field in sorted(set(before) | set(after)):
            if field in IGNORED_DIFF_FIELDS or before.get(field) == after.get(field):
                continue
            materiality = (
                DiffMateriality.MATERIAL_REVIEW
                if field in MATERIAL_FIELDS
                else DiffMateriality.REFRESH_ONLY
            )
            diffs.append(
                FieldDiff(
                    repository=repository,
                    field=field,
                    before=before.get(field),
                    after=after.get(field),
                    materiality=materiality,
                    reason=(
                        "field can invalidate a recorded hard gate"
                        if materiality is DiffMateriality.MATERIAL_REVIEW
                        else "volatile evidence refreshed without invalidating a named hard gate"
                    ),
                )
            )
    return tuple(diffs)
