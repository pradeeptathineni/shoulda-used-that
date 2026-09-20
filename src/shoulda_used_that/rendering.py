"""Stable machine renderings and concise human renderings."""

from __future__ import annotations

import json
from enum import StrEnum
from io import StringIO
from typing import Any

import yaml
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from shoulda_used_that.models import (
    CandidateEvaluation,
    CheckReceipt,
    DecisionReceipt,
    RecheckReceipt,
)
from shoulda_used_that.project_context import ProjectSnapshot


class OutputFormat(StrEnum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"


LOCAL_WORKFLOW_TYPES = (
    DecisionReceipt,
    RecheckReceipt,
)


def render(value: BaseModel, output_format: OutputFormat, *, explain: bool = False) -> str:
    """Render a validated model without changing its semantic content."""

    payload = value.model_dump(mode="json")
    if output_format is OutputFormat.JSON:
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output_format is OutputFormat.YAML:
        return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    if output_format is OutputFormat.MARKDOWN:
        return _markdown(value, payload)
    return _table(value, payload, explain=explain)


def _table(value: BaseModel, payload: dict[str, Any], *, explain: bool) -> str:
    console = Console(
        record=True,
        file=StringIO(),
        force_terminal=False,
        color_system=None,
        width=120,
    )
    if isinstance(value, CheckReceipt):
        _check_table(value, console, explain=explain)
    elif isinstance(value, LOCAL_WORKFLOW_TYPES):
        _local_workflow_table(value, console)
    elif isinstance(value, ProjectSnapshot):
        table = Table(title=f"Evidence for {value.target_identity}", min_width=80)
        table.add_column("Evidence")
        table.add_column("Observed value")
        if value.repository_metadata is not None:
            table.add_row("license", value.repository_metadata.license or "unknown")
            table.add_row("archived", str(value.repository_metadata.archived).lower())
            table.add_row("default branch", value.repository_metadata.default_branch)
        table.add_row("languages", ", ".join(item.name for item in value.languages) or "unknown")
        table.add_row("ecosystems", ", ".join(value.ecosystems) or "unknown")
        table.add_row(
            "typed evidence gaps",
            "; ".join(item.subject for item in value.evidence_gaps) or "none",
        )
        console.print(table)
        console.print(
            f"Use in a check: --in {value.project_snapshot_id} · "
            "Full source, manifest, and SBOM evidence: --format json"
        )
    elif _admin_table(value, console):
        pass
    else:
        table = Table(title=value.__class__.__name__)
        table.add_column("Field")
        table.add_column("Value")
        for key, item in payload.items():
            if isinstance(item, (dict, list)):
                rendered = json.dumps(item, sort_keys=True, ensure_ascii=False)
            else:
                rendered = str(item)
            table.add_row(key, rendered)
        console.print(table)
    return console.export_text(styles=False)


def _admin_table(value: BaseModel, console: Console) -> bool:
    """Render maintainer records without importing their modules on the public path."""

    from shoulda_used_that.curation import (
        CurationSnapshot,
        curation_projection_entries,
        repository_evidence_records,
    )
    from shoulda_used_that.github_apply import ApplyReceipt, VerifyReceipt
    from shoulda_used_that.projection import GitHubProjectionPlan
    from shoulda_used_that.public_export import PublicCatalogExport

    if isinstance(value, CurationSnapshot):
        table = Table(title=f"{value.curation_snapshot_id} · {value.profile_id}")
        table.add_column("Repository")
        table.add_column("Disposition")
        table.add_column("Collections")
        table.add_column("Freshness")
        freshness_by_repository = {
            item.repository: item.freshness_state.value
            for item in repository_evidence_records(value)
        }
        for entry in curation_projection_entries(value):
            table.add_row(
                entry.repository,
                entry.primary_disposition.value,
                ", ".join(entry.collection_memberships),
                freshness_by_repository[entry.repository],
            )
        console.print(table)
        console.print(
            f"Entries: {value.counts.entries} · Excluded: {value.counts.excluded} · "
            f"Inbox: {value.counts.inbox} · Stale: {value.counts.stale}"
        )
        console.print(f"Snapshot fingerprint: {value.canonical_fingerprint}")
    elif isinstance(value, GitHubProjectionPlan):
        table = Table(title=f"{value.plan_id} · {value.target_account}")
        table.add_column("#", justify="right")
        table.add_column("Additive operation")
        table.add_column("Target")
        table.add_column("Exact detail")
        table.add_column("Memberships preserved")
        for index, projection_operation in enumerate(value.operations, start=1):
            target = projection_operation.repository or projection_operation.list_name or "-"
            detail = (
                projection_operation.list_description
                if projection_operation.kind == "create-list"
                else projection_operation.list_name
                if projection_operation.kind == "add-membership"
                else projection_operation.repository or "-"
            )
            table.add_row(
                str(index),
                projection_operation.kind,
                target,
                detail or "-",
                ", ".join(projection_operation.preserved_list_ids) or "none",
            )
        if not value.operations:
            table.add_row("-", "semantic-no-op", "-", "No additive changes", "all")
        console.print(table)
        console.print(
            f"Account: {value.observed_login} · Capability: {value.capability.state.value} · "
            f"Ready to apply: {'yes' if value.apply_ready else 'no'} · "
            f"Expires: {value.expires_at.isoformat()}"
        )
        console.print(
            f"Create Lists: {value.operation_counts.create_lists} · "
            f"Star repositories: {value.operation_counts.star_repositories} · "
            f"Add memberships: {value.operation_counts.add_memberships} · "
            f"Total operations: {value.operation_counts.total}"
        )
        console.print(f"Source-state fingerprint: {value.github_state_fingerprint}")
        console.print(f"Plan fingerprint: {value.canonical_plan_fingerprint}")
        console.print(f"Forbidden operations: {', '.join(value.forbidden_operation_classes)}")
        if value.capability.operator_command:
            console.print(f"Operator action required: {value.capability.operator_command}")
    elif isinstance(value, ApplyReceipt):
        table = Table(title=f"{value.apply_receipt_id} · {value.status.value}")
        table.add_column("Attempt")
        table.add_column("Operation")
        table.add_column("Outcome")
        table.add_column("Readback")
        table.add_column("Error")
        for apply_operation in value.operation_receipts:
            table.add_row(
                str(apply_operation.attempt),
                apply_operation.request_kind,
                apply_operation.outcome.value,
                (
                    "satisfied"
                    if apply_operation.readback_satisfied is True
                    else "not-satisfied"
                    if apply_operation.readback_satisfied is False
                    else "pending"
                ),
                apply_operation.error_code or "-",
            )
        console.print(table)
        console.print(
            f"Plan: {value.plan_id} · Resume from: {value.resume_cursor or 'none'} · "
            f"Failure: {value.failure_code or 'none'}"
        )
        console.print(f"Receipt fingerprint: {value.canonical_fingerprint}")
    elif isinstance(value, VerifyReceipt):
        table = Table(title=f"{value.verify_receipt_id} · {value.status.value}")
        table.add_column("Postcondition")
        table.add_column("Subject")
        table.add_column("Expected")
        table.add_column("Actual")
        table.add_column("State")
        for condition in value.postconditions:
            table.add_row(
                condition.kind,
                condition.subject,
                condition.expected,
                condition.actual or "unavailable",
                condition.state.value,
            )
        console.print(table)
        console.print(f"Observed login: {value.observed_login or 'unavailable'}")
        console.print(f"Receipt fingerprint: {value.canonical_fingerprint}")
    elif isinstance(value, PublicCatalogExport):
        table = Table(title=f"{value.export_id} · public catalog ready")
        table.add_column("Public result")
        table.add_column("Count or state")
        table.add_row("Prior-art briefs", str(len(value.briefs)))
        table.add_row("Assessed relations", str(len(value.assessments)))
        table.add_row("Safe corpus records", str(len(value.exported_records)))
        table.add_row("Excluded candidates", str(len(value.excluded_candidates)))
        table.add_row("Generated files", str(len(value.generated_file_manifest) + 1))
        table.add_row("Reproducibility", value.reproducibility_status)
        table.add_row("Renderer", value.renderer_version)
        console.print(table)
        console.print(
            "Private field classes omitted: "
            f"{sum(value.omitted_private_field_counts.values())} · "
            f"Catalog fingerprint: {value.canonical_fingerprint}"
        )
    else:
        return False
    return True


def _check_table(value: CheckReceipt, console: Console, *, explain: bool) -> None:
    table = Table(title=f"Options for: {value.need}")
    table.add_column("Repository", min_width=28, no_wrap=True)
    for heading in ("Description", "Evidence", "Upstream position"):
        table.add_column(heading)
    if explain:
        table.add_column("Why included")
    if value.project_snapshot_id:
        table.add_column("Project context")
    evaluation_by_repository = {
        evaluation.candidate.repository: evaluation for evaluation in value.evaluations
    }
    visible_evaluations = tuple(
        evaluation_by_repository[repository] for repository in value.result_repositories
    )
    for evaluation in visible_evaluations:
        source_rank = ", ".join(
            f"{item.source} #{item.rank}" for item in evaluation.candidate.source_ranks
        )
        row = [
            evaluation.candidate.repository,
            evaluation.candidate.description or "No description supplied.",
            evaluation.candidate.evidence_state.value,
            source_rank or "not supplied",
        ]
        if explain:
            failed = [reason.reason for reason in evaluation.reasons if not reason.passed]
            row.append("; ".join(failed) or "all predicates passed")
        if value.project_snapshot_id:
            row.append(
                "; ".join(f"{item.field}:{item.relationship}" for item in evaluation.applicability)
                or "unavailable"
            )
        table.add_row(*row)
    if not visible_evaluations:
        empty = ["none", "No candidate survived the explicit plan.", "-", "-"]
        if explain:
            empty.append("see diagnosis below")
        if value.project_snapshot_id:
            empty.append("-")
        table.add_row(*empty)
    console.print(table)
    predicate_excluded = tuple(
        evaluation
        for evaluation in value.evaluations
        if not evaluation.included
        and not any(reason.field == "limit" for reason in evaluation.reasons)
    )
    limit_excluded = tuple(
        evaluation
        for evaluation in value.evaluations
        if any(not reason.passed and reason.field == "limit" for reason in evaluation.reasons)
    )
    console.print(
        f"Visible: {value.counts.visible} · Filtered or gated: {len(predicate_excluded)} · "
        f"Outside limit: {len(limit_excluded)}"
        + (f" · Project context: {value.project_snapshot_id}" if value.project_snapshot_id else "")
    )
    console.print(
        f"Plan: {len(value.source_requests)} explicit source request(s); "
        "NEED is context only and never expands a query."
    )
    if not visible_evaluations:
        console.print(_zero_result_diagnosis(value, predicate_excluded))
    elif value.result_repositories:
        console.print(f"Inspect: shoulda inspect github:{value.result_repositories[0]}")
    if explain and (predicate_excluded or limit_excluded):
        _excluded_table((*predicate_excluded, *limit_excluded), console)


def _excluded_table(evaluations: tuple[CandidateEvaluation, ...], console: Console) -> None:
    details = Table(title="Excluded candidates")
    for heading in ("Repository", "Stage", "Reason"):
        details.add_column(heading)
    for evaluation in evaluations:
        failures = tuple(reason for reason in evaluation.reasons if not reason.passed)
        stage = (
            "limit"
            if any(reason.field == "limit" for reason in failures)
            else "hard gate"
            if any(reason.category == "hard-gate" for reason in failures)
            else "filter"
        )
        details.add_row(
            evaluation.candidate.repository,
            stage,
            "; ".join(reason.reason for reason in failures),
        )
    console.print(details)


def _zero_result_diagnosis(
    value: CheckReceipt, predicate_excluded: tuple[CandidateEvaluation, ...]
) -> str:
    if value.counts.deduplicated == 0:
        return (
            "Zero-result diagnosis: the explicit sources returned no candidates. "
            "Review --source, --query, --repo, or fixture input; nothing was broadened."
        )
    missing_required_evidence = sum(
        any(
            not reason.passed and reason.category == "hard-gate" and reason.unknown
            for reason in evaluation.reasons
        )
        for evaluation in predicate_excluded
    )
    if missing_required_evidence:
        return (
            "Zero-result diagnosis: "
            f"{missing_required_evidence} candidate(s) lacked required hard-gate evidence. "
            "Use --explain to inspect the missing facts; nothing was broadened."
        )
    return (
        "Zero-result diagnosis: every source candidate was removed by the explicit gates or "
        "filters. Use --explain to inspect reasons or edit the research plan; nothing was "
        "broadened."
    )


def _local_workflow_table(value: BaseModel, console: Console) -> None:
    """Render the smaller local workflow records without exposing model field dumps."""

    if isinstance(value, DecisionReceipt):
        table = Table(title=f"{value.decision_id} · {value.repository}")
        table.add_column("Decision detail")
        table.add_column("Recorded value")
        table.add_row("Need", value.need)
        table.add_row("Status", value.disposition.value)
        table.add_row("Why", "; ".join(value.rationale))
        table.add_row("Evidence", "; ".join(value.evidence_ids) or "none recorded")
        table.add_row("Alternatives", "; ".join(value.alternatives) or "none recorded")
        table.add_row("Unknowns", "; ".join(value.unknowns) or "none recorded")
        table.add_row("Reconsider when", "; ".join(value.reconsider_when))
        table.add_row("Supersedes", value.supersedes or "nothing")
        console.print(table)
        console.print("Stored as an immutable local decision receipt.")
    elif isinstance(value, RecheckReceipt):
        table = Table(title=f"{value.recheck_id} · {value.outcome.value}")
        table.add_column("Repository")
        table.add_column("Changed field")
        table.add_column("Materiality")
        table.add_column("Why it matters")
        for difference in value.diffs:
            table.add_row(
                difference.repository,
                difference.field,
                difference.materiality.value,
                difference.reason,
            )
        if not value.diffs:
            table.add_row("none", "none", "no difference", "No typed differences found.")
        console.print(table)
        console.print(
            f"Last-known-good preserved: {'yes' if value.last_known_good_preserved else 'no'} · "
            f"Source errors: {'; '.join(value.source_errors) or 'none'}"
        )
    else:  # pragma: no cover - guarded by LOCAL_WORKFLOW_TYPES
        raise TypeError(f"unsupported local workflow record: {type(value).__name__}")


def _markdown(value: BaseModel, payload: dict[str, Any]) -> str:
    lines = [f"# {value.__class__.__name__}", ""]
    if isinstance(value, CheckReceipt):
        evaluation_by_repository = {
            evaluation.candidate.repository: evaluation for evaluation in value.evaluations
        }
        visible_evaluations = tuple(
            evaluation_by_repository[repository] for repository in value.result_repositories
        )
        predicate_excluded = tuple(
            evaluation
            for evaluation in value.evaluations
            if not evaluation.included
            and not any(reason.field == "limit" for reason in evaluation.reasons)
        )
        limit_excluded = tuple(
            evaluation
            for evaluation in value.evaluations
            if any(not reason.passed and reason.field == "limit" for reason in evaluation.reasons)
        )
        lines.extend(
            [
                f"- Check: `{value.check_id}`",
                f"- Problem context: {value.need}",
                f"- Visible: {value.counts.visible}",
                f"- Filtered or gated: {len(predicate_excluded)}",
                f"- Outside limit: {len(limit_excluded)}",
                "- Query behavior: explicit sources only; problem context never expands queries",
                *(
                    [f"- Project context: `{value.project_snapshot_id}`"]
                    if value.project_snapshot_id
                    else []
                ),
                "",
                "| Repository | Description | Evidence | Upstream position |",
                "|---|---|---|---|",
            ]
        )
        for evaluation in visible_evaluations:
            candidate = evaluation.candidate
            description = candidate.description or "No description supplied."
            source_rank = ", ".join(
                f"{item.source} #{item.rank}" for item in candidate.source_ranks
            )
            lines.append(
                f"| `{candidate.repository}` | {description} | "
                f"{candidate.evidence_state.value} | {source_rank or 'not supplied'} |"
            )
        if not visible_evaluations:
            lines.extend(["| none | No candidate survived the explicit plan. | - | - |", ""])
            lines.append(_zero_result_diagnosis(value, predicate_excluded))
        elif value.result_repositories:
            lines.extend(["", f"Inspect: `shoulda inspect github:{value.result_repositories[0]}`"])
    elif isinstance(value, LOCAL_WORKFLOW_TYPES):
        lines.extend(_local_workflow_markdown(value))
    elif isinstance(value, ProjectSnapshot):
        lines.extend(
            [
                f"- Snapshot: `{value.project_snapshot_id}`",
                f"- Target: `{value.target_identity}`",
                f"- Canonical fingerprint: `{value.canonical_fingerprint}`",
                f"- Manifests: {len(value.manifest_facts)}",
                f"- Dependency components: {len(value.dependency_components)}",
                f"- Evidence gaps: {len(value.evidence_gaps)}",
                "",
                "| Ecosystem | Manifest | Kind |",
                "|---|---|---|",
            ]
        )
        for manifest in value.manifest_facts:
            lines.append(
                f"| {manifest.ecosystem} | `{manifest.relative_path}` | {manifest.manifest_kind} |"
            )
    else:
        admin_lines = _admin_markdown(value)
        if admin_lines is not None:
            lines.extend(admin_lines)
        else:
            for key, item in payload.items():
                rendered = (
                    f"`{json.dumps(item, sort_keys=True, ensure_ascii=False)}`"
                    if isinstance(item, (dict, list))
                    else f"`{item}`"
                )
                lines.append(f"- **{key}:** {rendered}")
    return "\n".join(lines) + "\n"


def _admin_markdown(value: BaseModel) -> list[str] | None:
    """Return maintainer Markdown without loading admin modules for public records."""

    from shoulda_used_that.curation import (
        CurationSnapshot,
        curation_projection_entries,
        repository_evidence_records,
    )
    from shoulda_used_that.github_apply import ApplyReceipt, VerifyReceipt
    from shoulda_used_that.projection import GitHubProjectionPlan
    from shoulda_used_that.public_export import PublicCatalogExport

    lines: list[str] = []
    if isinstance(value, CurationSnapshot):
        lines.extend(
            [
                f"- Snapshot: `{value.curation_snapshot_id}`",
                f"- Profile: `{value.profile_id}`",
                f"- Canonical fingerprint: `{value.canonical_fingerprint}`",
                f"- Entries: {value.counts.entries}",
                f"- Excluded: {value.counts.excluded}",
                "",
                "| Repository | Disposition | Collections | Freshness |",
                "|---|---|---|---|",
            ]
        )
        freshness_by_repository = {
            item.repository: item.freshness_state.value
            for item in repository_evidence_records(value)
        }
        for entry in curation_projection_entries(value):
            lines.append(
                f"| `{entry.repository}` | {entry.primary_disposition.value} | "
                f"{', '.join(entry.collection_memberships)} | "
                f"{freshness_by_repository[entry.repository]} |"
            )
    elif isinstance(value, GitHubProjectionPlan):
        lines.extend(
            [
                f"- Plan: `{value.plan_id}`",
                f"- Target: `{value.target_account}` (`{value.observed_account_node_id}`)",
                f"- Source state: `{value.github_state_fingerprint}`",
                f"- Capability: {value.capability.state.value}",
                f"- Apply ready: {'yes' if value.apply_ready else 'no'}",
                f"- Expires: `{value.expires_at.isoformat()}`",
                f"- Plan fingerprint: `{value.canonical_plan_fingerprint}`",
                "",
                "| # | Additive operation | Target | Preserved List IDs |",
                "|---:|---|---|---|",
            ]
        )
        for index, projection_operation in enumerate(value.operations, start=1):
            target = projection_operation.repository or projection_operation.list_name or "-"
            preserved = ", ".join(projection_operation.preserved_list_ids) or "none"
            lines.append(f"| {index} | {projection_operation.kind} | `{target}` | `{preserved}` |")
        if not value.operations:
            lines.append("| - | semantic-no-op | - | all |")
        lines.extend(
            [
                "",
                "## Intentionally forbidden",
                "",
                *[f"- {item}" for item in value.forbidden_operation_classes],
            ]
        )
        if value.capability.operator_command:
            lines.extend(
                [
                    "",
                    "## Operator action required",
                    "",
                    f"`{value.capability.operator_command}`",
                ]
            )
    elif isinstance(value, ApplyReceipt):
        lines.extend(
            [
                f"- Apply receipt: `{value.apply_receipt_id}`",
                f"- Plan: `{value.plan_id}`",
                f"- Status: {value.status.value}",
                f"- Resume cursor: `{value.resume_cursor or 'none'}`",
                f"- Fingerprint: `{value.canonical_fingerprint}`",
                "",
                "| Operation | Attempt | Outcome | Error |",
                "|---|---:|---|---|",
            ]
        )
        for apply_operation in value.operation_receipts:
            lines.append(
                f"| {apply_operation.request_kind} | {apply_operation.attempt} | "
                f"{apply_operation.outcome.value} | {apply_operation.error_code or '-'} |"
            )
    elif isinstance(value, VerifyReceipt):
        lines.extend(
            [
                f"- Verify receipt: `{value.verify_receipt_id}`",
                f"- Apply receipt: `{value.apply_receipt_id}`",
                f"- Status: {value.status.value}",
                f"- Observed login: `{value.observed_login or 'unavailable'}`",
                (f"- Observed account node: `{value.observed_account_node_id or 'unavailable'}`"),
                f"- Fingerprint: `{value.canonical_fingerprint}`",
                "",
                "| Postcondition | Subject | State |",
                "|---|---|---|",
            ]
        )
        for condition in value.postconditions:
            lines.append(f"| {condition.kind} | `{condition.subject}` | {condition.state.value} |")
    elif isinstance(value, PublicCatalogExport):
        return [
            f"- Public export: `{value.export_id}`",
            f"- Prior-art briefs: {len(value.briefs)}",
            f"- Assessed relations: {len(value.assessments)}",
            f"- Safe corpus records: {len(value.exported_records)}",
            f"- Excluded candidates: {len(value.excluded_candidates)}",
            f"- Generated files: {len(value.generated_file_manifest) + 1}",
            f"- Reproducibility: {value.reproducibility_status}",
            f"- Renderer: `{value.renderer_version}`",
            f"- Private field classes omitted: {sum(value.omitted_private_field_counts.values())}",
            f"- Catalog fingerprint: `{value.canonical_fingerprint}`",
        ]
    else:
        return None
    return lines


def _local_workflow_markdown(value: BaseModel) -> list[str]:
    """Return reader-facing Markdown for local workflow records."""

    if isinstance(value, DecisionReceipt):
        return [
            f"- Decision: `{value.decision_id}`",
            f"- Repository: `{value.repository}`",
            f"- Need: {value.need}",
            f"- Status: {value.disposition.value}",
            f"- Why: {'; '.join(value.rationale)}",
            f"- Evidence: {'; '.join(value.evidence_ids) or 'none recorded'}",
            f"- Alternatives: {'; '.join(value.alternatives) or 'none recorded'}",
            f"- Unknowns: {'; '.join(value.unknowns) or 'none recorded'}",
            f"- Reconsider when: {'; '.join(value.reconsider_when)}",
            f"- Supersedes: `{value.supersedes or 'nothing'}`",
            "",
            "Stored as an immutable local decision receipt.",
        ]
    if isinstance(value, RecheckReceipt):
        lines = [
            f"- Recheck: `{value.recheck_id}`",
            f"- Outcome: {value.outcome.value}",
            f"- Last-known-good preserved: {'yes' if value.last_known_good_preserved else 'no'}",
            f"- Source errors: {'; '.join(value.source_errors) or 'none'}",
            "",
            "| Repository | Changed field | Materiality | Why it matters |",
            "|---|---|---|---|",
        ]
        lines.extend(
            f"| `{difference.repository}` | {difference.field} | "
            f"{difference.materiality.value} | {difference.reason} |"
            for difference in value.diffs
        )
        if not value.diffs:
            lines.append("| none | none | no difference | No typed differences found. |")
        return lines
    raise TypeError(f"unsupported local workflow record: {type(value).__name__}")
