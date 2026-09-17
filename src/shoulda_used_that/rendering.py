"""Stable machine renderings and concise human renderings."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

import yaml
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from shoulda_used_that.curation import CurationSnapshot
from shoulda_used_that.models import CheckReceipt


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
    console = Console(record=True, force_terminal=False, color_system=None, width=120)
    if isinstance(value, CheckReceipt):
        table = Table(title=f"{value.check_id} · {value.need}")
        table.add_column("Repository")
        table.add_column("Role")
        table.add_column("License")
        table.add_column("Evidence")
        table.add_column("Result")
        if explain:
            table.add_column("Reasons")
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
            table.add_row(*row)
        console.print(table)
        console.print(
            f"visible={value.counts.visible} excluded={value.counts.excluded} "
            f"result={value.result_set_fingerprint}"
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
    else:
        for key, item in payload.items():
            rendered = (
                f"`{json.dumps(item, sort_keys=True, ensure_ascii=False)}`"
                if isinstance(item, (dict, list))
                else f"`{item}`"
            )
            lines.append(f"- **{key}:** {rendered}")
    return "\n".join(lines) + "\n"
