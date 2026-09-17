"""Bounded, read-only project and standards-based SBOM snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator, model_validator

from shoulda_used_that import __version__
from shoulda_used_that.canonical import canonical_bytes, digest, short_id
from shoulda_used_that.errors import (
    GitHubError,
    GitHubNotFoundError,
    GitHubSchemaError,
    SourceError,
    StateError,
)
from shoulda_used_that.github import GhClient, GhResult, GhSbomResult
from shoulda_used_that.models import (
    ApplicabilityEvidence,
    Candidate,
    FrozenModel,
    normalize_repository,
    utc_now,
)

PROJECT_SCHEMA_VERSION: Literal["2.0"] = "2.0"
MAX_LOCAL_FILES = 20_000
MAX_LOCAL_DEPTH = 20
MAX_MANIFESTS = 250
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_TOTAL_BYTES = 10 * 1024 * 1024
MAX_SBOM_BYTES = 10 * 1024 * 1024
MAX_SBOM_COMPONENTS = 10_000
SKIPPED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".release-smoke",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)


class ProjectTargetKind(StrEnum):
    GITHUB = "github"
    LOCAL = "local"


class ProjectEvidenceState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PENDING = "pending"
    PARTIAL = "partial"
    ERROR = "error"


class ProjectSourceReceipt(FrozenModel):
    receipt_id: str = Field(pattern=r"^src_[0-9a-f]{24}$")
    source_kind: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    observed_at: datetime
    tool_version: str = Field(min_length=1)
    state: ProjectEvidenceState
    payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reference: str | None = None
    error_code: str | None = None


class RepositoryProjectMetadata(FrozenModel):
    repository: str
    node_id: str | None = None
    visibility: Literal["public", "private", "internal", "unknown"]
    default_branch: str
    head_commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40,64}$")
    license: str | None = None
    archived: bool
    url: str

    _normalize_repository = field_validator("repository")(normalize_repository)


class ProjectLanguage(FrozenModel):
    name: str = Field(min_length=1)
    byte_count: int = Field(ge=0)


class ManifestFact(FrozenModel):
    relative_path: str = Field(min_length=1)
    ecosystem: str = Field(min_length=1)
    manifest_kind: Literal["manifest", "lockfile", "dependency-configuration"]
    byte_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("relative_path")
    @classmethod
    def portable_relative_path(cls, value: str) -> str:
        candidate = Path(value)
        if candidate.is_absolute() or ".." in candidate.parts or "\\" in value:
            raise ValueError("manifest paths must be portable paths beneath the target root")
        return candidate.as_posix()


class DependencyComponent(FrozenModel):
    identity: str = Field(min_length=1)
    component_type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str | None = None
    purl: str | None = None
    licenses: tuple[str, ...] = ()
    provenance: str = Field(min_length=1)

    @field_validator("licenses", mode="before")
    @classmethod
    def stable_licenses(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))


class SbomDescriptor(FrozenModel):
    format: Literal["spdx", "cyclonedx"]
    specification_version: str = Field(min_length=1)
    document_name: str | None = None
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    component_count: int = Field(ge=0)
    source_reference: str = Field(min_length=1)


class ProjectEvidenceGap(FrozenModel):
    code: str = Field(min_length=1)
    state: ProjectEvidenceState
    subject: str = Field(min_length=1)
    explanation: str = Field(min_length=1)


class ProjectSnapshot(FrozenModel):
    schema_version: Literal["2.0"] = PROJECT_SCHEMA_VERSION
    project_snapshot_id: str = Field(pattern=r"^psn_[0-9a-f]{24}$")
    target_kind: ProjectTargetKind
    target_identity: str = Field(min_length=1)
    observed_at: datetime
    inspector_version: str
    source_receipts: tuple[ProjectSourceReceipt, ...] = Field(min_length=1)
    repository_metadata: RepositoryProjectMetadata | None = None
    languages: tuple[ProjectLanguage, ...]
    topics: tuple[str, ...]
    ecosystems: tuple[str, ...]
    manifest_facts: tuple[ManifestFact, ...]
    dependency_components: tuple[DependencyComponent, ...]
    sbom: SbomDescriptor | None = None
    evidence_gaps: tuple[ProjectEvidenceGap, ...]
    inspected_file_count: int = Field(ge=0)
    inspected_byte_count: int = Field(ge=0)
    canonical_fingerprint: str = Field(pattern=r"^project_[0-9a-f]{64}$")

    @field_validator("topics", "ecosystems", mode="before")
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))

    @model_validator(mode="after")
    def relationships_and_fingerprint_are_coherent(self) -> ProjectSnapshot:
        if self.target_kind is ProjectTargetKind.GITHUB:
            if self.repository_metadata is None:
                raise ValueError("GitHub project snapshots require repository metadata")
            expected_identity = f"github:{self.repository_metadata.repository}"
            if self.target_identity != expected_identity:
                raise ValueError("GitHub target identity does not match repository metadata")
        elif self.repository_metadata is not None:
            raise ValueError("local project snapshots cannot contain GitHub repository metadata")
        for label, identities in (
            ("source receipt", [item.receipt_id for item in self.source_receipts]),
            ("language", [item.name.casefold() for item in self.languages]),
            ("manifest", [item.relative_path for item in self.manifest_facts]),
            ("component", [item.identity for item in self.dependency_components]),
        ):
            if len(identities) != len(set(identities)):
                raise ValueError(f"{label} identities must be unique")
        if self.sbom is None and self.dependency_components:
            raise ValueError("dependency components require an exact SBOM descriptor")
        if self.sbom is not None and self.sbom.component_count != len(self.dependency_components):
            raise ValueError("SBOM component count does not match normalized components")
        semantic = self.model_dump(
            mode="json", exclude={"project_snapshot_id", "canonical_fingerprint"}
        )
        expected_fingerprint = digest(semantic, prefix="project")
        expected_id = short_id(semantic, prefix="psn")
        if self.canonical_fingerprint != expected_fingerprint:
            raise ValueError("project snapshot canonical fingerprint does not match its content")
        if self.project_snapshot_id != expected_id:
            raise ValueError("project snapshot ID does not match its content")
        return self


class ProjectGitHub(Protocol):
    def repository(self, repository: str) -> GhResult: ...

    def repository_languages(self, repository: str) -> GhResult: ...

    def repository_commit(self, repository: str, reference: str) -> GhResult: ...

    def dependency_sbom(self, repository: str) -> GhSbomResult: ...


def inspect_project(
    target: str,
    *,
    sbom_path: Path | None = None,
    github: ProjectGitHub | None = None,
    observed_at: datetime | None = None,
) -> ProjectSnapshot:
    """Inspect only the explicit target and optional explicit SBOM."""

    timestamp = observed_at or utc_now()
    if target.startswith("github:"):
        repository = normalize_repository(target.removeprefix("github:"))
        return _inspect_github(
            repository,
            sbom_path=sbom_path,
            github=github or GhClient(),
            observed_at=timestamp,
        )
    if not target.strip():
        raise StateError(
            code="project_target_required",
            message="Project inspection requires an explicit GitHub target or local path.",
        )
    return _inspect_local(Path(target), sbom_path=sbom_path, observed_at=timestamp)


def applicability_evidence(
    candidate: Candidate, snapshot: ProjectSnapshot
) -> tuple[ApplicabilityEvidence, ...]:
    """Compare explicit candidate facts with project facts without hidden filtering."""

    project_languages = tuple(item.name for item in snapshot.languages)
    candidate_languages = (candidate.language,) if candidate.language else ()
    return (
        _applicability(
            field="ecosystem",
            candidate_values=candidate.ecosystems,
            project_values=snapshot.ecosystems,
        ),
        _applicability(
            field="language",
            candidate_values=candidate_languages,
            project_values=project_languages,
        ),
    )


def _inspect_github(
    repository: str,
    *,
    sbom_path: Path | None,
    github: ProjectGitHub,
    observed_at: datetime,
) -> ProjectSnapshot:
    receipts: list[ProjectSourceReceipt] = []
    gaps: list[ProjectEvidenceGap] = []
    metadata_result = github.repository(repository)
    metadata_payload = _require_mapping(metadata_result.payload, "repository metadata")
    full_name = metadata_payload.get("full_name")
    if not isinstance(full_name, str) or normalize_repository(full_name) != repository:
        raise GitHubSchemaError(
            code="github_repository_identity_mismatch",
            message="GitHub repository metadata did not match the explicit target.",
        )
    default_branch = metadata_payload.get("default_branch")
    archived = metadata_payload.get("archived")
    if not isinstance(default_branch, str) or not isinstance(archived, bool):
        raise GitHubSchemaError(
            code="github_repository_schema_invalid",
            message="GitHub repository metadata omitted default_branch or archived state.",
        )
    topics = _string_tuple(metadata_payload.get("topics"), label="repository topics")
    visibility = _visibility(metadata_payload)
    license_payload = metadata_payload.get("license")
    license_id = None
    if license_payload is not None:
        if not isinstance(license_payload, dict):
            raise GitHubSchemaError(
                code="github_repository_schema_invalid",
                message="GitHub repository license metadata was not an object or null.",
            )
        observed_license = license_payload.get("spdx_id")
        if isinstance(observed_license, str) and observed_license not in {"NOASSERTION", ""}:
            license_id = observed_license
    node_id = metadata_payload.get("node_id")
    if node_id is not None and not isinstance(node_id, str):
        raise GitHubSchemaError(
            code="github_repository_schema_invalid",
            message="GitHub repository node_id was not a string.",
        )
    receipts.append(
        _receipt(
            source_kind="github-repository",
            locator=f"github:{repository}",
            observed_at=observed_at,
            tool_version=f"gh/{metadata_result.tool_version}",
            state=ProjectEvidenceState.AVAILABLE,
            payload=metadata_payload,
        )
    )

    languages: tuple[ProjectLanguage, ...] = ()
    try:
        language_result = github.repository_languages(repository)
        language_payload = _require_mapping(language_result.payload, "repository languages")
        parsed_languages: list[ProjectLanguage] = []
        for name, byte_count in language_payload.items():
            if (
                not isinstance(name, str)
                or isinstance(byte_count, bool)
                or not isinstance(byte_count, int)
            ):
                raise GitHubSchemaError(
                    code="github_languages_schema_invalid",
                    message="GitHub repository languages contained an invalid byte count.",
                )
            parsed_languages.append(ProjectLanguage(name=name, byte_count=byte_count))
        languages = tuple(sorted(parsed_languages, key=lambda item: item.name.casefold()))
        receipts.append(
            _receipt(
                source_kind="github-languages",
                locator=f"github:{repository}:languages",
                observed_at=observed_at,
                tool_version=f"gh/{language_result.tool_version}",
                state=ProjectEvidenceState.AVAILABLE,
                payload=language_payload,
            )
        )
    except GitHubError as exc:
        receipts.append(
            _error_receipt("github-languages", f"github:{repository}:languages", observed_at, exc)
        )
        gaps.append(_github_gap("languages", exc))

    head_commit = None
    try:
        commit_result = github.repository_commit(repository, default_branch)
        commit_payload = _require_mapping(commit_result.payload, "repository commit")
        sha = commit_payload.get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            raise GitHubSchemaError(
                code="github_commit_schema_invalid",
                message="GitHub default-branch commit omitted a valid commit identity.",
            )
        head_commit = sha
        receipts.append(
            _receipt(
                source_kind="github-commit",
                locator=f"github:{repository}@{default_branch}",
                observed_at=observed_at,
                tool_version=f"gh/{commit_result.tool_version}",
                state=ProjectEvidenceState.AVAILABLE,
                payload=commit_payload,
            )
        )
    except GitHubError as exc:
        receipts.append(
            _error_receipt(
                "github-commit", f"github:{repository}@{default_branch}", observed_at, exc
            )
        )
        gaps.append(_github_gap("default-branch commit", exc))

    metadata = RepositoryProjectMetadata(
        repository=repository,
        node_id=node_id,
        visibility=visibility,
        default_branch=default_branch,
        head_commit=head_commit,
        license=license_id,
        archived=archived,
        url=f"https://github.com/{repository}",
    )
    sbom = None
    components: tuple[DependencyComponent, ...] = ()
    if sbom_path is not None:
        sbom, components, receipt = _read_sbom_file(sbom_path, observed_at=observed_at)
        receipts.append(receipt)
    else:
        try:
            report = github.dependency_sbom(repository)
            locator = f"github:{repository}:dependency-graph-sbom"
            if report.state == "pending":
                receipts.append(
                    _receipt(
                        source_kind="github-dependency-sbom",
                        locator=locator,
                        observed_at=observed_at,
                        tool_version=f"gh/{report.tool_version}",
                        state=ProjectEvidenceState.PENDING,
                        reference=f"report:{report.report_id}",
                    )
                )
                gaps.append(
                    ProjectEvidenceGap(
                        code="github_sbom_pending",
                        state=ProjectEvidenceState.PENDING,
                        subject="dependency inventory",
                        explanation="GitHub accepted the report request but it is not ready yet.",
                    )
                )
            else:
                if report.payload is None:  # pragma: no cover - dataclass contract guard
                    raise GitHubSchemaError(
                        code="github_sbom_schema_mismatch",
                        message="An available GitHub SBOM report omitted its document.",
                    )
                raw = canonical_bytes(report.payload)
                sbom, components = _parse_sbom_payload(
                    report.payload,
                    sha256=hashlib.sha256(raw).hexdigest(),
                    source_reference=f"github-report:{report.report_id}",
                )
                receipts.append(
                    _receipt(
                        source_kind="github-dependency-sbom",
                        locator=locator,
                        observed_at=observed_at,
                        tool_version=f"gh/{report.tool_version}",
                        state=ProjectEvidenceState.AVAILABLE,
                        payload=report.payload,
                        reference=f"report:{report.report_id}",
                    )
                )
        except GitHubNotFoundError as exc:
            receipts.append(
                _error_receipt(
                    "github-dependency-sbom",
                    f"github:{repository}:dependency-graph-sbom",
                    observed_at,
                    exc,
                    state=ProjectEvidenceState.UNAVAILABLE,
                )
            )
            gaps.append(
                ProjectEvidenceGap(
                    code="github_sbom_unavailable",
                    state=ProjectEvidenceState.UNAVAILABLE,
                    subject="dependency inventory",
                    explanation="GitHub did not expose a dependency-graph SBOM for this target.",
                )
            )
        except GitHubError as exc:
            receipts.append(
                _error_receipt(
                    "github-dependency-sbom",
                    f"github:{repository}:dependency-graph-sbom",
                    observed_at,
                    exc,
                )
            )
            gaps.append(_github_gap("dependency inventory", exc))

    ecosystems = _ecosystems((), components)
    return _snapshot(
        target_kind=ProjectTargetKind.GITHUB,
        target_identity=f"github:{repository}",
        observed_at=observed_at,
        receipts=tuple(receipts),
        repository_metadata=metadata,
        languages=languages,
        topics=topics,
        ecosystems=ecosystems,
        manifests=(),
        components=components,
        sbom=sbom,
        gaps=tuple(gaps),
        inspected_file_count=0,
        inspected_byte_count=0,
    )


def _inspect_local(
    target: Path, *, sbom_path: Path | None, observed_at: datetime
) -> ProjectSnapshot:
    root = _resolve_local_root(target)
    manifests, visited_files, inspected_bytes = _manifest_inventory(root)
    inventory_payload = [item.model_dump(mode="json") for item in manifests]
    receipts = [
        _receipt(
            source_kind="local-manifest-inventory",
            locator="local:manifest-inventory",
            observed_at=observed_at,
            tool_version=f"shoulda/{__version__}",
            state=ProjectEvidenceState.AVAILABLE,
            payload=inventory_payload,
            reference=f"visited-files:{visited_files}",
        )
    ]
    gaps = [
        ProjectEvidenceGap(
            code="local_language_topics_unavailable",
            state=ProjectEvidenceState.UNAVAILABLE,
            subject="languages and topics",
            explanation=(
                "Local inspection records bounded manifest facts only; it does not infer "
                "languages or topics."
            ),
        )
    ]
    sbom = None
    components: tuple[DependencyComponent, ...] = ()
    if sbom_path is not None:
        sbom, components, receipt = _read_sbom_file(sbom_path, observed_at=observed_at)
        receipts.append(receipt)
    else:
        gaps.append(
            ProjectEvidenceGap(
                code="sbom_not_supplied",
                state=ProjectEvidenceState.UNAVAILABLE,
                subject="dependency inventory",
                explanation=(
                    "No SPDX or CycloneDX document was supplied; external scanners are never "
                    "installed or run implicitly."
                ),
            )
        )
    ecosystems = _ecosystems(manifests, components)
    return _snapshot(
        target_kind=ProjectTargetKind.LOCAL,
        target_identity=f"local:{_logical_local_name(root.name)}",
        observed_at=observed_at,
        receipts=tuple(receipts),
        repository_metadata=None,
        languages=(),
        topics=(),
        ecosystems=ecosystems,
        manifests=manifests,
        components=components,
        sbom=sbom,
        gaps=tuple(gaps),
        inspected_file_count=visited_files,
        inspected_byte_count=inspected_bytes,
    )


def _snapshot(
    *,
    target_kind: ProjectTargetKind,
    target_identity: str,
    observed_at: datetime,
    receipts: tuple[ProjectSourceReceipt, ...],
    repository_metadata: RepositoryProjectMetadata | None,
    languages: tuple[ProjectLanguage, ...],
    topics: tuple[str, ...],
    ecosystems: tuple[str, ...],
    manifests: tuple[ManifestFact, ...],
    components: tuple[DependencyComponent, ...],
    sbom: SbomDescriptor | None,
    gaps: tuple[ProjectEvidenceGap, ...],
    inspected_file_count: int,
    inspected_byte_count: int,
) -> ProjectSnapshot:
    semantic = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "target_kind": target_kind.value,
        "target_identity": target_identity,
        "observed_at": _json_timestamp(observed_at),
        "inspector_version": __version__,
        "source_receipts": [item.model_dump(mode="json") for item in receipts],
        "repository_metadata": (
            repository_metadata.model_dump(mode="json") if repository_metadata else None
        ),
        "languages": [item.model_dump(mode="json") for item in languages],
        "topics": list(topics),
        "ecosystems": list(ecosystems),
        "manifest_facts": [item.model_dump(mode="json") for item in manifests],
        "dependency_components": [item.model_dump(mode="json") for item in components],
        "sbom": sbom.model_dump(mode="json") if sbom else None,
        "evidence_gaps": [item.model_dump(mode="json") for item in gaps],
        "inspected_file_count": inspected_file_count,
        "inspected_byte_count": inspected_byte_count,
    }
    return ProjectSnapshot(
        project_snapshot_id=short_id(semantic, prefix="psn"),
        target_kind=target_kind,
        target_identity=target_identity,
        observed_at=observed_at,
        inspector_version=__version__,
        source_receipts=receipts,
        repository_metadata=repository_metadata,
        languages=languages,
        topics=topics,
        ecosystems=ecosystems,
        manifest_facts=manifests,
        dependency_components=components,
        sbom=sbom,
        evidence_gaps=gaps,
        inspected_file_count=inspected_file_count,
        inspected_byte_count=inspected_byte_count,
        canonical_fingerprint=digest(semantic, prefix="project"),
    )


def _resolve_local_root(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        root_stat = expanded.lstat()
        resolved = expanded.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StateError(
            code="project_root_unreadable",
            message=f"Explicit local project root cannot be read: {exc}",
        ) from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise StateError(
            code="project_root_unsafe",
            message="Explicit local project root must be a non-symlink directory.",
        )
    return resolved


def _manifest_inventory(root: Path) -> tuple[tuple[ManifestFact, ...], int, int]:
    facts: list[ManifestFact] = []
    visited_files = 0
    inspected_bytes = 0
    for current, directories, filenames in os.walk(
        root, topdown=True, onerror=_raise_walk_error, followlinks=False
    ):
        current_path = Path(current)
        relative_directory = current_path.relative_to(root)
        if len(relative_directory.parts) > MAX_LOCAL_DEPTH:
            raise StateError(
                code="project_tree_too_deep",
                message=f"Local project exceeded the {MAX_LOCAL_DEPTH}-level traversal limit.",
            )
        kept_directories: list[str] = []
        for directory in sorted(directories):
            child = current_path / directory
            if child.is_symlink():
                _assert_symlink_contained(child, root)
                continue
            if directory in SKIPPED_DIRECTORIES:
                continue
            kept_directories.append(directory)
        directories[:] = kept_directories
        for filename in sorted(filenames):
            visited_files += 1
            if visited_files > MAX_LOCAL_FILES:
                raise StateError(
                    code="project_tree_too_large",
                    message=f"Local project exceeded the {MAX_LOCAL_FILES}-file traversal limit.",
                )
            path = current_path / filename
            if path.is_symlink():
                _assert_symlink_contained(path, root)
                continue
            relative = path.relative_to(root)
            descriptor = _manifest_descriptor(relative)
            if descriptor is None:
                continue
            raw = _read_regular_file(
                path,
                maximum_bytes=MAX_MANIFEST_BYTES,
                unsafe_code="project_manifest_unsafe",
                unreadable_code="project_manifest_unreadable",
                too_large_code="project_manifest_too_large",
            )
            inspected_bytes += len(raw)
            if inspected_bytes > MAX_MANIFEST_TOTAL_BYTES:
                raise StateError(
                    code="project_manifest_total_too_large",
                    message=(
                        "Local project manifests exceeded the "
                        f"{MAX_MANIFEST_TOTAL_BYTES}-byte total limit."
                    ),
                )
            ecosystem, manifest_kind = descriptor
            facts.append(
                ManifestFact(
                    relative_path=relative.as_posix(),
                    ecosystem=ecosystem,
                    manifest_kind=manifest_kind,
                    byte_count=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                )
            )
            if len(facts) > MAX_MANIFESTS:
                raise StateError(
                    code="project_manifest_count_exceeded",
                    message=f"Local project exceeded the {MAX_MANIFESTS}-manifest limit.",
                )
    return tuple(sorted(facts, key=lambda item: item.relative_path)), visited_files, inspected_bytes


def _manifest_descriptor(
    relative: Path,
) -> tuple[str, Literal["manifest", "lockfile", "dependency-configuration"]] | None:
    name = relative.name.casefold()
    exact: dict[str, tuple[str, Literal["manifest", "lockfile", "dependency-configuration"]]] = {
        "pyproject.toml": ("pypi", "manifest"),
        "uv.lock": ("pypi", "lockfile"),
        "poetry.lock": ("pypi", "lockfile"),
        "pdm.lock": ("pypi", "lockfile"),
        "pipfile": ("pypi", "manifest"),
        "pipfile.lock": ("pypi", "lockfile"),
        "package.json": ("npm", "manifest"),
        "package-lock.json": ("npm", "lockfile"),
        "npm-shrinkwrap.json": ("npm", "lockfile"),
        "yarn.lock": ("npm", "lockfile"),
        "pnpm-lock.yaml": ("npm", "lockfile"),
        "bun.lock": ("npm", "lockfile"),
        "bun.lockb": ("npm", "lockfile"),
        "cargo.toml": ("cargo", "manifest"),
        "cargo.lock": ("cargo", "lockfile"),
        "go.mod": ("golang", "manifest"),
        "go.sum": ("golang", "lockfile"),
        "pom.xml": ("maven", "manifest"),
        "build.gradle": ("maven", "manifest"),
        "build.gradle.kts": ("maven", "manifest"),
        "gemfile": ("gem", "manifest"),
        "gemfile.lock": ("gem", "lockfile"),
        "composer.json": ("composer", "manifest"),
        "composer.lock": ("composer", "lockfile"),
        "mix.exs": ("hex", "manifest"),
        "mix.lock": ("hex", "lockfile"),
        "package.swift": ("swift", "manifest"),
        "package.resolved": ("swift", "lockfile"),
        "packages.lock.json": ("nuget", "lockfile"),
        "directory.packages.props": ("nuget", "dependency-configuration"),
    }
    if name in exact:
        return exact[name]
    if re.fullmatch(r"requirements(?:[-_.][a-z0-9_.-]+)?\.txt", name):
        return "pypi", "manifest"
    if name.endswith((".csproj", ".fsproj", ".vbproj")):
        return "nuget", "manifest"
    return None


def _raise_walk_error(error: OSError) -> None:
    raise StateError(
        code="project_tree_unreadable",
        message=f"Local project traversal could not read an entry: {error}",
    )


def _assert_symlink_contained(path: Path, root: Path) -> None:
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise StateError(
            code="project_symlink_escape",
            message="A local project symlink escaped the explicit inspection root.",
        ) from exc


def _read_sbom_file(
    path: Path, *, observed_at: datetime
) -> tuple[SbomDescriptor, tuple[DependencyComponent, ...], ProjectSourceReceipt]:
    raw = _read_regular_file(
        path.expanduser(),
        maximum_bytes=MAX_SBOM_BYTES,
        unsafe_code="project_sbom_unsafe",
        unreadable_code="project_sbom_unreadable",
        too_large_code="project_sbom_too_large",
    )
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceError(
            code="project_sbom_invalid_json",
            message=f"Supplied SBOM is not valid UTF-8 JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise SourceError(
            code="project_sbom_invalid",
            message="Supplied SBOM must be a JSON object.",
        )
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    descriptor, components = _parse_sbom_payload(
        payload, sha256=raw_sha256, source_reference="supplied-sbom"
    )
    return (
        descriptor,
        components,
        _receipt(
            source_kind=f"{descriptor.format}-sbom",
            locator="supplied-sbom",
            observed_at=observed_at,
            tool_version=f"shoulda/{__version__}",
            state=ProjectEvidenceState.AVAILABLE,
            payload_sha256=raw_sha256,
        ),
    )


def _parse_sbom_payload(
    payload: dict[str, Any], *, sha256: str, source_reference: str
) -> tuple[SbomDescriptor, tuple[DependencyComponent, ...]]:
    spdx_version = payload.get("spdxVersion")
    if isinstance(spdx_version, str):
        if not re.fullmatch(r"SPDX-2\.[0-9]+", spdx_version):
            raise SourceError(
                code="project_spdx_version_unsupported",
                message=f"Unsupported SPDX version: {spdx_version}",
            )
        components = _spdx_components(payload, source_reference)
        descriptor = SbomDescriptor(
            format="spdx",
            specification_version=spdx_version,
            document_name=_optional_string(payload.get("name")),
            sha256=sha256,
            component_count=len(components),
            source_reference=source_reference,
        )
        return descriptor, components
    if payload.get("bomFormat") == "CycloneDX":
        specification_version = payload.get("specVersion")
        if not isinstance(specification_version, str) or not re.fullmatch(
            r"1\.[4-9][0-9]*", specification_version
        ):
            raise SourceError(
                code="project_cyclonedx_version_unsupported",
                message=f"Unsupported CycloneDX version: {specification_version}",
            )
        components = _cyclonedx_components(payload, source_reference)
        metadata = payload.get("metadata")
        document_name = None
        if isinstance(metadata, dict) and isinstance(metadata.get("component"), dict):
            document_name = _optional_string(metadata["component"].get("name"))
        descriptor = SbomDescriptor(
            format="cyclonedx",
            specification_version=specification_version,
            document_name=document_name,
            sha256=sha256,
            component_count=len(components),
            source_reference=source_reference,
        )
        return descriptor, components
    raise SourceError(
        code="project_sbom_format_unsupported",
        message="Supplied dependency inventory is neither SPDX JSON nor CycloneDX JSON.",
    )


def _spdx_components(payload: dict[str, Any], provenance: str) -> tuple[DependencyComponent, ...]:
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise SourceError(
            code="project_spdx_schema_invalid",
            message="SPDX document omitted its packages array.",
        )
    if len(packages) > MAX_SBOM_COMPONENTS:
        raise SourceError(
            code="project_sbom_component_limit",
            message=f"SBOM exceeded the {MAX_SBOM_COMPONENTS}-component limit.",
        )
    components: list[DependencyComponent] = []
    for package in packages:
        if not isinstance(package, dict) or not isinstance(package.get("name"), str):
            raise SourceError(
                code="project_spdx_schema_invalid",
                message="SPDX package omitted a string name.",
            )
        purl = None
        external_refs = package.get("externalRefs", [])
        if not isinstance(external_refs, list):
            raise SourceError(
                code="project_spdx_schema_invalid",
                message="SPDX package externalRefs was not an array.",
            )
        for reference in external_refs:
            if (
                isinstance(reference, dict)
                and str(reference.get("referenceType", "")).casefold() == "purl"
                and isinstance(reference.get("referenceLocator"), str)
            ):
                purl = reference["referenceLocator"]
                break
        name = package["name"].strip()
        if not name:
            raise SourceError(
                code="project_spdx_schema_invalid",
                message="SPDX package name cannot be empty.",
            )
        version = _optional_string(package.get("versionInfo"))
        component_type = _optional_string(package.get("primaryPackagePurpose")) or "package"
        licenses = tuple(
            value
            for value in (
                _normalized_license(package.get("licenseConcluded")),
                _normalized_license(package.get("licenseDeclared")),
            )
            if value
        )
        components.append(
            _component(
                component_type=component_type.casefold(),
                name=name,
                version=version,
                purl=purl,
                licenses=licenses,
                provenance=provenance,
            )
        )
    return _deduplicate_components(components)


def _cyclonedx_components(
    payload: dict[str, Any], provenance: str
) -> tuple[DependencyComponent, ...]:
    roots = payload.get("components")
    if not isinstance(roots, list):
        raise SourceError(
            code="project_cyclonedx_schema_invalid",
            message="CycloneDX document omitted its components array.",
        )
    pending: list[tuple[Any, int]] = [(item, 1) for item in reversed(roots)]
    components: list[DependencyComponent] = []
    while pending:
        raw_component, depth = pending.pop()
        if depth > MAX_LOCAL_DEPTH:
            raise SourceError(
                code="project_cyclonedx_depth_exceeded",
                message="CycloneDX component nesting exceeded the safety limit.",
            )
        if not isinstance(raw_component, dict) or not isinstance(raw_component.get("name"), str):
            raise SourceError(
                code="project_cyclonedx_schema_invalid",
                message="CycloneDX component omitted a string name.",
            )
        nested = raw_component.get("components", [])
        if not isinstance(nested, list):
            raise SourceError(
                code="project_cyclonedx_schema_invalid",
                message="Nested CycloneDX components was not an array.",
            )
        pending.extend((item, depth + 1) for item in reversed(nested))
        licenses = _cyclonedx_licenses(raw_component.get("licenses", []))
        components.append(
            _component(
                component_type=_optional_string(raw_component.get("type")) or "library",
                name=raw_component["name"],
                version=_optional_string(raw_component.get("version")),
                purl=_optional_string(raw_component.get("purl")),
                licenses=licenses,
                provenance=provenance,
            )
        )
        if len(components) + len(pending) > MAX_SBOM_COMPONENTS:
            raise SourceError(
                code="project_sbom_component_limit",
                message=f"SBOM exceeded the {MAX_SBOM_COMPONENTS}-component limit.",
            )
    return _deduplicate_components(components)


def _cyclonedx_licenses(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SourceError(
            code="project_cyclonedx_schema_invalid",
            message="CycloneDX component licenses was not an array.",
        )
    licenses: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        expression = _optional_string(item.get("expression"))
        if expression:
            licenses.add(expression)
        license_value = item.get("license")
        if isinstance(license_value, dict):
            identifier = _optional_string(license_value.get("id")) or _optional_string(
                license_value.get("name")
            )
            if identifier:
                licenses.add(identifier)
    return tuple(sorted(licenses))


def _component(
    *,
    component_type: str,
    name: str,
    version: str | None,
    purl: str | None,
    licenses: tuple[str, ...],
    provenance: str,
) -> DependencyComponent:
    cleaned_name = name.strip()
    cleaned_purl = purl.strip() if purl else None
    if cleaned_purl is not None and not cleaned_purl.startswith("pkg:"):
        raise SourceError(
            code="project_sbom_purl_invalid",
            message=f"SBOM component {cleaned_name} has an invalid package URL.",
        )
    identity = cleaned_purl or (
        f"{component_type.casefold()}:{cleaned_name.casefold()}@{version or 'unknown'}"
    )
    return DependencyComponent(
        identity=identity,
        component_type=component_type,
        name=cleaned_name,
        version=version,
        purl=cleaned_purl,
        licenses=licenses,
        provenance=provenance,
    )


def _deduplicate_components(
    components: list[DependencyComponent],
) -> tuple[DependencyComponent, ...]:
    deduplicated: dict[str, DependencyComponent] = {}
    for component in components:
        existing = deduplicated.get(component.identity)
        if existing is not None and existing != component:
            raise SourceError(
                code="project_sbom_component_conflict",
                message=f"SBOM contains conflicting claims for {component.identity}.",
            )
        deduplicated[component.identity] = component
    return tuple(deduplicated[key] for key in sorted(deduplicated, key=str.casefold))


def _read_regular_file(
    path: Path,
    *,
    maximum_bytes: int,
    unsafe_code: str,
    unreadable_code: str,
    too_large_code: str,
) -> bytes:
    try:
        initial_stat = path.lstat()
    except OSError as exc:
        raise SourceError(
            code=unreadable_code,
            message=f"Explicit input cannot be read: {exc}",
        ) from exc
    if stat.S_ISLNK(initial_stat.st_mode) or not stat.S_ISREG(initial_stat.st_mode):
        raise SourceError(
            code=unsafe_code,
            message="Explicit input must be a regular non-symlink file.",
        )
    try:
        with path.open("rb") as stream:
            opened_stat = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened_stat.st_mode) or (
                initial_stat.st_dev,
                initial_stat.st_ino,
            ) != (opened_stat.st_dev, opened_stat.st_ino):
                raise SourceError(
                    code=unsafe_code,
                    message="Explicit input identity changed while it was opened.",
                )
            raw = stream.read(maximum_bytes + 1)
    except SourceError:
        raise
    except OSError as exc:
        raise SourceError(
            code=unreadable_code,
            message=f"Explicit input cannot be read: {exc}",
        ) from exc
    if len(raw) > maximum_bytes:
        raise SourceError(
            code=too_large_code,
            message=f"Explicit input exceeded the {maximum_bytes}-byte safety limit.",
        )
    return raw


def _receipt(
    *,
    source_kind: str,
    locator: str,
    observed_at: datetime,
    tool_version: str,
    state: ProjectEvidenceState,
    payload: Any | None = None,
    payload_sha256: str | None = None,
    reference: str | None = None,
    error_code: str | None = None,
) -> ProjectSourceReceipt:
    if payload_sha256 is None and payload is not None:
        payload_sha256 = hashlib.sha256(canonical_bytes(payload)).hexdigest()
    seed = {
        "source_kind": source_kind,
        "locator": locator,
        "observed_at": observed_at.isoformat(),
        "tool_version": tool_version,
        "state": state.value,
        "payload_sha256": payload_sha256,
        "reference": reference,
        "error_code": error_code,
    }
    return ProjectSourceReceipt(
        receipt_id=short_id(seed, prefix="src"),
        source_kind=source_kind,
        locator=locator,
        observed_at=observed_at,
        tool_version=tool_version,
        state=state,
        payload_sha256=payload_sha256,
        reference=reference,
        error_code=error_code,
    )


def _error_receipt(
    source_kind: str,
    locator: str,
    observed_at: datetime,
    error: GitHubError,
    *,
    state: ProjectEvidenceState = ProjectEvidenceState.ERROR,
) -> ProjectSourceReceipt:
    return _receipt(
        source_kind=source_kind,
        locator=locator,
        observed_at=observed_at,
        tool_version="gh/unavailable",
        state=state,
        error_code=error.code,
    )


def _github_gap(subject: str, error: GitHubError) -> ProjectEvidenceGap:
    return ProjectEvidenceGap(
        code=error.code,
        state=ProjectEvidenceState.ERROR,
        subject=subject,
        explanation=f"GitHub evidence was unavailable: {error.code}.",
    )


def _applicability(
    *,
    field: Literal["ecosystem", "language"],
    candidate_values: tuple[str, ...],
    project_values: tuple[str, ...],
) -> ApplicabilityEvidence:
    candidate_folded = {item.casefold() for item in candidate_values}
    project_folded = {item.casefold() for item in project_values}
    if not candidate_folded or not project_folded:
        relationship: Literal["match", "mismatch", "unknown"] = "unknown"
        reason = "Candidate or project facts are unavailable; no applicability claim was inferred."
    elif candidate_folded & project_folded:
        relationship = "match"
        reason = "Candidate and project facts overlap."
    else:
        relationship = "mismatch"
        reason = "Known candidate and project facts do not overlap."
    return ApplicabilityEvidence(
        field=field,
        candidate_values=candidate_values,
        project_values=project_values,
        relationship=relationship,
        effect="evidence-only",
        reason=reason,
    )


def _visibility(payload: dict[str, Any]) -> Literal["public", "private", "internal", "unknown"]:
    value = payload.get("visibility")
    if value == "public":
        return "public"
    if value == "private":
        return "private"
    if value == "internal":
        return "internal"
    private = payload.get("private")
    if isinstance(private, bool):
        return "private" if private else "public"
    return "unknown"


def _ecosystems(
    manifests: tuple[ManifestFact, ...], components: tuple[DependencyComponent, ...]
) -> tuple[str, ...]:
    values = {item.ecosystem for item in manifests}
    for component in components:
        if component.purl:
            ecosystem = component.purl.removeprefix("pkg:").split("/", maxsplit=1)[0]
            if ecosystem:
                values.add(ecosystem)
    return tuple(sorted(values, key=str.casefold))


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubSchemaError(
            code="github_schema_mismatch",
            message=f"GitHub {label} was not a JSON object.",
        )
    return value


def _string_tuple(value: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
        raise GitHubSchemaError(
            code="github_repository_schema_invalid",
            message=f"GitHub {label} was not an array of strings.",
        )
    return tuple(sorted({item.strip() for item in value if item.strip()}, key=str.casefold))


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _normalized_license(value: Any) -> str | None:
    normalized = _optional_string(value)
    return None if normalized in {None, "NOASSERTION", "NONE"} else normalized


def _logical_local_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-.")
    return normalized.casefold() or "project"


def _json_timestamp(value: datetime) -> str:
    rendered = value.isoformat()
    return f"{rendered.removesuffix('+00:00')}Z" if rendered.endswith("+00:00") else rendered
