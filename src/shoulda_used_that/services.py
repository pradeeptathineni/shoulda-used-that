"""Deterministic read, research, decision, and recheck workflows."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from shoulda_used_that import __version__
from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.errors import ShouldaError, SourceError, StateError
from shoulda_used_that.filters import evaluate_candidates, normalized_predicate_tree
from shoulda_used_that.github import GhClient
from shoulda_used_that.models import (
    Candidate,
    CandidateEvaluation,
    CheckReceipt,
    DecisionReceipt,
    DiffMateriality,
    Disposition,
    EvidenceState,
    FieldDiff,
    FilterSpec,
    RecheckOutcome,
    RecheckReceipt,
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
from shoulda_used_that.sources import SourceBatch, load_sources, merge_batches
from shoulda_used_that.state import StateStore


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
