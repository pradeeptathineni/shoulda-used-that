"""Explicit allowlisted public summaries; private state is never deny-list exported."""

from __future__ import annotations

from typing import Any

from shoulda_used_that.models import (
    AdoptionPlan,
    CheckReceipt,
    DecisionReceipt,
    ProjectionPlan,
    RecheckReceipt,
    SaveReceipt,
)


def public_summary(
    value: CheckReceipt
    | SaveReceipt
    | DecisionReceipt
    | RecheckReceipt
    | ProjectionPlan
    | AdoptionPlan,
) -> dict[str, Any]:
    """Return only explicitly approved reusable fields for public reporting."""

    if isinstance(value, CheckReceipt):
        return {
            "schema_version": value.schema_version,
            "record_type": "check",
            "check_id": value.check_id,
            "source_snapshot_fingerprint": value.source_snapshot_fingerprint,
            "result_set_fingerprint": value.result_set_fingerprint,
            "counts": value.counts.model_dump(mode="json"),
            "ordering": list(value.ordering),
            "unknown_policy": value.unknown_policy,
        }
    if isinstance(value, SaveReceipt):
        return {
            "schema_version": value.schema_version,
            "record_type": "save",
            "save_id": value.save_id,
            "saved_count": len(value.repositories),
            "source_result_fingerprint": value.source_result_fingerprint,
        }
    if isinstance(value, DecisionReceipt):
        return {
            "schema_version": value.schema_version,
            "record_type": "decision",
            "decision_id": value.decision_id,
            "disposition": value.disposition.value,
            "evidence_count": len(value.evidence_ids),
            "supersedes": value.supersedes,
        }
    if isinstance(value, RecheckReceipt):
        return {
            "schema_version": value.schema_version,
            "record_type": "recheck",
            "recheck_id": value.recheck_id,
            "outcome": value.outcome.value,
            "last_known_good_preserved": value.last_known_good_preserved,
            "diff_count": len(value.diffs),
            "source_error_count": len(value.source_errors),
        }
    if isinstance(value, ProjectionPlan):
        return {
            "schema_version": value.schema_version,
            "record_type": "projection-plan",
            "plan_id": value.plan_id,
            "plan_fingerprint": value.plan_fingerprint,
            "operation_count": len(value.operations),
            "mutation_state": value.mutation_state,
        }
    return {
        "schema_version": value.schema_version,
        "record_type": "adoption-plan",
        "plan_id": value.plan_id,
        "plan_fingerprint": value.plan_fingerprint,
        "postcondition_count": len(value.expected_postconditions),
        "mutation_state": value.mutation_state,
    }
