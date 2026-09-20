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
    Assessment,
    AssessmentBasis,
    Brief,
    CandidateScreening,
    CollectionDefinition,
    CurationDisposition,
    CurationProfile,
    CurationProjectionEntry,
    CurationSnapshot,
    CurationVisibility,
    ExcludedCandidate,
    FreshnessState,
    PopularitySnapshot,
    Problem,
    RepositoryEvidence,
    ScreeningBasis,
    SourceProvenance,
    candidate_screenings,
    curation_projection_entries,
    repository_evidence_records,
    validate_curation_profile,
    validate_curation_snapshot,
)
from shoulda_used_that.errors import StateError
from shoulda_used_that.models import FrozenModel

PUBLIC_EXPORT_SCHEMA_VERSION: Literal["4.0"] = "4.0"
PUBLIC_ALLOWLIST_SCHEMA_VERSION: Literal["1.0"] = "1.0"
PUBLIC_RENDERER_VERSION = "shoulda-public-briefs/4.0"
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
    publication_state: Literal["screened", "assessed"]
    screening_basis: ScreeningBasis
    operator_disposition: CurationDisposition
    decision_receipt_ids: tuple[str, ...]
    evidence_receipt_ids: tuple[str, ...]
    observed_license: str | None
    archived: bool | None
    latest_release: str | None
    latest_commit: str | None
    popularity: PopularitySnapshot
    last_checked_at: str
    freshness_state: FreshnessState
    source_provenance: tuple[SourceProvenance, ...]
    attribution_obligations: tuple[str, ...]


class PublicProblem(FrozenModel):
    problem_id: str
    question: str
    domains: tuple[str, ...]


class PublicAssessment(FrozenModel):
    problem_id: str
    repository: str
    assessment_basis: AssessmentBasis
    covers: tuple[str, ...]
    watch: tuple[str, ...]
    unknowns: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_state: CurationDisposition | None
    reconsider_when: tuple[str, ...]
    assessed_at: str


class PublicBrief(FrozenModel):
    problem_id: str
    title: str
    candidate_repositories: tuple[str, ...]
    what_appears_covered: tuple[str, ...]
    what_remains_unresolved: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    checked_at: str


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
    schema_version: Literal["4.0"] = PUBLIC_EXPORT_SCHEMA_VERSION
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
    problems: tuple[PublicProblem, ...]
    assessments: tuple[PublicAssessment, ...]
    briefs: tuple[PublicBrief, ...]
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
        record_ids = tuple(item.repository for item in self.exported_records)
        if record_ids != tuple(sorted(set(record_ids))):
            raise ValueError("public catalog records must use unique canonical repository order")
        problem_ids_in_order = tuple(item.problem_id for item in self.problems)
        if problem_ids_in_order != tuple(sorted(set(problem_ids_in_order))):
            raise ValueError("public problems must use unique canonical problem order")
        relations = tuple((item.problem_id, item.repository) for item in self.assessments)
        if relations != tuple(sorted(set(relations))):
            raise ValueError("public assessments must use unique canonical relation order")
        repositories = {item.repository for item in self.exported_records}
        assessed_repositories = {item.repository for item in self.assessments}
        problem_ids = {item.problem_id for item in self.problems}
        if any(
            item.repository not in repositories or item.problem_id not in problem_ids
            for item in self.assessments
        ):
            raise ValueError("public assessments must reference exported problems and repositories")
        brief_problem_ids = tuple(item.problem_id for item in self.briefs)
        if brief_problem_ids != tuple(sorted(set(brief_problem_ids))):
            raise ValueError("public briefs must use unique canonical problem order")
        assessment_relations = set(relations)
        for brief in self.briefs:
            if (
                brief.problem_id not in problem_ids
                or not 3 <= len(brief.candidate_repositories) <= 5
                or len(brief.candidate_repositories) != len(set(brief.candidate_repositories))
            ):
                raise ValueError(
                    "public briefs require one known problem and 3-5 unique candidates"
                )
            if any(
                (brief.problem_id, repository) not in assessment_relations
                for repository in brief.candidate_repositories
            ):
                raise ValueError("public brief candidates require contextual assessments")
        if any(
            item.publication_state
            != ("assessed" if item.repository in assessed_repositories else "screened")
            for item in self.exported_records
        ):
            raise ValueError("public record state must be derived from explicit assessments")
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
    screenings = candidate_screenings(snapshot)
    screening_by_repository = {item.repository: item for item in screenings}
    projection_by_repository = {
        item.repository: item for item in curation_projection_entries(snapshot)
    }
    assessed_repositories = {item.repository for item in snapshot.assessments}
    records = tuple(
        _public_record(
            item,
            screening_by_repository[item.repository],
            projection_by_repository[item.repository],
            visible_collection_slugs,
            assessed=item.repository in assessed_repositories,
        )
        for item in repository_evidence_records(snapshot)
    )
    problems = tuple(
        _public_problem(item, visible_collection_slugs)
        for item in sorted(snapshot.problems, key=lambda item: item.problem_id)
    )
    assessments = tuple(
        _public_assessment(item)
        for item in sorted(
            snapshot.assessments, key=lambda item: (item.problem_id, item.repository)
        )
    )
    briefs = tuple(
        _public_brief(item) for item in sorted(snapshot.briefs, key=lambda item: item.problem_id)
    )
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
    files = _render_files(
        snapshot,
        profile,
        collections,
        records,
        problems,
        assessments,
        briefs,
        excluded,
        attributions,
    )
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
        for screening in screenings
        for slug in screening.domain_tags
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
        "problems": [item.model_dump(mode="json") for item in problems],
        "assessments": [item.model_dump(mode="json") for item in assessments],
        "briefs": [item.model_dump(mode="json") for item in briefs],
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
        problems=problems,
        assessments=assessments,
        briefs=briefs,
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
    for evidence in repository_evidence_records(snapshot):
        if evidence.field_classification != "public":  # pragma: no cover - literal model guard
            raise StateError(
                code="public_export_private_record",
                message="Private records are rejected rather than redacted during export.",
            )
        for locator in (item.locator for item in evidence.source_provenance):
            if Path(locator).is_absolute() and not locator.startswith(("https://", "http://")):
                raise StateError(
                    code="public_export_local_path_leak",
                    message=(
                        f"Public evidence locator is a local absolute path: {evidence.repository}"
                    ),
                )
    for locator in (
        ref
        for screening in candidate_screenings(snapshot)
        for ref in screening.evidence_receipt_ids
    ):
        if Path(locator).is_absolute() and not locator.startswith(("https://", "http://")):
            raise StateError(
                code="public_export_local_path_leak",
                message="Public screening evidence contains a local absolute path.",
            )
    for locator in (ref for assessment in snapshot.assessments for ref in assessment.evidence_refs):
        if Path(locator).is_absolute() and not locator.startswith(("https://", "http://")):
            raise StateError(
                code="public_export_local_path_leak",
                message="Public assessment evidence contains a local absolute path.",
            )
    for locator in (ref for brief in snapshot.briefs for ref in brief.evidence_refs):
        if Path(locator).is_absolute() and not locator.startswith(("https://", "http://")):
            raise StateError(
                code="public_export_local_path_leak",
                message="Public brief evidence contains a local absolute path.",
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
    value: RepositoryEvidence,
    screening: CandidateScreening,
    projection_entry: CurationProjectionEntry,
    visible_collection_slugs: frozenset[str],
    *,
    assessed: bool,
) -> PublicCatalogRecord:
    return PublicCatalogRecord(
        repository=value.repository,
        url=value.url,
        description=value.description,
        collections=tuple(
            slug for slug in screening.domain_tags if slug in visible_collection_slugs
        ),
        publication_state="assessed" if assessed else "screened",
        screening_basis=screening.screening_basis,
        operator_disposition=projection_entry.primary_disposition,
        decision_receipt_ids=screening.decision_receipt_ids,
        evidence_receipt_ids=screening.evidence_receipt_ids,
        observed_license=value.observed_license,
        archived=value.archived,
        latest_release=value.latest_release,
        latest_commit=value.latest_commit,
        popularity=value.popularity,
        last_checked_at=value.last_checked_at.isoformat(),
        freshness_state=value.freshness_state,
        source_provenance=value.source_provenance,
        attribution_obligations=value.attribution_obligations,
    )


def _public_problem(value: Problem, visible_collection_slugs: frozenset[str]) -> PublicProblem:
    return PublicProblem(
        problem_id=value.problem_id,
        question=value.question,
        domains=tuple(slug for slug in value.domain_tags if slug in visible_collection_slugs),
    )


def _public_assessment(value: Assessment) -> PublicAssessment:
    return PublicAssessment(
        problem_id=value.problem_id,
        repository=value.repository,
        assessment_basis=value.assessment_basis,
        covers=value.covers,
        watch=value.watch,
        unknowns=value.unknowns,
        evidence_refs=value.evidence_refs,
        decision_state=value.decision_state,
        reconsider_when=value.reconsider_when,
        assessed_at=value.assessed_at.isoformat(),
    )


def _public_brief(value: Brief) -> PublicBrief:
    return PublicBrief(
        problem_id=value.problem_id,
        title=value.title,
        candidate_repositories=value.candidate_repositories,
        what_appears_covered=value.what_appears_covered,
        what_remains_unresolved=value.what_remains_unresolved,
        evidence_refs=value.evidence_refs,
        checked_at=value.checked_at.isoformat(),
    )


def _render_files(
    snapshot: CurationSnapshot,
    profile: CurationProfile,
    collections: tuple[PublicCollection, ...],
    records: tuple[PublicCatalogRecord, ...],
    problems: tuple[PublicProblem, ...],
    assessments: tuple[PublicAssessment, ...],
    briefs: tuple[PublicBrief, ...],
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
        "corpus_records": [item.model_dump(mode="json") for item in records],
        "problems": [item.model_dump(mode="json") for item in problems],
        "assessments": [item.model_dump(mode="json") for item in assessments],
        "briefs": [item.model_dump(mode="json") for item in briefs],
        "excluded_candidates": [item.model_dump(mode="json") for item in excluded],
        "renderer_version": PUBLIC_RENDERER_VERSION,
    }
    record_by_repository = {item.repository: item for item in records}
    problem_by_id = {item.problem_id: item for item in problems}
    assessment_by_relation = {(item.problem_id, item.repository): item for item in assessments}
    files: dict[str, bytes] = {
        "catalog.json": canonical_bytes(catalog_payload) + b"\n",
        "index.md": _briefs_index_markdown(profile, snapshot, problems, briefs).encode(),
        "sources.md": _sources_markdown(profile, snapshot, attributions).encode(),
        "tags.md": _tags_markdown().encode(),
        "assets/catalog.css": _catalog_css().encode(),
    }
    for brief in briefs:
        files[f"briefs/{brief.problem_id}.md"] = _brief_markdown(
            brief,
            problem_by_id[brief.problem_id],
            record_by_repository,
            assessment_by_relation,
        ).encode()
    assessed_repositories = sorted(
        {repository for brief in briefs for repository in brief.candidate_repositories}
    )
    for repository in assessed_repositories:
        files[f"evidence/{_repository_slug(repository)}.md"] = _evidence_markdown(
            record_by_repository[repository],
            briefs,
            problem_by_id,
            assessment_by_relation,
        ).encode()
    return files


def _frontmatter(
    title: str,
    description: str,
    tags: tuple[str, ...] = (),
    *,
    exclude_from_search: bool = False,
) -> str:
    lines = ["---", f"title: {_frontmatter_string(title)}"]
    lines.append(f"description: {_frontmatter_string(description)}")
    if tags:
        lines.append("tags:")
        lines.extend(f"  - {_frontmatter_string(tag)}" for tag in tags)
    if exclude_from_search:
        lines.extend(("search:", "  exclude: true"))
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


def _briefs_index_markdown(
    profile: CurationProfile,
    snapshot: CurationSnapshot,
    problems: tuple[PublicProblem, ...],
    briefs: tuple[PublicBrief, ...],
) -> str:
    problem_by_id = {item.problem_id: item for item in problems}
    cards = "\n".join(
        f"""<article class="catalog-card brief-card">
  <h2><a href="briefs/{html.escape(brief.problem_id, quote=True)}.md">{html.escape(brief.title)}</a></h2>
  <p>{html.escape(problem_by_id[brief.problem_id].question)}</p>
  <p><strong>{len(brief.candidate_repositories)} approaches worth knowing</strong></p>
  <p class="catalog-card__evidence">Checked {html.escape(_checked_date(brief.checked_at))} · <a href="briefs/{html.escape(brief.problem_id, quote=True)}.md">Open brief</a></p>
</article>"""
        for brief in briefs
    )
    return (
        _frontmatter(
            "Explore prior-art briefs",
            "Concrete software build problems with assessed options, tradeoffs, and residual gaps.",
            ("prior art", "software architecture"),
        )
        + f"""# Explore prior-art briefs

Start with a build problem. Each brief shows the few existing approaches worth knowing, what they
cover, where they stop, and what still appears unresolved. No brief chooses a universal winner.

<div class="catalog-grid">
{cards}
</div>

## Evidence boundary

These {len(briefs)} briefs use explicit problem-by-repository assessments. The complete safe corpus
of {snapshot.counts.entries} screened repositories remains available in [machine-readable JSON](catalog.json),
but screened metadata never becomes contextual fit copy or a rich reader page.

Checked {_display_timestamp(snapshot.compiled_at)} · [Sources and attribution](sources.md) ·
[Reproducibility manifest](manifest.json)
"""
    )


def _brief_markdown(
    brief: PublicBrief,
    problem: PublicProblem,
    records: dict[str, PublicCatalogRecord],
    assessments: dict[tuple[str, str], PublicAssessment],
) -> str:
    cards: list[str] = []
    for repository in brief.candidate_repositories:
        record = records[repository]
        assessment = assessments[(brief.problem_id, repository)]
        covers = "; ".join(assessment.covers)
        watch = "; ".join(assessment.watch)
        unknowns = "; ".join(assessment.unknowns)
        caution_label = "Watch" if watch else "Unknown"
        caution = watch or unknowns
        if watch and unknowns:
            caution = f"{watch} Unknown: {unknowns}"
        cards.append(
            f"""<article class="catalog-card assessment-card">
  <h2>{html.escape(repository)}</h2>
  <p>{html.escape(record.description)}</p>
  <p><strong>Covers:</strong> {html.escape(covers)}</p>
  <p><strong>{caution_label}:</strong> {html.escape(caution)}</p>
  <p class="catalog-card__evidence">Checked {html.escape(_checked_date(record.last_checked_at))} · <a href="{html.escape(record.url, quote=True)}">Repository</a> · <a href="../evidence/{_repository_slug(repository)}.md#{html.escape(brief.problem_id, quote=True)}">Evidence</a></p>
</article>"""
        )
    covered = "\n".join(f"- {_markdown_text(item)}" for item in brief.what_appears_covered)
    unresolved = "\n".join(f"- {_markdown_text(item)}" for item in brief.what_remains_unresolved)
    evidence = "\n".join(
        f"- {_evidence_anchor(locator, depth=2)}" for locator in brief.evidence_refs
    )
    return (
        _frontmatter(brief.title, problem.question, problem.domains)
        + f"""# {_markdown_text(brief.title)}

## Problem

{_markdown_text(problem.question)}

## Approaches worth knowing

<div class="catalog-grid">
{chr(10).join(cards)}
</div>

## What appears covered

{covered}

## What still appears unresolved

{unresolved}

Based on the reviewed evidence, that residual work may still justify a focused build. This brief
does not rank the candidates or imply certainty beyond the cited evidence.

Checked {_markdown_text(_checked_date(brief.checked_at))} · [Explore all briefs](../index.md)

<details>
<summary>Brief research evidence</summary>

{evidence}

</details>
"""
    )


def _evidence_markdown(
    record: PublicCatalogRecord,
    briefs: tuple[PublicBrief, ...],
    problems: dict[str, PublicProblem],
    assessments: dict[tuple[str, str], PublicAssessment],
) -> str:
    sections: list[str] = []
    for brief in briefs:
        if record.repository not in brief.candidate_repositories:
            continue
        assessment = assessments[(brief.problem_id, record.repository)]
        covers = "\n".join(f"- {_markdown_text(item)}" for item in assessment.covers)
        watch = "\n".join(f"- {_markdown_text(item)}" for item in assessment.watch)
        unknowns = "\n".join(f"- {_markdown_text(item)}" for item in assessment.unknowns)
        evidence = "\n".join(
            f"- {_evidence_anchor(locator, depth=2)}" for locator in assessment.evidence_refs
        )
        sections.append(
            f"""<a id="{html.escape(brief.problem_id, quote=True)}"></a>
## {_markdown_text(brief.title)}

**Problem:** {_markdown_text(problems[brief.problem_id].question)}

### Covers

{covers}

### Watch

{watch or "- No separate watch item; see explicit uncertainty below."}

### Unknowns

{unknowns or "- No additional unknown recorded."}

### Assessment evidence

{evidence}

Assessed {_markdown_text(_checked_date(assessment.assessed_at))} ·
[Return to brief](../briefs/{brief.problem_id}.md)
"""
        )
    source_links = "\n".join(
        f"- {_evidence_anchor(source.locator, depth=2)} — observed `{source.observed_at.isoformat()}`"
        for source in record.source_provenance
    )
    screening_links = "\n".join(
        f"- {_evidence_anchor(locator, depth=2)}" for locator in record.evidence_receipt_ids
    )
    return (
        _frontmatter(
            f"Evidence for {record.repository}",
            f"Problem-relative assessment and observed repository facts for {record.repository}.",
            record.collections,
            exclude_from_search=True,
        )
        + f"""# Evidence for {_markdown_text(record.repository)}

{_markdown_text(record.description)}

[Open repository]({html.escape(record.url, quote=True)}){{ .md-button .md-button--primary }}

{(chr(10) * 2).join(sections)}

<details>
<summary>Observed repository and provenance details</summary>

- **License:** {_markdown_text(record.observed_license or "unknown")}
- **Archived:** {_markdown_text(str(record.archived).lower() if record.archived is not None else "unknown")}
- **Latest release:** {_markdown_text(record.latest_release or "not recorded")}
- **Latest commit:** `{html.escape(record.latest_commit or "not recorded")}`
- **Last checked:** `{html.escape(record.last_checked_at)}`

### Screening evidence

{screening_links or "- No separate screening evidence link recorded."}

### Source provenance

{source_links}

</details>
"""
    )


def _sources_markdown(
    profile: CurationProfile,
    snapshot: CurationSnapshot,
    attributions: tuple[PublicAttribution, ...],
) -> str:
    sources = "\n".join(
        f"<li><code>{html.escape(item.locator)}</code> — SHA-256 "
        f"<code>{item.content_sha256}</code>; {item.entry_count} records</li>"
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


def _tags_markdown() -> str:
    return _frontmatter("Tags", "Browse catalog pages by domain and evidence state.", ("tags",)) + (
        "# Tags\n\nUse tags to combine domain and evidence views.\n\n<!-- material/tags -->\n"
    )


def _repository_slug(repository: str) -> str:
    return repository.replace("/", "--")


def _display_timestamp(value: datetime) -> str:
    rendered = value.isoformat(timespec="minutes")
    return f"{rendered.removesuffix('+00:00')} UTC" if rendered.endswith("+00:00") else rendered


def _checked_date(value: str) -> str:
    return value.split("T", 1)[0]


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
.assessment-card__problem { color: var(--sut-accent-strong) !important; font-size: .82rem; font-weight: 700; }
.catalog-card__evidence { border-top: 1px solid var(--sut-line); font-size: .82rem; margin-top: auto !important; padding-top: .65rem; }

.freshness-chip {
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

.freshness-chip--stale, .freshness-chip--partial { color: var(--sut-warm); }
.freshness-chip--blocked { color: #a32638; }

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
