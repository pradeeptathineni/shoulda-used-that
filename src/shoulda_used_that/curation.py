"""Versioned curation profiles and a deterministic snapshot compiler."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from shoulda_used_that import __version__
from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.errors import StateError
from shoulda_used_that.models import FrozenModel, normalize_repository

CURATION_SCHEMA_VERSION: Literal["2.0"] = "2.0"
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SOURCE_BYTES = 5 * 1024 * 1024


class CurationVisibility(StrEnum):
    """Whether a profile is private, public, or composed with a private overlay."""

    PRIVATE = "private"
    PUBLIC = "public"
    PUBLIC_WITH_PRIVATE_OVERLAY = "public-with-private-overlay"


class CurationDisposition(StrEnum):
    """Primary meaning of one repository in one curation context."""

    ADOPT = "adopt"
    TRIAL = "trial"
    REFERENCE = "reference"
    LEARN = "learn"
    WATCH = "watch"
    REJECT = "reject"
    BUILD = "build"
    INBOX = "inbox"


class FreshnessState(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    PARTIAL = "partial"
    BLOCKED = "blocked"


class CollectionDefinition(FrozenModel):
    """Durable collection semantics independent of a GitHub List."""

    slug: str
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    aliases: tuple[str, ...] = ()
    semantics: str = Field(min_length=1)
    inclusion_rule: str = Field(min_length=1)
    exclusion_rule: str = Field(min_length=1)
    exact_bound_sources: tuple[str, ...] = Field(min_length=1)
    max_candidates: int = Field(gt=0, le=10000)
    max_repositories: int = Field(gt=0, le=10000)
    github_list_projection: bool = False
    public_site_visibility: bool = True
    reconsideration_cadence_days: int = Field(gt=0, le=3650)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError("collection slug must use lowercase kebab-case")
        return value

    @field_validator("aliases", "exact_bound_sources", mode="before")
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            value = [value]
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))

    @model_validator(mode="after")
    def coherent_budgets(self) -> CollectionDefinition:
        if self.max_repositories > self.max_candidates:
            raise ValueError("max_repositories cannot exceed max_candidates")
        return self


class CurationSourceSpec(FrozenModel):
    """Exact public input bound into a profile."""

    kind: Literal["public-json"] = "public-json"
    locator: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str | None = None
    attribution: str | None = None


class ProjectionPolicy(FrozenModel):
    """Deliberately smaller public GitHub projection than the full catalog."""

    enabled: bool = False
    account: str | None = None
    selected_collection_slugs: tuple[str, ...] = ()
    max_projected_lists: int = Field(default=0, ge=0, le=20)

    @field_validator("selected_collection_slugs", mode="before")
    @classmethod
    def stable_slugs(cls, value: Any) -> tuple[str, ...]:
        return tuple(dict.fromkeys(str(item).strip() for item in value or () if str(item).strip()))


class ReviewPolicy(FrozenModel):
    """Deterministic freshness reference used by the compiler."""

    as_of: datetime
    default_freshness_days: int = Field(gt=0, le=3650)


class OperationCaps(FrozenModel):
    total: int = Field(gt=0, le=1000)
    create_lists: int = Field(ge=0, le=100)
    star_repositories: int = Field(ge=0, le=1000)
    add_memberships: int = Field(ge=0, le=5000)


class MutationPolicy(FrozenModel):
    additive_only: Literal[True] = True
    require_tty: Literal[True] = True
    forbid_ci: Literal[True] = True
    plan_expiry_hours: int = Field(gt=0, le=168)
    caps: OperationCaps


class CurationProfile(FrozenModel):
    """Human intent compiled into a curation snapshot."""

    schema_version: Literal["2.0"] = CURATION_SCHEMA_VERSION
    profile_id: str
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    public_owner_identity: str = Field(min_length=1)
    visibility: CurationVisibility
    source_specifications: tuple[CurationSourceSpec, ...] = Field(min_length=1)
    collections: tuple[CollectionDefinition, ...] = Field(min_length=1)
    projection_policy: ProjectionPolicy
    allowed_dispositions: tuple[CurationDisposition, ...] = Field(min_length=1)
    review_policy: ReviewPolicy
    popularity_treatment: str = Field(min_length=1)
    non_ranking_disclaimer: str = Field(min_length=1)
    publication_targets: tuple[str, ...] = Field(min_length=1)
    mutation_policy: MutationPolicy
    canonical_fingerprint: str = Field(pattern=r"^profile_[0-9a-f]{64}$")

    @field_validator("profile_id")
    @classmethod
    def valid_profile_id(cls, value: str) -> str:
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError("profile_id must use lowercase kebab-case")
        return value

    @field_validator("allowed_dispositions", mode="before")
    @classmethod
    def stable_dispositions(cls, value: Any) -> tuple[CurationDisposition, ...]:
        return tuple(
            sorted({CurationDisposition(item) for item in value}, key=lambda item: item.value)
        )

    @field_validator("publication_targets", mode="before")
    @classmethod
    def stable_targets(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))

    @model_validator(mode="after")
    def coherent_collections_and_projection(self) -> CurationProfile:
        source_locators = [item.locator for item in self.source_specifications]
        if len(source_locators) != len(set(source_locators)):
            raise ValueError("source locators must be unique")
        slugs = [item.slug for item in self.collections]
        if len(slugs) != len(set(slugs)):
            raise ValueError("collection slugs must be unique")
        searchable_names: set[str] = set()
        for collection in self.collections:
            unknown_sources = sorted(set(collection.exact_bound_sources) - set(source_locators))
            if unknown_sources:
                raise ValueError(
                    f"collection {collection.slug} references unknown sources: {unknown_sources}"
                )
            for name in (collection.title, *collection.aliases):
                folded = name.casefold()
                if folded in searchable_names:
                    raise ValueError(f"collection title or alias is ambiguous: {name}")
                searchable_names.add(folded)
        selected = self.projection_policy.selected_collection_slugs
        unknown = sorted(set(selected) - set(slugs))
        if unknown:
            raise ValueError(f"projection references unknown collections: {unknown}")
        if len(selected) > self.projection_policy.max_projected_lists:
            raise ValueError("selected projection collections exceed max_projected_lists")
        eligible = {item.slug for item in self.collections if item.github_list_projection}
        ineligible = sorted(set(selected) - eligible)
        if ineligible:
            raise ValueError(f"projection selects ineligible collections: {ineligible}")
        if not self.projection_policy.enabled and selected:
            raise ValueError("disabled projection policy cannot select collections")
        if self.projection_policy.enabled and not self.projection_policy.account:
            raise ValueError("enabled projection policy requires an exact account")
        if not self.projection_policy.enabled and self.projection_policy.max_projected_lists:
            raise ValueError("disabled projection policy must have a zero List cap")
        if set(self.allowed_dispositions) != set(CurationDisposition):
            raise ValueError("allowed_dispositions must explicitly enumerate every disposition")
        return self

    def identity_view(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"canonical_fingerprint"})


class PopularitySnapshot(FrozenModel):
    stars: int | None = Field(default=None, ge=0)
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def observed_stars_have_a_timestamp(self) -> PopularitySnapshot:
        if self.stars is not None and self.observed_at is None:
            raise ValueError("a star count requires an observation timestamp")
        return self


class SourceProvenance(FrozenModel):
    source: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    observed_at: datetime
    content_digest: str | None = None


class CurationEntry(FrozenModel):
    """One evidence-bound repository meaning in a curation context."""

    schema_version: Literal["2.0"] = CURATION_SCHEMA_VERSION
    repository: str
    url: str
    collection_memberships: tuple[str, ...]
    primary_disposition: CurationDisposition
    role: str = Field(min_length=1)
    need: str = Field(min_length=1)
    rationale: str = ""
    decision_receipt_ids: tuple[str, ...] = ()
    evidence_receipt_ids: tuple[str, ...] = ()
    observed_license: str | None = None
    archived: bool | None = None
    latest_release: str | None = None
    latest_commit: str | None = None
    popularity: PopularitySnapshot
    last_checked_at: datetime
    freshness_state: FreshnessState
    reconsideration_trigger: str = Field(min_length=1)
    source_provenance: tuple[SourceProvenance, ...] = Field(min_length=1)
    attribution_obligations: tuple[str, ...] = ()
    field_classification: Literal["public"] = "public"

    _normalize_repository = field_validator("repository")(normalize_repository)

    @field_validator(
        "collection_memberships",
        "decision_receipt_ids",
        "evidence_receipt_ids",
        "attribution_obligations",
        mode="before",
    )
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))

    @model_validator(mode="after")
    def reviewed_disposition_has_reason(self) -> CurationEntry:
        if self.primary_disposition is not CurationDisposition.INBOX and not (
            self.rationale or self.decision_receipt_ids
        ):
            raise ValueError("every non-inbox disposition needs a rationale or decision receipt")
        if (
            self.primary_disposition is not CurationDisposition.INBOX
            and not self.collection_memberships
        ):
            raise ValueError("every non-inbox disposition needs a collection membership")
        expected_url = f"https://github.com/{self.repository}"
        if self.url.casefold().rstrip("/") != expected_url:
            raise ValueError("entry URL must match the canonical public GitHub repository")
        return self


class ExcludedCandidate(FrozenModel):
    repository: str
    reason: str = Field(min_length=1)
    source: str = Field(min_length=1)

    _normalize_repository = field_validator("repository")(normalize_repository)


class CurationInput(FrozenModel):
    schema_version: Literal["2.0"] = CURATION_SCHEMA_VERSION
    entries: tuple[CurationEntry, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...] = ()


class CurationSourceSnapshot(FrozenModel):
    kind: str
    locator: str
    content_sha256: str
    entry_count: int = Field(ge=0)


class CurationCounts(FrozenModel):
    sources: int = Field(ge=0)
    entries: int = Field(ge=0)
    excluded: int = Field(ge=0)
    inbox: int = Field(ge=0)
    stale: int = Field(ge=0)
    partial: int = Field(ge=0)
    blocked: int = Field(ge=0)


class CurationSemanticDiff(FrozenModel):
    previous_snapshot_id: str | None = None
    profile_changed: bool = False
    added_repositories: tuple[str, ...] = ()
    removed_repositories: tuple[str, ...] = ()
    changed_repositories: tuple[str, ...] = ()
    added_exclusions: tuple[str, ...] = ()
    removed_exclusions: tuple[str, ...] = ()
    changed_exclusions: tuple[str, ...] = ()
    material: bool = False


class CurationSnapshot(FrozenModel):
    schema_version: Literal["2.0"] = CURATION_SCHEMA_VERSION
    curation_snapshot_id: str
    profile_id: str
    profile_fingerprint: str
    compiler_version: str
    compiled_at: datetime
    source_snapshots: tuple[CurationSourceSnapshot, ...]
    entries: tuple[CurationEntry, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...]
    unresolved_inbox_entries: tuple[str, ...]
    stale_entries: tuple[str, ...]
    partial_entries: tuple[str, ...]
    blocked_entries: tuple[str, ...]
    collection_membership_map: dict[str, tuple[str, ...]]
    counts: CurationCounts
    semantic_diff: CurationSemanticDiff
    canonical_fingerprint: str = Field(pattern=r"^curation_[0-9a-f]{64}$")


def profile_fingerprint(profile_payload: dict[str, Any]) -> str:
    """Return the canonical fingerprint for a profile payload without its fingerprint field."""

    semantic = {
        key: value for key, value in profile_payload.items() if key != "canonical_fingerprint"
    }
    return digest(semantic, prefix="profile")


def load_profile(path: Path) -> CurationProfile:
    payload = _read_json(path, maximum_bytes=MAX_SOURCE_BYTES)
    try:
        profile = CurationProfile.model_validate(payload)
    except ValidationError as exc:
        raise StateError(
            code="curation_profile_invalid",
            message=f"Curation profile {path.name} is invalid: {exc}",
        ) from exc
    expected = profile_fingerprint(payload)
    if profile.canonical_fingerprint != expected:
        raise StateError(
            code="curation_profile_fingerprint_mismatch",
            message="Curation profile fingerprint does not match its canonical public intent.",
            details={"expected": expected, "actual": profile.canonical_fingerprint},
        )
    return profile


def compile_profile(
    path: Path,
    *,
    previous: CurationSnapshot | None = None,
    source_root: Path | None = None,
) -> CurationSnapshot:
    """Compile exact profile inputs into a stable snapshot."""

    profile = load_profile(path)
    try:
        profile_path = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StateError(
            code="curation_profile_unreadable",
            message=f"Curation profile cannot be resolved: {path}: {exc}",
        ) from exc
    root = _resolve_root(source_root or _default_source_root(profile_path))
    collection_by_slug = {item.slug: item for item in profile.collections}
    source_snapshots: list[CurationSourceSnapshot] = []
    entries: dict[str, CurationEntry] = {}
    excluded: dict[str, ExcludedCandidate] = {}
    for source in profile.source_specifications:
        source_path = _resolve_source(root, source.locator)
        payload_bytes = _read_bytes(source_path, maximum_bytes=MAX_SOURCE_BYTES)
        content_sha256 = hashlib.sha256(payload_bytes).hexdigest()
        if content_sha256 != source.content_sha256:
            raise StateError(
                code="curation_source_drift",
                message=f"Curation source digest changed: {source.locator}",
                details={"expected": source.content_sha256, "actual": content_sha256},
            )
        try:
            document = CurationInput.model_validate_json(payload_bytes)
        except ValidationError as exc:
            raise StateError(
                code="curation_source_invalid",
                message=f"Curation source {source.locator} is invalid: {exc}",
            ) from exc
        source_snapshots.append(
            CurationSourceSnapshot(
                kind=source.kind,
                locator=source.locator,
                content_sha256=content_sha256,
                entry_count=len(document.entries),
            )
        )
        for raw_entry in document.entries:
            entry = _normalize_freshness(raw_entry, profile)
            unknown_collections = sorted(
                set(entry.collection_memberships) - set(collection_by_slug)
            )
            if unknown_collections:
                raise StateError(
                    code="curation_collection_unknown",
                    message=f"{entry.repository} references unknown collections.",
                    details={"collections": unknown_collections},
                )
            existing = entries.get(entry.repository)
            if existing is not None and existing != entry:
                raise StateError(
                    code="curation_disposition_conflict",
                    message=f"Conflicting curation claims for {entry.repository}.",
                )
            entries[entry.repository] = entry
        for candidate in document.excluded_candidates:
            existing_excluded = excluded.get(candidate.repository)
            if existing_excluded is not None and existing_excluded != candidate:
                raise StateError(
                    code="curation_exclusion_conflict",
                    message=f"Conflicting exclusion reasons for {candidate.repository}.",
                )
            excluded[candidate.repository] = candidate

    stable_entries = tuple(entries[key] for key in sorted(entries))
    membership_map = {
        slug: tuple(
            entry.repository for entry in stable_entries if slug in entry.collection_memberships
        )
        for slug in sorted(collection_by_slug)
    }
    for slug, repositories in membership_map.items():
        maximum = collection_by_slug[slug].max_repositories
        if len(repositories) > maximum:
            raise StateError(
                code="curation_collection_budget_exceeded",
                message=f"Collection {slug} exceeds its repository budget.",
                details={"count": len(repositories), "maximum": maximum},
            )

    inbox = tuple(
        entry.repository
        for entry in stable_entries
        if entry.primary_disposition is CurationDisposition.INBOX
    )
    stale = _repositories_with_freshness(stable_entries, FreshnessState.STALE)
    partial = _repositories_with_freshness(stable_entries, FreshnessState.PARTIAL)
    blocked = _repositories_with_freshness(stable_entries, FreshnessState.BLOCKED)
    stable_excluded = tuple(excluded[key] for key in sorted(excluded))
    counts = CurationCounts(
        sources=len(source_snapshots),
        entries=len(stable_entries),
        excluded=len(stable_excluded),
        inbox=len(inbox),
        stale=len(stale),
        partial=len(partial),
        blocked=len(blocked),
    )
    semantic = {
        "profile_fingerprint": profile.canonical_fingerprint,
        "compiler_version": __version__,
        "compiled_at": profile.review_policy.as_of.isoformat(),
        "source_snapshots": [item.model_dump(mode="json") for item in source_snapshots],
        "entries": [item.model_dump(mode="json") for item in stable_entries],
        "excluded_candidates": [item.model_dump(mode="json") for item in stable_excluded],
        "collection_membership_map": membership_map,
        "counts": counts.model_dump(mode="json"),
    }
    fingerprint = digest(semantic, prefix="curation")
    if previous is not None and previous.canonical_fingerprint == fingerprint:
        return previous
    diff = _semantic_diff(
        previous,
        profile_fingerprint=profile.canonical_fingerprint,
        current_entries=stable_entries,
        current_exclusions=stable_excluded,
    )
    return CurationSnapshot(
        curation_snapshot_id=short_id(semantic, prefix="cur"),
        profile_id=profile.profile_id,
        profile_fingerprint=profile.canonical_fingerprint,
        compiler_version=__version__,
        compiled_at=profile.review_policy.as_of,
        source_snapshots=tuple(source_snapshots),
        entries=stable_entries,
        excluded_candidates=stable_excluded,
        unresolved_inbox_entries=inbox,
        stale_entries=stale,
        partial_entries=partial,
        blocked_entries=blocked,
        collection_membership_map=membership_map,
        counts=counts,
        semantic_diff=diff,
        canonical_fingerprint=fingerprint,
    )


def _default_source_root(profile_path: Path) -> Path:
    if profile_path.parent.name == "profiles" and profile_path.parent.parent.name == "curation":
        return profile_path.parent.parent.parent
    return profile_path.parent


def _resolve_root(path: Path) -> Path:
    try:
        root_stat = path.lstat()
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StateError(
            code="curation_source_root_unreadable",
            message=f"Curation source root cannot be resolved: {path}: {exc}",
        ) from exc
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise StateError(
            code="curation_source_root_unsafe",
            message=f"Curation source root must be a non-symlink directory: {path}",
        )
    return resolved


def _resolve_source(root: Path, locator: str) -> Path:
    candidate = Path(locator)
    if candidate.is_absolute():
        raise StateError(
            code="curation_source_unsafe",
            message="Curation source locators must be portable relative paths.",
        )
    source_path = root / candidate
    try:
        resolved = source_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise StateError(
            code="curation_source_unreadable",
            message=f"Curation source cannot be resolved: {locator}: {exc}",
        ) from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise StateError(
            code="curation_source_unsafe",
            message=f"Curation source escapes the allowed root: {locator}",
        ) from exc
    return source_path


def _read_bytes(path: Path, *, maximum_bytes: int) -> bytes:
    try:
        initial_stat = path.lstat()
    except OSError as exc:
        raise StateError(
            code="curation_source_unreadable",
            message=f"Curation input cannot be read: {path.name}: {exc}",
        ) from exc
    if stat.S_ISLNK(initial_stat.st_mode) or not stat.S_ISREG(initial_stat.st_mode):
        raise StateError(
            code="curation_source_unsafe",
            message=f"Curation input must be a regular non-symlink file: {path.name}",
        )
    try:
        with path.open("rb") as stream:
            opened_stat = os.fstat(stream.fileno())
            same_file = (initial_stat.st_dev, initial_stat.st_ino) == (
                opened_stat.st_dev,
                opened_stat.st_ino,
            )
            if not stat.S_ISREG(opened_stat.st_mode) or not same_file:
                raise StateError(
                    code="curation_source_changed_during_read",
                    message=f"Curation input identity changed while opening: {path.name}",
                )
            payload = stream.read(maximum_bytes + 1)
    except StateError:
        raise
    except OSError as exc:
        raise StateError(
            code="curation_source_unreadable",
            message=f"Curation input cannot be read: {path.name}: {exc}",
        ) from exc
    if len(payload) > maximum_bytes:
        raise StateError(
            code="curation_source_too_large",
            message=f"Curation input exceeds {maximum_bytes} bytes: {path.name}",
        )
    return payload


def _read_json(path: Path, *, maximum_bytes: int) -> dict[str, Any]:
    try:
        payload = json.loads(_read_bytes(path, maximum_bytes=maximum_bytes))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError(
            code="curation_json_invalid",
            message=f"Curation JSON is unreadable: {path.name}: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise StateError(
            code="curation_json_invalid",
            message=f"Curation JSON must contain an object: {path.name}",
        )
    return payload


def _normalize_freshness(entry: CurationEntry, profile: CurationProfile) -> CurationEntry:
    if entry.last_checked_at > profile.review_policy.as_of:
        raise StateError(
            code="curation_entry_from_future",
            message=f"{entry.repository} was checked after the profile review time.",
        )
    if entry.freshness_state is not FreshnessState.CURRENT:
        return entry
    maximum_age = timedelta(days=profile.review_policy.default_freshness_days)
    if profile.review_policy.as_of - entry.last_checked_at > maximum_age:
        return entry.model_copy(update={"freshness_state": FreshnessState.STALE})
    return entry


def _repositories_with_freshness(
    entries: tuple[CurationEntry, ...], state: FreshnessState
) -> tuple[str, ...]:
    return tuple(entry.repository for entry in entries if entry.freshness_state is state)


def _semantic_diff(
    previous: CurationSnapshot | None,
    *,
    profile_fingerprint: str,
    current_entries: tuple[CurationEntry, ...],
    current_exclusions: tuple[ExcludedCandidate, ...],
) -> CurationSemanticDiff:
    if previous is None:
        added_repositories = tuple(item.repository for item in current_entries)
        added_exclusions = tuple(item.repository for item in current_exclusions)
        return CurationSemanticDiff(
            added_repositories=added_repositories,
            added_exclusions=added_exclusions,
            material=bool(added_repositories or added_exclusions),
        )
    before = {item.repository: item for item in previous.entries}
    after = {item.repository: item for item in current_entries}
    added = tuple(sorted(set(after) - set(before)))
    removed = tuple(sorted(set(before) - set(after)))
    changed = tuple(
        repository
        for repository in sorted(set(before) & set(after))
        if before[repository] != after[repository]
    )
    before_exclusions = {item.repository: item for item in previous.excluded_candidates}
    after_exclusions = {item.repository: item for item in current_exclusions}
    added_exclusions = tuple(sorted(set(after_exclusions) - set(before_exclusions)))
    removed_exclusions = tuple(sorted(set(before_exclusions) - set(after_exclusions)))
    changed_exclusions = tuple(
        repository
        for repository in sorted(set(before_exclusions) & set(after_exclusions))
        if before_exclusions[repository] != after_exclusions[repository]
    )
    profile_changed = previous.profile_fingerprint != profile_fingerprint
    return CurationSemanticDiff(
        previous_snapshot_id=previous.curation_snapshot_id,
        profile_changed=profile_changed,
        added_repositories=added,
        removed_repositories=removed,
        changed_repositories=changed,
        added_exclusions=added_exclusions,
        removed_exclusions=removed_exclusions,
        changed_exclusions=changed_exclusions,
        material=bool(
            profile_changed
            or added
            or removed
            or changed
            or added_exclusions
            or removed_exclusions
            or changed_exclusions
        ),
    )
