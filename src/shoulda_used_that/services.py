"""End-to-end deterministic workflows behind the public CLI."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from shoulda_used_that import __version__
from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.errors import ShouldaError, SourceError, StateError
from shoulda_used_that.filters import evaluate_candidates, normalized_predicate_tree
from shoulda_used_that.github import GhClient
from shoulda_used_that.models import (
    AdoptionPlan,
    Candidate,
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
from shoulda_used_that.sources import SourceBatch, load_sources, merge_batches
from shoulda_used_that.state import StateStore

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
    source_fingerprint = _source_fingerprint(batches)
    seed = {
        "need": need,
        "profile": store.profile,
        "created_at": timestamp.isoformat(),
        "source_snapshot_fingerprint": source_fingerprint,
        "filter_spec": filter_spec.model_dump(mode="json"),
        "result_set_fingerprint": result_fingerprint,
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
        },
        evaluations=evaluations,
        result_repositories=tuple(candidate.repository for candidate in visible),
        result_set_fingerprint=result_fingerprint,
        ordering=(
            *(field for field in filter_spec.sort if field.removeprefix("-") != "repo"),
            "repo",
        ),
        counts=counts,
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

    projection = None
    if list_name:
        if check is None:
            raise StateError(
                code="projection_requires_check",
                message="A List projection must be bound to --all or --from <check_id>.",
            )
        projection = _projection_plan(
            store,
            check=check,
            candidates=tuple(candidates[repository] for repository in normalized),
            list_name=list_name,
            created_at=timestamp,
        )
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
        lkg_preserved = False
        source_fingerprint = _source_identity_from_observations(tuple(observations))
        snapshot_seed = {
            "need": prior.need,
            "profile": store.profile,
            "created_at": timestamp.isoformat(),
            "source_snapshot_fingerprint": source_fingerprint,
            "filter_spec": prior.filter_spec.model_dump(mode="json"),
            "result_set_fingerprint": current_fingerprint,
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
    """Resolve a sealed plan and prove v0.1.0 cannot execute it."""

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
