"""The deterministic ShouldaUsedThat command surface."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

import click
import yaml

from shoulda_used_that import __version__, services
from shoulda_used_that.errors import ShouldaError
from shoulda_used_that.models import (
    Disposition,
    EvidenceState,
    FilterSpec,
    NetworkBoundary,
    SecurityState,
    SourceKind,
    SourceRequest,
)
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.state import StateStore


@dataclass(slots=True)
class Runtime:
    store: StateStore
    output_format: OutputFormat


def _enum_choice(enum_type: type[StrEnum]) -> click.Choice[str]:
    return click.Choice([item.value for item in enum_type], case_sensitive=False)


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=(
        "Start here: check finds options from an explicit source/query plan; inspect opens "
        "evidence for one target; remember records a decision; recheck tells you what changed. "
        "Catalog and GitHub operations are grouped by what they affect."
    ),
)
@click.version_option(version=__version__, prog_name="shoulda")
@click.option(
    "--state-dir",
    type=click.Path(path_type=Path, file_okay=False),
    help="Explicit private state root; defaults to the OS user-data directory.",
)
@click.option("--profile", default="default", show_default=True, help="Isolated state profile.")
@click.option(
    "--format",
    "output_format",
    type=_enum_choice(OutputFormat),
    default=OutputFormat.TABLE.value,
    show_default=True,
    help="Choose a readable table or an authoritative JSON/YAML/Markdown rendering.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    state_dir: Path | None,
    profile: str,
    output_format: str,
) -> None:
    """Find, inspect, decide, and recheck evidence-backed OSS options."""

    ctx.obj = Runtime(
        store=StateStore(state_dir, profile=profile),
        output_format=OutputFormat(output_format),
    )


@cli.command("inspect")
@click.argument("target")
@click.option(
    "--sbom",
    "sbom_path",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Supplied SPDX or CycloneDX document to inspect with the project.",
)
@click.pass_obj
def inspect_command(runtime: Runtime, target: str, sbom_path: Path | None) -> None:
    """Inspect the available evidence for one explicit project."""

    try:
        snapshot = services.inspected(runtime.store, target=target, sbom_path=sbom_path)
        click.echo(render(snapshot, runtime.output_format), nl=False)
    except (ShouldaError, ValueError) as exc:
        _fail(
            runtime,
            exc if isinstance(exc, ShouldaError) else ShouldaError("invalid_input", str(exc)),
        )


@cli.command("check")
@click.argument("need")
@click.option(
    "--source",
    type=_enum_choice(SourceKind),
    multiple=True,
    required=True,
    help="Explicit discovery source; repeat to combine source kinds.",
)
@click.option(
    "--fixture",
    type=click.Path(path_type=Path, dir_okay=False),
    multiple=True,
    help="Public or synthetic fixture file used by --source fixture.",
)
@click.option(
    "--query",
    multiple=True,
    help="Exact GitHub repository-search query; NEED never expands or rewrites it.",
)
@click.option("--repo", multiple=True, help="Exact owner/repo seed.")
@click.option("--role", multiple=True, help="Keep a matching role; repeat for OR within role.")
@click.option(
    "--language", multiple=True, help="Keep a matching language; repeat for OR within language."
)
@click.option(
    "--ecosystem", multiple=True, help="Keep a matching ecosystem; repeat for OR within ecosystem."
)
@click.option("--topic", multiple=True, help="Keep a matching topic; repeat for OR within topic.")
@click.option("--license", "license_allow", multiple=True, help="Allowed SPDX identifier.")
@click.option("--deny-license", "license_deny", multiple=True, help="Denied SPDX identifier.")
@click.option("--not-archived", is_flag=True, help="Require affirmative evidence of not archived.")
@click.option("--maintained-within", type=str, help="Hard freshness gate such as 365d or 12w.")
@click.option("--released-within", type=str, help="Hard release freshness gate such as 365d.")
@click.option("--starred-within", type=str, help="Star-inbox recency filter such as 30d.")
@click.option("--platform", "platforms", multiple=True, help="Keep a matching platform.")
@click.option("--runtime", "runtimes", multiple=True, help="Keep a matching runtime.")
@click.option(
    "--evidence-state",
    type=_enum_choice(EvidenceState),
    multiple=True,
    help="Keep a matching evidence state.",
)
@click.option(
    "--network-boundary",
    type=_enum_choice(NetworkBoundary),
    multiple=True,
    help="Keep a matching network boundary.",
)
@click.option(
    "--security-state",
    type=_enum_choice(SecurityState),
    multiple=True,
    help="Keep a matching security state.",
)
@click.option("--min-stars", type=click.IntRange(min=0), help="Minimum observed GitHub stars.")
@click.option("--where", help="JMESPath expression over the stable canonical candidate view.")
@click.option(
    "--sort",
    "sort_fields",
    multiple=True,
    default=("repo",),
    show_default=True,
    help=(
        "Sort field; prefix with - for descending. Canonical repo is always the final tie-breaker."
    ),
)
@click.option(
    "--limit",
    type=click.IntRange(min=1, max=1000),
    default=5,
    show_default=True,
    help="Maximum visible results after filtering and stable ordering.",
)
@click.option(
    "--explain",
    "--explain-filter",
    "explain_filter",
    is_flag=True,
    help="Show candidate-level filter and limit reasons.",
)
@click.option(
    "--in",
    "project_context",
    help="Explicit psn_ snapshot ID, github:owner/repo target, or local project path.",
)
@click.pass_obj
def check_command(
    runtime: Runtime,
    need: str,
    source: tuple[str, ...],
    fixture: tuple[Path, ...],
    query: tuple[str, ...],
    repo: tuple[str, ...],
    role: tuple[str, ...],
    language: tuple[str, ...],
    ecosystem: tuple[str, ...],
    topic: tuple[str, ...],
    license_allow: tuple[str, ...],
    license_deny: tuple[str, ...],
    not_archived: bool,
    maintained_within: str | None,
    released_within: str | None,
    starred_within: str | None,
    platforms: tuple[str, ...],
    runtimes: tuple[str, ...],
    evidence_state: tuple[str, ...],
    network_boundary: tuple[str, ...],
    security_state: tuple[str, ...],
    min_stars: int | None,
    where: str | None,
    sort_fields: tuple[str, ...],
    limit: int,
    explain_filter: bool,
    project_context: str | None,
) -> None:
    """Find candidates from an explicit source/query plan; NEED is context only."""

    try:
        requests = _source_requests(source, fixture=fixture, query=query, repo=repo)
        filters = FilterSpec(
            roles=role,
            languages=language,
            ecosystems=ecosystem,
            topics=topic,
            license_allow=license_allow,
            license_deny=license_deny,
            not_archived=not_archived,
            maintained_within_days=_duration_days(maintained_within),
            released_within_days=_duration_days(released_within),
            starred_within_days=_duration_days(starred_within),
            platforms=platforms,
            runtimes=runtimes,
            evidence_states=tuple(EvidenceState(value) for value in evidence_state),
            network_boundaries=tuple(NetworkBoundary(value) for value in network_boundary),
            security_states=tuple(SecurityState(value) for value in security_state),
            min_stars=min_stars,
            where=where,
            sort=sort_fields,
            limit=limit,
        )
        project_snapshot = (
            services.resolve_project_context(runtime.store, project_context)
            if project_context
            else None
        )
        receipt = services.checked(
            runtime.store,
            need=need,
            source_requests=requests,
            filter_spec=filters,
            project_snapshot=project_snapshot,
        )
        click.echo(render(receipt, runtime.output_format, explain=explain_filter), nl=False)
    except ShouldaError as exc:
        _fail(runtime, exc)
    except ValueError as exc:
        _fail(runtime, ShouldaError("invalid_input", str(exc)))


@cli.command("remember")
@click.argument("repository")
@click.option(
    "--as",
    "disposition",
    type=_enum_choice(Disposition),
    required=True,
    help="Decision status for this named need.",
)
@click.option("--for", "need", required=True, help="The concrete need this decision addresses.")
@click.option(
    "--because", "rationale", multiple=True, required=True, help="Evidence-bound reason; repeat."
)
@click.option(
    "--evidence", "evidence_ids", multiple=True, help="Supporting receipt or evidence ID; repeat."
)
@click.option(
    "--alternative", "alternatives", multiple=True, help="Alternative considered; repeat."
)
@click.option("--unknown", "unknowns", multiple=True, help="Open uncertainty; repeat.")
@click.option(
    "--reconsider-when",
    multiple=True,
    required=True,
    help="Concrete trigger that reopens the decision; repeat.",
)
@click.option("--from", "from_check_id", help="Check receipt that supplied the candidates.")
@click.option("--supersedes", help="Earlier decision receipt replaced by this judgment.")
@click.pass_obj
def remember_command(
    runtime: Runtime,
    repository: str,
    disposition: str,
    need: str,
    rationale: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    alternatives: tuple[str, ...],
    unknowns: tuple[str, ...],
    reconsider_when: tuple[str, ...],
    from_check_id: str | None,
    supersedes: str | None,
) -> None:
    """Record what you decided, why, and when to reconsider it."""

    try:
        receipt = services.remembered(
            runtime.store,
            repository=repository,
            need=need,
            disposition=Disposition(disposition),
            rationale=rationale,
            evidence_ids=evidence_ids,
            reconsider_when=reconsider_when,
            alternatives=alternatives,
            unknowns=unknowns,
            from_check_id=from_check_id,
            supersedes=supersedes,
        )
        click.echo(render(receipt, runtime.output_format), nl=False)
    except (ShouldaError, ValueError) as exc:
        _fail(
            runtime,
            exc if isinstance(exc, ShouldaError) else ShouldaError("invalid_input", str(exc)),
        )


@cli.command("recheck")
@click.argument("target_id")
@click.pass_obj
def recheck_command(runtime: Runtime, target_id: str) -> None:
    """Repeat the bound check and report meaningful evidence changes."""

    try:
        receipt = services.rechecked(runtime.store, target_id=target_id)
        click.echo(render(receipt, runtime.output_format), nl=False)
    except ShouldaError as exc:
        _fail(runtime, exc)


@cli.group("catalog")
def catalog_group() -> None:
    """Build and export the evidence-backed public catalog."""


@catalog_group.command("build")
@click.argument("profile_path", type=click.Path(path_type=Path, dir_okay=False, exists=True))
@click.pass_obj
def catalog_build_command(runtime: Runtime, profile_path: Path) -> None:
    """Build one exact public profile into a deterministic snapshot."""

    from shoulda_used_that import admin_services

    try:
        snapshot = admin_services.curated(runtime.store, profile_path=profile_path)
        click.echo(render(snapshot, runtime.output_format), nl=False)
    except ShouldaError as exc:
        _fail(runtime, exc)


@catalog_group.command("export")
@click.argument("curation_id")
@click.option(
    "--output",
    type=click.Path(path_type=Path, file_okay=False),
    required=True,
    help="Dedicated generated catalog directory.",
)
@click.pass_obj
def catalog_export_command(
    runtime: Runtime,
    curation_id: str,
    output: Path,
) -> None:
    """Write an allowlisted public catalog from one exact snapshot."""

    from shoulda_used_that import admin_services

    try:
        receipt = admin_services.exported(
            runtime.store,
            curation_snapshot_id=curation_id,
            output=output,
        )
        click.echo(render(receipt, runtime.output_format), nl=False)
    except ShouldaError as exc:
        _fail(runtime, exc)


@cli.group("github")
def github_group() -> None:
    """Plan, apply, and verify additive GitHub curation changes."""


@github_group.command("plan")
@click.argument("curation_id")
@click.option("--account", required=True, help="Exact GitHub login bound by the profile.")
@click.pass_obj
def github_plan_command(
    runtime: Runtime,
    curation_id: str,
    account: str,
) -> None:
    """Prepare an exact additive GitHub plan without changing GitHub."""

    from shoulda_used_that import admin_services

    try:
        plan = admin_services.projected(
            runtime.store,
            curation_snapshot_id=curation_id,
            account=account,
        )
        click.echo(render(plan, runtime.output_format), nl=False)
    except ShouldaError as exc:
        _fail(runtime, exc)


@github_group.command("apply")
@click.argument("plan_id")
@click.option("--fingerprint", required=True, help="Exact canonical plan fingerprint.")
@click.pass_obj
def apply_command(runtime: Runtime, plan_id: str, fingerprint: str) -> None:
    """Run one approved additive GitHub plan in an interactive terminal."""

    from shoulda_used_that import admin_services

    try:
        receipt = admin_services.applied(
            runtime.store,
            plan_id=plan_id,
            fingerprint=fingerprint,
            environment=os.environ,
            stdin_isatty=sys.stdin.isatty(),
        )
        click.echo(render(receipt, runtime.output_format), nl=False)
        if receipt.status.value != "complete":
            raise click.exceptions.Exit(2)
    except ShouldaError as exc:
        _fail(runtime, exc)


@github_group.command("verify")
@click.argument("apply_id")
@click.pass_obj
def verify_command(runtime: Runtime, apply_id: str) -> None:
    """Read GitHub back and verify every claimed postcondition."""

    from shoulda_used_that import admin_services

    try:
        receipt = admin_services.verified(runtime.store, apply_receipt_id=apply_id)
        click.echo(render(receipt, runtime.output_format), nl=False)
        if receipt.status.value != "verified":
            raise click.exceptions.Exit(2)
    except ShouldaError as exc:
        _fail(runtime, exc)


def main() -> None:
    """Console-script entry point."""

    cli()


def _source_requests(
    sources: tuple[str, ...],
    *,
    fixture: tuple[Path, ...],
    query: tuple[str, ...],
    repo: tuple[str, ...],
) -> tuple[SourceRequest, ...]:
    selected = tuple(dict.fromkeys(SourceKind(value) for value in sources))
    requests: list[SourceRequest] = []
    for kind in selected:
        if kind is SourceKind.FIXTURE:
            if not fixture:
                raise ShouldaError(
                    "fixture_required", "--source fixture requires at least one --fixture path."
                )
            requests.extend(SourceRequest(kind=kind, locator=str(path)) for path in fixture)
        elif kind is SourceKind.STARS:
            requests.append(SourceRequest(kind=kind))
        elif kind is SourceKind.GITHUB_SEARCH:
            if not query:
                raise ShouldaError(
                    "query_required", "--source github-search requires at least one --query value."
                )
            requests.extend(SourceRequest(kind=kind, query=value) for value in query)
        elif kind is SourceKind.REPOSITORY:
            if not repo:
                raise ShouldaError(
                    "repository_required",
                    "--source repository requires at least one --repo owner/name.",
                )
            requests.extend(SourceRequest(kind=kind, locator=value) for value in repo)
    if fixture and SourceKind.FIXTURE not in selected:
        raise ShouldaError("unused_fixture", "--fixture requires --source fixture.")
    if query and SourceKind.GITHUB_SEARCH not in selected:
        raise ShouldaError("unused_query", "--query requires --source github-search.")
    if repo and SourceKind.REPOSITORY not in selected:
        raise ShouldaError("unused_repo", "--repo requires --source repository.")
    return tuple(requests)


def _duration_days(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.fullmatch(r"([1-9][0-9]*)([dw])", value.casefold())
    if not match:
        raise ValueError(
            f"Invalid duration '{value}'; use a positive day/week value such as 365d or 12w."
        )
    count = int(match.group(1))
    return count if match.group(2) == "d" else count * 7


def _fail(runtime: Runtime, error: ShouldaError) -> NoReturn:
    payload = {"error": {"code": error.code, "message": error.message, "details": error.details}}
    if runtime.output_format is OutputFormat.JSON:
        click.echo(json.dumps(payload, indent=2, sort_keys=True) + "\n", err=True, nl=False)
    elif runtime.output_format is OutputFormat.YAML:
        click.echo(yaml.safe_dump(payload, sort_keys=False), err=True, nl=False)
    else:
        click.echo(f"Error [{error.code}]: {error.message}", err=True)
    raise click.exceptions.Exit(2)


if __name__ == "__main__":  # pragma: no cover
    main()
