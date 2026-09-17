"""Allowlisted, deterministic public catalog export and transactional publication."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal
from urllib.parse import quote

from pydantic import Field, field_validator, model_validator

from shoulda_used_that.canonical import canonical_bytes, digest, short_id
from shoulda_used_that.curation import (
    CollectionDefinition,
    CurationDisposition,
    CurationEntry,
    CurationProfile,
    CurationSnapshot,
    CurationVisibility,
    ExcludedCandidate,
    FreshnessState,
    PopularitySnapshot,
    SourceProvenance,
    validate_curation_profile,
    validate_curation_snapshot,
)
from shoulda_used_that.errors import StateError
from shoulda_used_that.models import FrozenModel

PUBLIC_EXPORT_SCHEMA_VERSION: Literal["2.0"] = "2.0"
PUBLIC_ALLOWLIST_SCHEMA_VERSION: Literal["1.0"] = "1.0"
PUBLIC_RENDERER_VERSION = "shoulda-public-catalog/2.0"
MANIFEST_NAME = "manifest.json"

PRIVATE_FIELD_CLASSES = (
    "credentials",
    "local_paths",
    "non_public_collections",
    "private_notes",
    "private_repositories",
    "raw_api_responses",
    "scope_details",
    "unreviewed_model_output",
)

DISPOSITION_LABELS = {
    CurationDisposition.ADOPT: "Used here",
    CurationDisposition.TRIAL: "Trialing",
    CurationDisposition.REFERENCE: "Reference",
    CurationDisposition.LEARN: "Learn",
    CurationDisposition.WATCH: "Watch",
    CurationDisposition.REJECT: "Rejected / deferred",
    CurationDisposition.BUILD: "Built here",
    CurationDisposition.INBOX: "Inbox",
}

DISPOSITION_MEANINGS = {
    CurationDisposition.ADOPT: "Confirmed by repository evidence for the named role.",
    CurationDisposition.TRIAL: "A bounded evaluation with an explicit removal trigger.",
    CurationDisposition.REFERENCE: (
        "Recommended only as a reference for this named need, not as a universal best choice."
    ),
    CurationDisposition.LEARN: "Kept for educational value without an integration claim.",
    CurationDisposition.WATCH: "Not selected; a concrete future trigger can reopen the decision.",
    CurationDisposition.REJECT: (
        "Considered and not selected for this context; the reason is evidence-bound."
    ),
    CurationDisposition.BUILD: "The residual capability this repository deliberately owns.",
    CurationDisposition.INBOX: "Discovered or bookmarked but not yet reviewed.",
}

TOOLCHAIN_GROUPS = (
    (
        "Runtime",
        "Click, Pydantic, JMESPath, platformdirs, PyYAML, Rich, and rfc8785",
        "../decisions/dependencies.json",
    ),
    (
        "Development",
        "uv, pytest, Hypothesis, coverage.py, Ruff, strict mypy, pre-commit, and Vale",
        "../architecture/dogfood-reuse-audit.md",
    ),
    (
        "CI",
        "GitHub Actions, checkout, setup-uv, and tested distribution artifacts",
        "../architecture/dogfood-reuse-audit.md",
    ),
    (
        "Security",
        "pip-audit, CodeQL, dependency review, actionlint, zizmor, and Scorecard",
        "../decisions/quality-security.json",
    ),
    (
        "Docs",
        "Generated Markdown/JSON, First Reader, local ZeroSlop checks, Vale, typos, lychee, and Zensical",
        "../decisions/public-writing-v0.3.json",
    ),
    (
        "Release",
        "Hatchling, CycloneDX, checksums, GitHub Releases, and artifact attestations",
        "../decisions/sbom-release.json",
    ),
)

LOCAL_PATH_PATTERN = re.compile(
    rb"(?:/(?:Users|home)/[^/\s]+|/(?:private|tmp|var/folders|Volumes)/[^\s)\]}>]+|[A-Za-z]:\\Users\\[^\\\s]+)"
)
SECRET_PATTERN = re.compile(
    rb"(?i)(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]{8,}|glpat-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{16}|bearer\s+[A-Za-z0-9._-]+|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


class PublicCollection(FrozenModel):
    slug: str
    title: str
    description: str
    aliases: tuple[str, ...]
    semantics: str
    inclusion_rule: str
    exclusion_rule: str
    github_list_projection: bool
    reconsideration_cadence_days: int


class PublicCatalogRecord(FrozenModel):
    repository: str
    url: str
    description: str
    collections: tuple[str, ...]
    disposition: CurationDisposition
    disposition_label: str
    role: str
    need: str
    rationale: str
    decision_receipt_ids: tuple[str, ...]
    evidence_receipt_ids: tuple[str, ...]
    observed_license: str | None
    archived: bool | None
    latest_release: str | None
    latest_commit: str | None
    popularity: PopularitySnapshot
    last_checked_at: str
    freshness_state: FreshnessState
    reconsideration_trigger: str
    source_provenance: tuple[SourceProvenance, ...]
    attribution_obligations: tuple[str, ...]


class PublicAttribution(FrozenModel):
    repository: str
    observed_license: str | None
    source_locators: tuple[str, ...]
    obligations: tuple[str, ...]


class GeneratedFileDigest(FrozenModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def portable_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or not value or ".." in path.parts or "\\" in value:
            raise ValueError("generated file paths must be portable and relative")
        return value


class PublicCatalogExport(FrozenModel):
    schema_version: Literal["2.0"] = PUBLIC_EXPORT_SCHEMA_VERSION
    export_id: str = Field(pattern=r"^pcx_[0-9a-f]{24}$")
    source_curation_snapshot_id: str = Field(pattern=r"^cur_[0-9a-f]{24}$")
    source_curation_fingerprint: str = Field(pattern=r"^curation_[0-9a-f]{64}$")
    source_profile_fingerprint: str = Field(pattern=r"^profile_[0-9a-f]{64}$")
    allowlist_schema_version: Literal["1.0"] = PUBLIC_ALLOWLIST_SCHEMA_VERSION
    title: str
    description: str
    public_owner_identity: str
    generated_at: str
    popularity_treatment: str
    non_ranking_disclaimer: str
    collections: tuple[PublicCollection, ...]
    exported_records: tuple[PublicCatalogRecord, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...]
    omitted_private_field_counts: dict[str, int]
    license_attribution_inventory: tuple[PublicAttribution, ...]
    generated_file_manifest: tuple[GeneratedFileDigest, ...]
    renderer_version: str
    reproducibility_status: Literal["verified-deterministic"]
    canonical_fingerprint: str = Field(pattern=r"^public_[0-9a-f]{64}$")

    @model_validator(mode="after")
    def export_is_coherent(self) -> PublicCatalogExport:
        if set(self.omitted_private_field_counts) != set(PRIVATE_FIELD_CLASSES):
            raise ValueError("private-field count classes do not match the export allowlist")
        if any(value < 0 for value in self.omitted_private_field_counts.values()):
            raise ValueError("private-field counts cannot be negative")
        if tuple(item.repository for item in self.exported_records) != tuple(
            sorted(item.repository for item in self.exported_records)
        ):
            raise ValueError("public catalog records must use canonical repository order")
        paths = tuple(item.path for item in self.generated_file_manifest)
        if paths != tuple(sorted(set(paths))) or MANIFEST_NAME in paths:
            raise ValueError("generated file manifest must be unique, sorted, and non-recursive")
        semantic = self.model_dump(mode="json", exclude={"export_id", "canonical_fingerprint"})
        if self.canonical_fingerprint != digest(semantic, prefix="public"):
            raise ValueError("public export fingerprint does not match its content")
        if self.export_id != short_id(semantic, prefix="pcx"):
            raise ValueError("public export ID does not match its content")
        return self


def render_public_catalog(
    snapshot: CurationSnapshot,
    profile: CurationProfile,
) -> tuple[PublicCatalogExport, dict[str, bytes]]:
    """Render a complete public package from explicit allowlisted fields only."""

    _validate_public_inputs(snapshot, profile)
    collections = tuple(
        _public_collection(item)
        for item in sorted(snapshot.collection_definitions, key=lambda item: item.slug)
        if item.public_site_visibility
    )
    visible_collection_slugs = frozenset(item.slug for item in collections)
    records = tuple(_public_record(item, visible_collection_slugs) for item in snapshot.entries)
    excluded = tuple(sorted(snapshot.excluded_candidates, key=lambda item: item.repository))
    attributions = tuple(
        PublicAttribution(
            repository=record.repository,
            observed_license=record.observed_license,
            source_locators=tuple(sorted({source.locator for source in record.source_provenance})),
            obligations=record.attribution_obligations,
        )
        for record in records
    )
    files = _render_files(snapshot, profile, collections, records, excluded, attributions)
    file_manifest = tuple(
        GeneratedFileDigest(
            path=path,
            sha256=hashlib.sha256(payload).hexdigest(),
            bytes=len(payload),
        )
        for path, payload in sorted(files.items())
    )
    omitted_counts = dict.fromkeys(PRIVATE_FIELD_CLASSES, 0)
    omitted_counts["non_public_collections"] = sum(
        slug not in visible_collection_slugs
        for entry in snapshot.entries
        for slug in entry.collection_memberships
    )
    semantic: dict[str, Any] = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "source_curation_snapshot_id": snapshot.curation_snapshot_id,
        "source_curation_fingerprint": snapshot.canonical_fingerprint,
        "source_profile_fingerprint": profile.canonical_fingerprint,
        "allowlist_schema_version": PUBLIC_ALLOWLIST_SCHEMA_VERSION,
        "title": profile.title,
        "description": profile.description,
        "public_owner_identity": profile.public_owner_identity,
        "generated_at": snapshot.compiled_at.isoformat(),
        "popularity_treatment": profile.popularity_treatment,
        "non_ranking_disclaimer": profile.non_ranking_disclaimer,
        "collections": [item.model_dump(mode="json") for item in collections],
        "exported_records": [item.model_dump(mode="json") for item in records],
        "excluded_candidates": [item.model_dump(mode="json") for item in excluded],
        "omitted_private_field_counts": omitted_counts,
        "license_attribution_inventory": [item.model_dump(mode="json") for item in attributions],
        "generated_file_manifest": [item.model_dump(mode="json") for item in file_manifest],
        "renderer_version": PUBLIC_RENDERER_VERSION,
        "reproducibility_status": "verified-deterministic",
    }
    export = PublicCatalogExport(
        export_id=short_id(semantic, prefix="pcx"),
        source_curation_snapshot_id=snapshot.curation_snapshot_id,
        source_curation_fingerprint=snapshot.canonical_fingerprint,
        source_profile_fingerprint=profile.canonical_fingerprint,
        title=profile.title,
        description=profile.description,
        public_owner_identity=profile.public_owner_identity,
        generated_at=snapshot.compiled_at.isoformat(),
        popularity_treatment=profile.popularity_treatment,
        non_ranking_disclaimer=profile.non_ranking_disclaimer,
        collections=collections,
        exported_records=records,
        excluded_candidates=excluded,
        omitted_private_field_counts=omitted_counts,
        license_attribution_inventory=attributions,
        generated_file_manifest=file_manifest,
        renderer_version=PUBLIC_RENDERER_VERSION,
        reproducibility_status="verified-deterministic",
        canonical_fingerprint=digest(semantic, prefix="public"),
    )
    files[MANIFEST_NAME] = canonical_bytes(export.model_dump(mode="json")) + b"\n"
    validate_public_catalog_files(files, export)
    return export, files


def write_public_catalog(
    snapshot: CurationSnapshot,
    profile: CurationProfile,
    destination: Path,
) -> tuple[PublicCatalogExport, bool]:
    """Stage, validate, and transactionally replace one managed export directory."""

    export, files = render_public_catalog(snapshot, profile)
    target = destination.expanduser().absolute()
    if target.name in {"", ".", ".."}:
        raise StateError(
            code="public_export_destination_unsafe",
            message="Public export destination must name a dedicated directory.",
        )
    parent = target.parent
    parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    if parent.is_symlink() or not parent.is_dir():
        raise StateError(
            code="public_export_destination_unsafe",
            message="Public export parent must be a regular directory.",
        )
    if target.exists():
        if target.is_symlink() or not target.is_dir():
            raise StateError(
                code="public_export_destination_unsafe",
                message="Public export destination must be a non-symlink directory.",
            )
        existing = tuple(target.iterdir())
        manifest_path = target / MANIFEST_NAME
        if existing and (manifest_path.is_symlink() or not manifest_path.is_file()):
            raise StateError(
                code="public_export_destination_unmanaged",
                message="Refusing to replace a non-empty directory without an export manifest.",
            )
        if _tree_matches(target, files):
            return export, False

    stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.stage-", dir=parent))
    stage.chmod(0o755)
    backup: Path | None = None
    try:
        _write_staged_files(stage, files)
        validate_public_catalog_directory(stage, export)
        if target.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=parent))
            backup.rmdir()
            os.replace(target, backup)
        try:
            os.replace(stage, target)
        except OSError:
            if backup is not None and backup.exists() and not target.exists():
                os.replace(backup, target)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    except OSError as exc:
        raise StateError(
            code="public_export_write_failed",
            message=f"Public export could not replace {target.name}: {exc}",
        ) from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if backup is not None and backup.exists():
            shutil.rmtree(backup)
    return export, True


def validate_public_catalog_files(files: dict[str, bytes], export: PublicCatalogExport) -> None:
    """Validate an in-memory export package before any destination replacement."""

    expected_paths = {item.path for item in export.generated_file_manifest} | {MANIFEST_NAME}
    if set(files) != expected_paths:
        raise StateError(
            code="public_export_manifest_mismatch",
            message="Generated public files do not match the sealed manifest.",
        )
    for item in export.generated_file_manifest:
        payload = files[item.path]
        if len(payload) != item.bytes or hashlib.sha256(payload).hexdigest() != item.sha256:
            raise StateError(
                code="public_export_digest_mismatch",
                message=f"Generated file digest does not match: {item.path}",
            )
    parsed = PublicCatalogExport.model_validate_json(files[MANIFEST_NAME])
    if parsed != export:
        raise StateError(
            code="public_export_manifest_mismatch",
            message="Serialized public export manifest does not match the validated receipt.",
        )
    combined = b"\n".join(files[path] for path in sorted(files))
    if LOCAL_PATH_PATTERN.search(combined):
        raise StateError(
            code="public_export_local_path_leak",
            message="Generated public files contain a local absolute path.",
        )
    if SECRET_PATTERN.search(combined):
        raise StateError(
            code="public_export_secret_leak",
            message="Generated public files contain a credential-like value.",
        )


def validate_public_catalog_directory(root: Path, export: PublicCatalogExport) -> None:
    """Validate a staged or committed export tree without following symlinks."""

    observed: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise StateError(
                code="public_export_symlink",
                message=f"Public export contains a symlink: {path.name}",
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise StateError(
                code="public_export_file_unsafe",
                message=f"Public export contains a non-regular file: {path.name}",
            )
        relative = path.relative_to(root).as_posix()
        observed[relative] = path.read_bytes()
    validate_public_catalog_files(observed, export)


def _validate_public_inputs(snapshot: CurationSnapshot, profile: CurationProfile) -> None:
    validate_curation_snapshot(snapshot)
    validate_curation_profile(profile)
    if snapshot.profile_fingerprint != profile.canonical_fingerprint:
        raise StateError(
            code="public_export_profile_mismatch",
            message="Curation snapshot and public profile fingerprints do not match.",
        )
    if profile.visibility is not CurationVisibility.PUBLIC:
        raise StateError(
            code="public_export_private_profile",
            message="Only an explicitly public profile may enter the public exporter.",
        )
    for entry in snapshot.entries:
        if entry.field_classification != "public":  # pragma: no cover - literal model guard
            raise StateError(
                code="public_export_private_record",
                message="Private records are rejected rather than redacted during export.",
            )
        for locator in (
            *entry.evidence_receipt_ids,
            *(item.locator for item in entry.source_provenance),
        ):
            if Path(locator).is_absolute() and not locator.startswith(("https://", "http://")):
                raise StateError(
                    code="public_export_local_path_leak",
                    message=f"Public evidence locator is a local absolute path: {entry.repository}",
                )


def _public_collection(value: CollectionDefinition) -> PublicCollection:
    return PublicCollection(
        slug=value.slug,
        title=value.title,
        description=value.description,
        aliases=value.aliases,
        semantics=value.semantics,
        inclusion_rule=value.inclusion_rule,
        exclusion_rule=value.exclusion_rule,
        github_list_projection=value.github_list_projection,
        reconsideration_cadence_days=value.reconsideration_cadence_days,
    )


def _public_record(
    value: CurationEntry,
    visible_collection_slugs: frozenset[str],
) -> PublicCatalogRecord:
    return PublicCatalogRecord(
        repository=value.repository,
        url=value.url,
        description=value.description,
        collections=tuple(
            slug for slug in value.collection_memberships if slug in visible_collection_slugs
        ),
        disposition=value.primary_disposition,
        disposition_label=DISPOSITION_LABELS[value.primary_disposition],
        role=value.role,
        need=value.need,
        rationale=value.rationale,
        decision_receipt_ids=value.decision_receipt_ids,
        evidence_receipt_ids=value.evidence_receipt_ids,
        observed_license=value.observed_license,
        archived=value.archived,
        latest_release=value.latest_release,
        latest_commit=value.latest_commit,
        popularity=value.popularity,
        last_checked_at=value.last_checked_at.isoformat(),
        freshness_state=value.freshness_state,
        reconsideration_trigger=value.reconsideration_trigger,
        source_provenance=value.source_provenance,
        attribution_obligations=value.attribution_obligations,
    )


def _render_files(
    snapshot: CurationSnapshot,
    profile: CurationProfile,
    collections: tuple[PublicCollection, ...],
    records: tuple[PublicCatalogRecord, ...],
    excluded: tuple[ExcludedCandidate, ...],
    attributions: tuple[PublicAttribution, ...],
) -> dict[str, bytes]:
    catalog_payload = {
        "schema_version": PUBLIC_EXPORT_SCHEMA_VERSION,
        "allowlist_schema_version": PUBLIC_ALLOWLIST_SCHEMA_VERSION,
        "source_curation_snapshot_id": snapshot.curation_snapshot_id,
        "source_curation_fingerprint": snapshot.canonical_fingerprint,
        "source_profile_fingerprint": profile.canonical_fingerprint,
        "title": profile.title,
        "description": profile.description,
        "public_owner_identity": profile.public_owner_identity,
        "generated_at": snapshot.compiled_at.isoformat(),
        "popularity_treatment": profile.popularity_treatment,
        "non_ranking_disclaimer": profile.non_ranking_disclaimer,
        "collections": [item.model_dump(mode="json") for item in collections],
        "records": [item.model_dump(mode="json") for item in records],
        "excluded_candidates": [item.model_dump(mode="json") for item in excluded],
        "renderer_version": PUBLIC_RENDERER_VERSION,
    }
    files: dict[str, bytes] = {
        "catalog.json": canonical_bytes(catalog_payload) + b"\n",
        "index.md": _index_markdown(profile, snapshot, collections, records).encode(),
        "selection.md": _selection_markdown(profile, collections, records).encode(),
        "dogfood.md": _dogfood_markdown(profile, snapshot, collections, records).encode(),
        "in-use.md": _in_use_markdown(profile, records).encode(),
        "considered.md": _considered_markdown(profile, records, excluded).encode(),
        "freshness.md": _freshness_markdown(profile, snapshot, records).encode(),
        "sources.md": _sources_markdown(profile, snapshot, attributions).encode(),
        "tags.md": _tags_markdown().encode(),
        "assets/catalog.css": _catalog_css().encode(),
        "collections/index.md": _collections_index_markdown(profile, collections, records).encode(),
        "entries/index.md": _entries_index_markdown(profile, records).encode(),
    }
    for collection in collections:
        collection_records = tuple(
            record for record in records if collection.slug in record.collections
        )
        files[f"collections/{collection.slug}.md"] = _collection_markdown(
            collection, collection_records
        ).encode()
    for record in records:
        files[f"entries/{_repository_slug(record.repository)}.md"] = _entry_markdown(
            record, collections
        ).encode()
    return files


def _frontmatter(title: str, description: str, tags: tuple[str, ...] = ()) -> str:
    lines = ["---", f"title: {_frontmatter_string(title)}"]
    lines.append(f"description: {_frontmatter_string(description)}")
    if tags:
        lines.append("tags:")
        lines.extend(f"  - {_frontmatter_string(tag)}" for tag in tags)
    lines.extend(["---", ""])
    return "\n".join(lines)


def _frontmatter_string(value: str) -> str:
    """Encode YAML scalars without leaving raw HTML delimiters in generated Markdown."""

    return (
        json.dumps(value, ensure_ascii=False)
        .replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
    )


def _markdown_text(value: str) -> str:
    """Render untrusted prose as one escaped Markdown text span."""

    compact = " ".join(value.split())
    markdown_escaped = re.sub(r"([\\`*_\[\](){}#+|>!.-])", r"\\\1", compact)
    return html.escape(markdown_escaped)


def _index_markdown(
    profile: CurationProfile,
    snapshot: CurationSnapshot,
    collections: tuple[PublicCollection, ...],
    records: tuple[PublicCatalogRecord, ...],
) -> str:
    current = sum(record.freshness_state is FreshnessState.CURRENT for record in records)
    cards = "\n".join(
        _collection_card(
            collection,
            sum(collection.slug in record.collections for record in records),
            entry_prefix="collections/",
            show_eligibility=False,
        )
        for collection in collections
    )
    return (
        _frontmatter(profile.title, profile.description, ("OSS curation", "evidence"))
        + f"""# {_markdown_text(profile.title)}

<div class="catalog-hero">
  <p class="catalog-kicker">Check before you build</p>
  <p class="catalog-lead">Name the job. Find credible open-source options. See why each one is here and what could change the decision.</p>
  <div class="catalog-actions">
    <a class="md-button md-button--primary" href="collections/index.md">Browse by need</a>
    <a class="md-button" href="entries/index.md">Find a repository</a>
    <a class="md-button" href="in-use.md">See a worked example</a>
  </div>
</div>

!!! info "What reviewed means"
    Each entry passed its stated metadata and fit checks or carries a visible exception. This is not a code audit, security approval, adoption claim, or universal ranking. A GitHub star is only a bookmark.

## How to read an entry

Start with **Need** and **Why it is here**. The status says how this repository treats the option:
used here, trialing, reference, learning, watch, rejected, built here, or inbox. Then check the
evidence date and **Reconsider when** trigger before relying on the choice.

## Choose a need

These **{len(collections)} collections** contain **{len(records)} reviewed records**. Open the domain
closest to your problem, or use site search for a repository, technology, or phrase.

**{current} records** were inside the profile's **{profile.review_policy.default_freshness_days}-day
review window** at **{_display_timestamp(snapshot.compiled_at)}**. “Current” describes the review
date, not a security result or guarantee of active maintenance.

<div class="catalog-grid">
{cards}
</div>

## Want to see the method on itself?

Read [what ShouldaUsedThat uses](in-use.md) for concrete choices, or follow the
[catalog-to-GitHub self-use story](dogfood.md). The complete [entry index](entries/index.md) is
available when you already know what you want.

## Download or audit the evidence

- [Canonical public JSON](catalog.json)
- [Digest and reproducibility manifest](manifest.json)
- [Sources and attribution](sources.md)
- [Freshness and reconsideration](freshness.md)
"""
    )


def _dogfood_markdown(
    profile: CurationProfile,
    snapshot: CurationSnapshot,
    collections: tuple[PublicCollection, ...],
    records: tuple[PublicCatalogRecord, ...],
) -> str:
    selected = set(snapshot.projection_policy.selected_collection_slugs)
    projected_collections = tuple(item for item in collections if item.slug in selected)
    projectable_dispositions = {
        CurationDisposition.ADOPT,
        CurationDisposition.BUILD,
        CurationDisposition.LEARN,
        CurationDisposition.REFERENCE,
        CurationDisposition.TRIAL,
    }
    projectable = tuple(
        record
        for record in records
        if record.disposition in projectable_dispositions
        and selected.intersection(record.collections)
    )
    memberships = sum(
        collection.slug in record.collections
        for collection in projected_collections
        for record in projectable
    )
    account = profile.public_owner_identity.split("/", 1)[0]
    list_rows = "\n".join(
        "<tr>"
        f'<th scope="row"><a href="https://github.com/stars/{quote(account)}/lists/{_github_list_slug(collection.title)}">{html.escape(collection.title)}</a></th>'
        f"<td>{sum(collection.slug in record.collections for record in projectable)}</td>"
        f"<td>{html.escape(collection.description)}</td>"
        "</tr>"
        for collection in projected_collections
    )
    return (
        _frontmatter(
            "ShouldaUsedThat uses itself",
            "The catalog, additive GitHub projection, independent readback, and public export form one dogfood chain.",
            ("dogfood", "GitHub Lists", "verification"),
        )
        + f"""# ShouldaUsedThat uses itself

This repository uses its own workflow to answer a practical question: **what existing tools should
own each job, and what small residual capability is worth building here?** The result is the public
catalog you are reading and a set of GitHub Lists that make the same choices easier to revisit.

## What you can inspect

- **The choices:** [{len(records)} reviewed repositories](index.md) with needs, rationale, dates,
  and reconsideration triggers.
- **The public navigation:** {len(projected_collections)} GitHub Lists containing
  {len(projectable)} projectable repositories and {memberships} intentional memberships.
- **The readback:** [sanitized live evidence](../operations/live-projection.md) for what was
  actually applied and independently verified.

GitHub is a convenient view, not the ledger. Lists cannot carry the full rationale, provenance,
freshness, rejection, or reconsideration evidence preserved by the catalog.

## How the result is produced

1. A human-readable [interest selection](selection.md) exposes the domains and exact repositories compiled from `curation/selections/personal-interests.json`.
2. A [cross-source decision receipt](../decisions/personal-oss-curation.json) records discovery sources, hard gates, rejected shortcuts, unknowns, and reconsideration triggers.
3. `curated` compiles those public inputs with the repository's own dependency and prior-art receipts into immutable canonical JSON.
4. `projected` reads the current GitHub account and seals only additive Star and List operations.
5. `apply` rechecks identity, capability, drift, expiry, and operation caps before each allowed write.
6. `verify` independently reads back every claimed public List, star, description, membership, and preserved membership.
7. `exported` builds this allowlisted catalog and its deterministic manifest.

The snapshot's canonical curation fingerprint is `{snapshot.canonical_fingerprint}`.

## Native GitHub projection

Use the Lists for browsing; use the catalog when the reason or evidence matters.

<div class="table-scroll" role="region" aria-label="Projected GitHub Lists" tabindex="0">
<table>
  <caption>Public Lists generated from the reviewed profile</caption>
  <thead><tr><th scope="col">GitHub List</th><th scope="col">Reviewed repositories</th><th scope="col">Meaning</th></tr></thead>
  <tbody>
{list_rows}
  </tbody>
</table>
</div>

Private state, account node IDs, token scopes, raw API payloads, and operation receipts stay outside
the repository.

## What this proves—and what it does not

- It proves the repository can compile a substantial reviewed catalog, preserve meaningful multi-list membership, execute its bounded additive projection, and verify public postconditions.
- It does not claim that stars equal adoption, that popularity equals quality, or that one list is a universal ranking.
- It does not silently unstar, remove memberships, rename or delete Lists, expose private repositories, or grant scheduled jobs personal mutation authority.
"""
    )


def _selection_markdown(
    profile: CurationProfile,
    collections: tuple[PublicCollection, ...],
    records: tuple[PublicCatalogRecord, ...],
) -> str:
    receipt = "docs/decisions/personal-oss-curation.json"
    selected = tuple(record for record in records if receipt in record.evidence_receipt_ids)
    memberships = sum(len(record.collections) for record in selected)
    multi_collection = sum(len(record.collections) > 1 for record in selected)
    collection_by_slug = {item.slug: item for item in collections}
    sections: list[str] = []
    for slug in (
        collection.slug
        for collection in collections
        if any(collection.slug in record.collections for record in selected)
    ):
        collection = collection_by_slug[slug]
        members = tuple(record for record in selected if slug in record.collections)
        rows = "\n".join(
            f"- [{_markdown_text(record.repository)}](entries/{_repository_slug(record.repository)}.md) — {_markdown_text(record.disposition_label)}"
            for record in members
        )
        sections.append(
            f"## [{_markdown_text(collection.title)}](collections/{collection.slug}.md) — {len(members)}\n\n"
            f"{_markdown_text(collection.description)}\n\n{rows}"
        )
    return (
        _frontmatter(
            "Personal OSS interest selection",
            "The exact reviewed repositories grouped by the human-authored interest domains that drive the public GitHub projection.",
            ("OSS curation", "interests", "prior art"),
        )
        + f"""# Personal OSS interest selection

Use this page when you want the exact personal-interest set behind the public GitHub Lists, grouped
by the problem domains it was chosen to explore. It contains **{len(selected)} unique
repositories**, **{memberships} domain memberships**, and **{multi_collection} repositories with
intentional multi-domain membership**.

Selection means **consider this before building**; it is not a code audit, security approval, or
automatic adoption. Every entry passed the selection's public-identity, archive, description,
license, popularity, and freshness gates or carries a narrow written exception. The
[decision receipt](../decisions/personal-oss-curation.json) preserves sources, limits, rejected
shortcuts, and reconsideration triggers.

{(chr(10) * 2).join(sections)}

## Relationship to the full catalog

The [complete catalog](index.md) also includes ShouldaUsedThat's own dependency, prior-art, trial, rejection, and build records. The interest selection is kept separate so personal discovery intent remains readable while the compiled catalog remains authoritative for evidence and decision state.

Source selection: `curation/selections/personal-interests.json`.
"""
    )


def _in_use_markdown(profile: CurationProfile, records: tuple[PublicCatalogRecord, ...]) -> str:
    used = tuple(
        record
        for record in records
        if record.disposition in {CurationDisposition.ADOPT, CurationDisposition.BUILD}
    )
    rows = "\n".join(
        "<tr>"
        f'<th scope="row">{html.escape(group)}</th>'
        f"<td>{html.escape(tools)}</td>"
        f'<td><a href="{html.escape(evidence, quote=True)}">decision evidence</a></td>'
        "</tr>"
        for group, tools, evidence in TOOLCHAIN_GROUPS
    )
    cards = "\n".join(_record_card(record, "") for record in used)
    return (
        _frontmatter(
            "What ShouldaUsedThat uses",
            "Runtime, development, CI, security, documentation, and release roles.",
            ("Used here", "toolchain"),
        )
        + f"""# What ShouldaUsedThat uses

This is the catalog's clearest worked example: every item below owns a named job in this repository,
and repository or configuration evidence confirms that use. It answers “what did this project use
instead of rebuilding?”—not “what should every project use?”

<div class="table-scroll" role="region" aria-label="Toolchain role inventory" tabindex="0">
<table>
  <caption>Complete evidenced toolchain roles</caption>
  <thead><tr><th scope="col">Role family</th><th scope="col">Current owners</th><th scope="col">Evidence</th></tr></thead>
  <tbody>
{rows}
  </tbody>
</table>
</div>

## Catalog records marked used or built

<div class="catalog-grid">
{cards}
</div>

The [full implementation reuse gate](../architecture/dogfood-reuse-audit.md) records versions, boundaries, alternatives, and removal conditions for the wider toolchain. The catalog source remains {_markdown_text(profile.public_owner_identity)}'s reviewed public profile.
"""
    )


def _considered_markdown(
    profile: CurationProfile,
    records: tuple[PublicCatalogRecord, ...],
    excluded: tuple[ExcludedCandidate, ...],
) -> str:
    sections: list[str] = []
    for disposition in (
        CurationDisposition.TRIAL,
        CurationDisposition.REFERENCE,
        CurationDisposition.LEARN,
        CurationDisposition.WATCH,
        CurationDisposition.REJECT,
        CurationDisposition.INBOX,
    ):
        selected = tuple(record for record in records if record.disposition is disposition)
        cards = "\n".join(_record_card(record, "") for record in selected)
        body = (
            f'<div class="catalog-grid">\n{cards}\n</div>'
            if selected
            else '<p class="catalog-empty">No reviewed records currently have this status.</p>'
        )
        sections.append(
            f"## {DISPOSITION_LABELS[disposition]}\n\n{DISPOSITION_MEANINGS[disposition]}\n\n{body}"
        )
    excluded_rows = "\n".join(
        f"<li><strong>{html.escape(item.repository)}</strong> — {html.escape(item.reason)} "
        f"<em>Source: {html.escape(item.source)}.</em></li>"
        for item in excluded
    )
    excluded_list = f"<ul>\n{excluded_rows}\n</ul>" if excluded_rows else ""
    return (
        _frontmatter(
            "Considered choices",
            "Trials, references, watches, rejections, learning records, and inbox state.",
            ("Trialing", "Reference", "Watch", "Rejected", "Inbox"),
        )
        + "# Considered choices\n\n"
        + "Not every useful discovery becomes a dependency. Browse **Trialing** for active "
        + "evaluations, **Reference** or **Learn** for ideas, **Watch** for deferred choices, and "
        + "**Rejected / deferred** for options considered but not selected here.\n\n"
        + _markdown_text(profile.non_ranking_disclaimer)
        + "\n\n"
        + "\n\n".join(sections)
        + "\n\n## Excluded before catalog entry\n\n"
        + (excluded_list or "No candidates are currently recorded in the exclusion ledger.")
        + "\n"
    )


def _freshness_markdown(
    profile: CurationProfile,
    snapshot: CurationSnapshot,
    records: tuple[PublicCatalogRecord, ...],
) -> str:
    rows = "\n".join(
        "<tr>"
        f'<th scope="row"><a href="entries/{_repository_slug(record.repository)}.md">{html.escape(record.repository)}</a></th>'
        f"<td>{html.escape(record.freshness_state.value)}</td>"
        f'<td><time datetime="{html.escape(record.last_checked_at, quote=True)}">{html.escape(record.last_checked_at)}</time></td>'
        f"<td>{html.escape(record.reconsideration_trigger)}</td>"
        "</tr>"
        for record in records
    )
    return (
        _frontmatter(
            "Freshness and reconsideration",
            "Dated evidence state and the exact triggers that reopen a decision.",
            ("freshness", "reconsideration"),
        )
        + f"""# Freshness and reconsideration

This snapshot was compiled at **{_display_timestamp(snapshot.compiled_at)}**. “Current” means current under this profile's dated review policy, not permanently correct.

{_markdown_text(profile.popularity_treatment)}

<div class="table-scroll" role="region" aria-label="Catalog freshness" tabindex="0">
<table>
  <caption>Evidence freshness and next review trigger</caption>
  <thead><tr><th scope="col">Repository</th><th scope="col">State</th><th scope="col">Last checked</th><th scope="col">Reconsider when</th></tr></thead>
  <tbody>
{rows}
  </tbody>
</table>
</div>
"""
    )


def _sources_markdown(
    profile: CurationProfile,
    snapshot: CurationSnapshot,
    attributions: tuple[PublicAttribution, ...],
) -> str:
    sources = "\n".join(
        f"<li><code>{html.escape(item.locator)}</code> — SHA-256 "
        f"<code>{item.content_sha256}</code>; {item.entry_count} entries</li>"
        for item in snapshot.source_snapshots
    )
    attribution_rows = "\n".join(
        "<tr>"
        f'<th scope="row">{html.escape(item.repository)}</th>'
        f"<td>{html.escape(item.observed_license or 'unknown')}</td>"
        f"<td>{html.escape('; '.join(item.obligations) or 'No additional catalog obligation recorded.')}</td>"
        f"<td>{html.escape(', '.join(item.source_locators))}</td>"
        "</tr>"
        for item in attributions
    )
    return (
        _frontmatter(
            "Sources and attribution",
            "Exact source digests, licenses, provenance, and attribution obligations.",
            ("sources", "licenses", "attribution"),
        )
        + f"""# Sources and attribution

## Bound source snapshots

<ul>
{sources}
</ul>

The profile source is Apache-2.0 repository-authored review data. Upstream material remains under its own license; catalog-specific obligations are listed below.

<div class="table-scroll" role="region" aria-label="License and attribution inventory" tabindex="0">
<table>
  <caption>License and attribution inventory</caption>
  <thead><tr><th scope="col">Repository</th><th scope="col">Observed license</th><th scope="col">Obligation</th><th scope="col">Source</th></tr></thead>
  <tbody>
{attribution_rows}
  </tbody>
</table>
</div>

## Boundaries

{_markdown_text(profile.non_ranking_disclaimer)} The export contains no private notes, credentials, local paths, raw API responses, or hidden source membership.
"""
    )


def _collections_index_markdown(
    profile: CurationProfile,
    collections: tuple[PublicCollection, ...],
    records: tuple[PublicCatalogRecord, ...],
) -> str:
    cards = "\n".join(
        _collection_card(
            collection,
            sum(collection.slug in record.collections for record in records),
        )
        for collection in collections
    )
    return (
        _frontmatter(
            "Collections",
            "Durable domains and cross-cutting necessities with explicit aliases and rules.",
            ("collections",),
        )
        + f"""# Collections

Choose the collection closest to the job you are trying to solve. A repository may belong to more
than one collection when it genuinely serves more than one need.

Collections organize evidence; they do not rank repositories. Aliases are searchable, and an empty
collection stays visible as an intentional area rather than disappearing from the catalog.

<div class="catalog-grid">
{cards}
</div>

Only collections explicitly marked “GitHub List eligible” can enter a sealed projection. Eligibility does not mean the List exists or has been approved. Source profile: **{_markdown_text(profile.profile_id)}**.
"""
    )


def _collection_markdown(
    collection: PublicCollection,
    records: tuple[PublicCatalogRecord, ...],
) -> str:
    cards = "\n".join(_record_card(record, "../") for record in records)
    body = (
        f'<div class="catalog-grid">\n{cards}\n</div>'
        if records
        else (
            '<div class="catalog-empty"><strong>No reviewed entries yet.</strong> '
            "The collection stays searchable as intent; no candidate is invented to fill it.</div>"
        )
    )
    tags = (collection.title, *collection.aliases)
    return (
        _frontmatter(collection.title, collection.description, tags)
        + f"""# {_markdown_text(collection.title)}

<p class="collection-deck">{html.escape(collection.description)}</p>

## Use this collection when

{_markdown_text(collection.semantics)}

Browse the reviewed entries below first. The rules after them explain the exact boundary used to
keep this collection coherent.

## Reviewed entries

{body}

## Collection boundary

**Aliases:** {_markdown_text(", ".join(collection.aliases) or "none")}<br>
**GitHub List eligibility:** {"eligible for a sealed plan" if collection.github_list_projection else "site only"}<br>
**Review cadence:** {collection.reconsideration_cadence_days} days

- **Include:** {_markdown_text(collection.inclusion_rule)}
- **Exclude:** {_markdown_text(collection.exclusion_rule)}
"""
    )


def _entries_index_markdown(
    profile: CurationProfile, records: tuple[PublicCatalogRecord, ...]
) -> str:
    cards = "\n".join(_record_card(record, "../") for record in records)
    return (
        _frontmatter(
            "Catalog entries",
            "Every public repository record with its contextual disposition and evidence.",
            ("repositories", "evidence"),
        )
        + f"""# Catalog entries

Use site search when you know a repository name, technology, or phrase. If you are still naming the
problem, [browse collections](../collections/index.md) instead.

Every card is a contextual decision, not a universal endorsement. {_markdown_text(profile.non_ranking_disclaimer)}

<div class="catalog-grid">
{cards}
</div>
"""
    )


def _entry_markdown(
    record: PublicCatalogRecord,
    collections: tuple[PublicCollection, ...],
) -> str:
    titles = {item.slug: item.title for item in collections}
    collection_links = ", ".join(
        f'<a href="../collections/{html.escape(slug, quote=True)}.md">{html.escape(titles.get(slug, slug))}</a>'
        for slug in record.collections
    )
    evidence_links = (
        "\n".join(
            f"- {_evidence_anchor(locator, depth=2)}" for locator in record.evidence_receipt_ids
        )
        or "- No separate evidence link recorded."
    )
    source_links = "\n".join(
        f"- {_evidence_anchor(source.locator, depth=2)} — observed `{source.observed_at.isoformat()}`"
        for source in record.source_provenance
    )
    popularity = (
        f"{record.popularity.stars:,} stars observed at "
        f"`{record.popularity.observed_at.isoformat()}`"
        if record.popularity.stars is not None and record.popularity.observed_at is not None
        else "No public star count is claimed by this snapshot."
    )
    return (
        _frontmatter(
            record.repository,
            record.description,
            (record.disposition_label, *(titles.get(slug, slug) for slug in record.collections)),
        )
        + f"""# {_markdown_text(record.repository)}

<div class="entry-heading">
  {_status_chip(record)}
  {_freshness_chip(record.freshness_state)}
</div>

<p class="collection-deck">{html.escape(record.description)}</p>

[Open repository]({html.escape(record.url, quote=True)}){{ .md-button .md-button--primary }}

## Why it is here

**Need:** {_markdown_text(record.need)}<br>
**Why:** {_markdown_text(record.rationale)}<br>
**Role:** {_markdown_text(record.role)}<br>
**Status meaning:** {_markdown_text(DISPOSITION_MEANINGS[record.disposition])}<br>
**Collections:** {collection_links}

## Reconsider when

{_markdown_text(record.reconsideration_trigger)}

## Observed facts

- **License:** {html.escape(record.observed_license or "unknown")}
- **Archived:** {html.escape(str(record.archived).lower() if record.archived is not None else "unknown")}
- **Latest release:** {_markdown_text(record.latest_release or "not recorded")}
- **Latest commit:** <code>{html.escape(record.latest_commit or "not recorded")}</code>
- **Popularity:** {popularity}
- **Last checked:** `{html.escape(record.last_checked_at)}`

## Evidence

{evidence_links}

### Source provenance

{source_links}

## Attribution

{_markdown_text("; ".join(record.attribution_obligations) or "No additional catalog obligation recorded.")}
"""
    )


def _tags_markdown() -> str:
    return _frontmatter("Tags", "Browse catalog pages by status and collection.", ("tags",)) + (
        "# Tags\n\nUse tags to combine collection, disposition, and evidence views.\n\n"
        "<!-- material/tags -->\n"
    )


def _record_card(record: PublicCatalogRecord, entry_prefix: str) -> str:
    return f"""<article class="catalog-card">
  <div class="catalog-card__meta">{_status_chip(record)} {_freshness_chip(record.freshness_state)}</div>
  <h3><a href="{entry_prefix}entries/{_repository_slug(record.repository)}.md">{html.escape(record.repository)}</a></h3>
  <p>{html.escape(record.description)}</p>
  <p class="catalog-card__role"><strong>Role</strong> {html.escape(record.role)}</p>
  <p class="catalog-card__need"><strong>Need</strong> {html.escape(record.need)}</p>
</article>"""


def _collection_card(
    collection: PublicCollection,
    count: int,
    *,
    entry_prefix: str = "",
    show_eligibility: bool = True,
) -> str:
    eligibility = "GitHub List eligible" if collection.github_list_projection else "Site collection"
    meta = (
        f'  <div class="catalog-card__meta"><span class="projection-chip">{eligibility}</span></div>\n'
        if show_eligibility
        else ""
    )
    return f"""<article class="catalog-card collection-card">
{meta}  <h3><a href="{html.escape(entry_prefix + collection.slug, quote=True)}.md">{html.escape(collection.title)}</a></h3>
  <p>{html.escape(collection.description)}</p>
  <p><strong>{count}</strong> reviewed {"entry" if count == 1 else "entries"}</p>
  <p class="catalog-aliases"><strong>Aliases</strong> {html.escape(", ".join(collection.aliases) or "none")}</p>
</article>"""


def _status_chip(record: PublicCatalogRecord) -> str:
    value = html.escape(record.disposition.value, quote=True)
    return (
        f'<span class="status-chip status-chip--{value}">'
        f"{html.escape(record.disposition_label)}</span>"
    )


def _freshness_chip(state: FreshnessState) -> str:
    value = html.escape(state.value, quote=True)
    return f'<span class="freshness-chip freshness-chip--{value}">{value}</span>'


def _repository_slug(repository: str) -> str:
    return repository.replace("/", "--")


def _display_timestamp(value: datetime) -> str:
    rendered = value.isoformat(timespec="minutes")
    return f"{rendered.removesuffix('+00:00')} UTC" if rendered.endswith("+00:00") else rendered


def _github_list_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")


def _evidence_anchor(locator: str, *, depth: int) -> str:
    if locator.startswith(("https://", "http://")):
        href = locator
    elif locator.startswith("docs/"):
        href = "../" * depth + locator.removeprefix("docs/")
    else:
        href = "https://github.com/pradeeptathineni/shoulda-used-that/blob/main/" + quote(
            locator, safe="/._-"
        )
    return f'<a href="{html.escape(href, quote=True)}">{html.escape(locator)}</a>'


def _catalog_css() -> str:
    return """/* Generated public-catalog presentation; no remote assets or runtime requests. */
:root {
  --sut-ink: #13231f;
  --sut-muted: #4b635c;
  --sut-surface: #f5faf7;
  --sut-panel: #ffffff;
  --sut-line: #c8d8d1;
  --sut-accent: #087f5b;
  --sut-accent-strong: #075c45;
  --sut-warm: #a44a00;
}

[data-md-color-scheme="slate"] {
  --sut-ink: #e7f4ef;
  --sut-muted: #adc7bd;
  --sut-surface: #12201d;
  --sut-panel: #182a26;
  --sut-line: #3b5b52;
  --sut-accent: #62d9b0;
  --sut-accent-strong: #8ce8c8;
  --sut-warm: #ffb36f;
}

.catalog-hero {
  border: 1px solid var(--sut-line);
  border-radius: 1rem;
  padding: clamp(1.35rem, 4vw, 2.6rem);
  background: linear-gradient(145deg, color-mix(in srgb, var(--sut-accent) 12%, var(--sut-panel)), var(--sut-panel) 62%);
  box-shadow: 0 1rem 2.5rem color-mix(in srgb, var(--sut-ink) 9%, transparent);
}

.catalog-kicker {
  color: var(--sut-accent-strong);
  font-size: .72rem;
  font-weight: 800;
  letter-spacing: .14em;
  margin: 0 0 .5rem;
  text-transform: uppercase;
}

.catalog-lead, .collection-deck {
  color: var(--sut-ink);
  font-size: clamp(1.05rem, 2vw, 1.3rem);
  line-height: 1.55;
  max-width: 47rem;
}

.catalog-actions { display: flex; flex-wrap: wrap; gap: .65rem; margin-top: 1.25rem; }

.home-actions { margin: 1.25rem 0 2rem; }
.home-actions > p {
  align-items: stretch;
  display: flex;
  flex-wrap: wrap;
  gap: .65rem;
  margin: 0;
}
.home-actions .md-button {
  align-items: center;
  box-sizing: border-box;
  display: inline-flex;
  justify-content: center;
  margin: 0;
  min-height: 2.75rem;
  text-align: center;
}

.catalog-grid { display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr)); margin: 1.2rem 0 2rem; }

.catalog-card {
  background: var(--sut-panel);
  border: 1px solid var(--sut-line);
  border-radius: .8rem;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 1rem 1.05rem;
}

.catalog-card h3 { margin: .8rem 0 .45rem; overflow-wrap: anywhere; }
.catalog-card p { color: var(--sut-muted); margin: .35rem 0; }
.catalog-card__meta, .entry-heading { align-items: center; display: flex; flex-wrap: wrap; gap: .4rem; }
.catalog-card__role, .catalog-card__need { font-size: .82rem; }
.catalog-card__need { border-top: 1px solid var(--sut-line); margin-top: auto !important; padding-top: .65rem; }

.status-chip, .freshness-chip, .projection-chip {
  border: 1px solid currentColor;
  border-radius: 999px;
  display: inline-flex;
  font-size: .68rem;
  font-weight: 760;
  letter-spacing: .035em;
  line-height: 1;
  padding: .33rem .5rem;
  text-transform: uppercase;
}

.status-chip--adopt, .status-chip--build, .freshness-chip--current { color: var(--sut-accent-strong); }
.status-chip--trial, .status-chip--watch, .freshness-chip--stale, .freshness-chip--partial { color: var(--sut-warm); }
.status-chip--reject, .freshness-chip--blocked { color: #a32638; }
.status-chip--reference, .status-chip--learn, .status-chip--inbox, .projection-chip { color: var(--sut-muted); }

.catalog-empty {
  background: var(--sut-surface);
  border: 1px dashed var(--sut-line);
  border-radius: .75rem;
  color: var(--sut-muted);
  padding: 1rem;
}

.table-scroll { overflow-x: auto; margin: 1rem 0 2rem; }
.table-scroll:focus-visible, .catalog-card a:focus-visible, .catalog-actions a:focus-visible, .home-actions a:focus-visible {
  outline: 3px solid var(--sut-accent);
  outline-offset: 3px;
}
.table-scroll table { min-width: 42rem; width: 100%; }
.table-scroll caption { color: var(--sut-muted); font-size: .78rem; padding: .5rem; text-align: left; }
.table-scroll th { color: var(--sut-ink); }
.catalog-aliases { overflow-wrap: anywhere; }

@media (max-width: 44rem) {
  .catalog-hero { border-radius: .7rem; }
  .catalog-grid { grid-template-columns: 1fr; }
  .home-actions > p {
    display: grid;
    gap: .75rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .home-actions .md-button {
    border-radius: .75rem;
    line-height: 1.35;
    min-height: 3rem;
    padding: .65rem 1rem;
    white-space: normal;
    width: 100%;
  }
  .catalog-actions .md-button { text-align: center; width: 100%; }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; }
}
"""


def _write_staged_files(root: Path, files: dict[str, bytes]) -> None:
    for relative, payload in sorted(files.items()):
        path = root / PurePosixPath(relative)
        path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        path.write_bytes(payload)
        path.chmod(0o644)


def _tree_matches(root: Path, files: dict[str, bytes]) -> bool:
    observed: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_dir() and not path.is_file()):
            return False
        if path.is_file():
            observed[path.relative_to(root).as_posix()] = path.read_bytes()
    return observed == files
