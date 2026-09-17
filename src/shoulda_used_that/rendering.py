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

from shoulda_used_that.curation import CurationSnapshot
from shoulda_used_that.models import CheckReceipt
from shoulda_used_that.project_context import ProjectSnapshot
from shoulda_used_that.projection import GitHubProjectionPlan


class OutputFormat(StrEnum):
    TABLE = "table"
    JSON = "json"
    YAML = "yaml"
    MARKDOWN = "markdown"


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
        table = Table(title=f"{value.check_id} · {value.need}")
        table.add_column("Repository")
        table.add_column("Role")
        table.add_column("License")
        table.add_column("Evidence")
        table.add_column("Result")
        if explain:
            table.add_column("Reasons")
        if value.project_snapshot_id:
            table.add_column("Project context")
        for evaluation in value.evaluations:
            row = [
                evaluation.candidate.repository,
                evaluation.candidate.role,
                evaluation.candidate.license or "unknown",
                evaluation.candidate.evidence_state.value,
                "included" if evaluation.included else "excluded",
            ]
            if explain:
                failed = [reason.reason for reason in evaluation.reasons if not reason.passed]
                row.append("; ".join(failed) or "all predicates passed")
            if value.project_snapshot_id:
                row.append(
                    "; ".join(
                        f"{item.field}:{item.relationship}" for item in evaluation.applicability
                    )
                    or "unavailable"
                )
            table.add_row(*row)
        console.print(table)
        console.print(
            f"visible={value.counts.visible} excluded={value.counts.excluded} "
            f"result={value.result_set_fingerprint}"
            + (f" project={value.project_snapshot_id}" if value.project_snapshot_id else "")
        )
    elif isinstance(value, CurationSnapshot):
        table = Table(title=f"{value.curation_snapshot_id} · {value.profile_id}")
        table.add_column("Repository")
        table.add_column("Disposition")
        table.add_column("Collections")
        table.add_column("Freshness")
        for entry in value.entries:
            table.add_row(
                entry.repository,
                entry.primary_disposition.value,
                ", ".join(entry.collection_memberships),
                entry.freshness_state.value,
            )
        console.print(table)
        console.print(
            f"entries={value.counts.entries} excluded={value.counts.excluded} "
            f"inbox={value.counts.inbox} stale={value.counts.stale} "
            f"result={value.canonical_fingerprint}"
        )
    elif isinstance(value, ProjectSnapshot):
        table = Table(title=f"{value.project_snapshot_id} · {value.target_identity}", min_width=80)
        table.add_column("Evidence")
        table.add_column("Count")
        table.add_row("languages", str(len(value.languages)))
        table.add_row("topics", str(len(value.topics)))
        table.add_row("manifests", str(len(value.manifest_facts)))
        table.add_row("dependency components", str(len(value.dependency_components)))
        table.add_row("typed gaps", str(len(value.evidence_gaps)))
        console.print(table)
        console.print(
            f"files={value.inspected_file_count} bytes={value.inspected_byte_count} "
            f"sbom={value.sbom.format if value.sbom else 'unavailable'} "
            f"result={value.canonical_fingerprint}"
        )
    elif isinstance(value, GitHubProjectionPlan):
        table = Table(title=f"{value.plan_id} · {value.target_account}")
        table.add_column("#", justify="right")
        table.add_column("Additive operation")
        table.add_column("Target")
        table.add_column("Exact detail")
        table.add_column("Memberships preserved")
        for index, operation in enumerate(value.operations, start=1):
            target = operation.repository or operation.list_name or "-"
            detail = (
                operation.list_description
                if operation.kind == "create-list"
                else operation.list_name
                if operation.kind == "add-membership"
                else operation.repository or "-"
            )
            table.add_row(
                str(index),
                operation.kind,
                target,
                detail or "-",
                ", ".join(operation.preserved_list_ids) or "none",
            )
        if not value.operations:
            table.add_row("-", "semantic-no-op", "-", "No additive changes", "all")
        console.print(table)
        console.print(
            f"identity={value.observed_login} capability={value.capability.state.value} "
            f"apply-ready={'yes' if value.apply_ready else 'no'} "
            f"expires={value.expires_at.isoformat()}"
        )
        console.print(
            f"creates={value.operation_counts.create_lists} "
            f"stars={value.operation_counts.star_repositories} "
            f"memberships={value.operation_counts.add_memberships} "
            f"total={value.operation_counts.total}"
        )
        console.print(f"source-state={value.github_state_fingerprint}")
        console.print(f"plan={value.canonical_plan_fingerprint}")
        console.print(f"forbidden={', '.join(value.forbidden_operation_classes)}")
        if value.capability.operator_command:
            console.print(f"operator-action={value.capability.operator_command}")
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


def _markdown(value: BaseModel, payload: dict[str, Any]) -> str:
    lines = [f"# {value.__class__.__name__}", ""]
    if isinstance(value, CheckReceipt):
        lines.extend(
            [
                f"- Check: `{value.check_id}`",
                f"- Need: {value.need}",
                f"- Result fingerprint: `{value.result_set_fingerprint}`",
                f"- Visible: {value.counts.visible}",
                *(
                    [f"- Project context: `{value.project_snapshot_id}`"]
                    if value.project_snapshot_id
                    else []
                ),
                "",
                "| Repository | Role | License | Result |",
                "|---|---|---|---|",
            ]
        )
        for evaluation in value.evaluations:
            candidate = evaluation.candidate
            lines.append(
                f"| `{candidate.repository}` | {candidate.role} | "
                f"{candidate.license or 'unknown'} | "
                f"{'included' if evaluation.included else 'excluded'} |"
            )
    elif isinstance(value, CurationSnapshot):
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
        for entry in value.entries:
            lines.append(
                f"| `{entry.repository}` | {entry.primary_disposition.value} | "
                f"{', '.join(entry.collection_memberships)} | {entry.freshness_state.value} |"
            )
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
        for index, operation in enumerate(value.operations, start=1):
            target = operation.repository or operation.list_name or "-"
            preserved = ", ".join(operation.preserved_list_ids) or "none"
            lines.append(f"| {index} | {operation.kind} | `{target}` | `{preserved}` |")
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
    else:
        for key, item in payload.items():
            rendered = (
                f"`{json.dumps(item, sort_keys=True, ensure_ascii=False)}`"
                if isinstance(item, (dict, list))
                else f"`{item}`"
            )
            lines.append(f"- **{key}:** {rendered}")
    return "\n".join(lines) + "\n"
