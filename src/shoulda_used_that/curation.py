"""Versioned curation profiles and a deterministic snapshot compiler."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Hashable
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from shoulda_used_that import __version__
from shoulda_used_that.canonical import digest, short_id
from shoulda_used_that.errors import StateError
from shoulda_used_that.models import FrozenModel, normalize_repository

CURATION_SCHEMA_VERSION: Literal["3.0"] = "3.0"
LEGACY_CURATION_SCHEMA_VERSION: Literal["2.0"] = "2.0"
CONTEXT_MODEL_VERSION: Literal["2.0"] = "2.0"
LEGACY_CONTEXT_MODEL_VERSION: Literal["1.0"] = "1.0"
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


class ScreeningBasis(StrEnum):
    """Why a candidate is retained before contextual assessment."""

    METADATA_AND_ELIGIBILITY = "metadata-and-eligibility"
    REVIEWED_USE_AND_PRIOR_ART = "reviewed-use-and-prior-art"
    LEGACY_MIGRATION = "legacy-migration"


class AssessmentBasis(StrEnum):
    """Evidence-bearing bases that can support contextual human judgment."""

    DOCUMENTED_USE = "documented-use"
    CAPABILITY_REVIEW = "capability-review"
    DECISION_RECORD = "decision-record"


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

    kind: Literal["public-json", "public-corpus-json", "public-context-json"] = "public-json"
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

    schema_version: Literal["2.0", "3.0"] = CURATION_SCHEMA_VERSION
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


class RepositoryEvidence(FrozenModel):
    """Reusable repository observations with no problem-specific judgment."""

    schema_version: Literal["1.0"] = "1.0"
    repository: str
    url: str
    description: str = Field(min_length=1)
    observed_license: str | None = None
    archived: bool | None = None
    latest_release: str | None = None
    latest_commit: str | None = None
    popularity: PopularitySnapshot
    last_checked_at: datetime
    freshness_state: FreshnessState
    source_provenance: tuple[SourceProvenance, ...] = Field(min_length=1)
    attribution_obligations: tuple[str, ...] = ()
    field_classification: Literal["public"] = "public"

    _normalize_repository = field_validator("repository")(normalize_repository)

    @field_validator("attribution_obligations", mode="before")
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))

    @model_validator(mode="after")
    def public_github_identity_matches(self) -> RepositoryEvidence:
        expected_url = f"https://github.com/{self.repository}"
        if self.url.casefold().rstrip("/") != expected_url:
            raise ValueError("repository evidence URL must match the canonical GitHub identity")
        return self


class CandidateScreening(FrozenModel):
    """A candidate retained by eligibility evidence, not a contextual fit claim."""

    schema_version: Literal["1.0"] = "1.0"
    repository: str
    domain_tags: tuple[str, ...] = Field(min_length=1)
    screening_basis: ScreeningBasis
    decision_receipt_ids: tuple[str, ...] = ()
    evidence_receipt_ids: tuple[str, ...] = Field(min_length=1)
    notes: tuple[str, ...] = ()
    screened_at: datetime

    _normalize_repository = field_validator("repository")(normalize_repository)

    @field_validator(
        "domain_tags",
        "decision_receipt_ids",
        "evidence_receipt_ids",
        "notes",
        mode="before",
    )
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))


class CurationProjectionEntry(FrozenModel):
    """Operator-only GitHub projection intent, separate from contextual assessment."""

    schema_version: Literal["1.0"] = "1.0"
    repository: str
    collection_memberships: tuple[str, ...]
    primary_disposition: CurationDisposition

    _normalize_repository = field_validator("repository")(normalize_repository)

    @field_validator("collection_memberships", mode="before")
    @classmethod
    def stable_memberships(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))

    @model_validator(mode="after")
    def reviewed_projection_has_membership(self) -> CurationProjectionEntry:
        if self.primary_disposition is not CurationDisposition.INBOX and not (
            self.collection_memberships
        ):
            raise ValueError("every non-inbox projection entry needs a collection membership")
        return self


class Problem(FrozenModel):
    """One concrete build need or question; domains remain optional taxonomy."""

    schema_version: Literal["1.0"] = "1.0"
    problem_id: str
    question: str = Field(min_length=12)
    domain_tags: tuple[str, ...] = ()

    @field_validator("problem_id")
    @classmethod
    def valid_problem_id(cls, value: str) -> str:
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError("problem_id must use lowercase kebab-case")
        return value

    @field_validator("question")
    @classmethod
    def concrete_question(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized.split()) < 3:
            raise ValueError("a problem must describe a concrete job or question")
        return normalized

    @field_validator("domain_tags", mode="before")
    @classmethod
    def stable_domain_tags(cls, value: Any) -> tuple[str, ...]:
        return tuple(sorted({str(item).strip() for item in value or () if str(item).strip()}))


class Assessment(FrozenModel):
    """Contextual judgment owned by exactly one problem and repository relation."""

    schema_version: Literal["1.0"] = "1.0"
    problem_id: str
    repository: str
    publication_state: Literal["assessed"] = "assessed"
    assessment_basis: AssessmentBasis
    covers: tuple[str, ...] = ()
    watch: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    decision_state: CurationDisposition | None = None
    reconsider_when: tuple[str, ...] = ()
    assessed_at: datetime

    _normalize_repository = field_validator("repository")(normalize_repository)

    @field_validator(
        "covers", "watch", "unknowns", "evidence_refs", "reconsider_when", mode="before"
    )
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        return tuple(dict.fromkeys(str(item).strip() for item in value or () if str(item).strip()))

    @model_validator(mode="after")
    def assessment_has_contextual_judgment(self) -> Assessment:
        if not (self.covers or self.watch or self.unknowns):
            raise ValueError("an assessment needs covers, watch, or explicit unknowns")
        return self


class Brief(FrozenModel):
    """A deliberately small prior-art answer for exactly one concrete problem."""

    schema_version: Literal["1.0"] = "1.0"
    problem_id: str
    title: str = Field(min_length=1, max_length=100)
    candidate_repositories: tuple[str, ...] = Field(min_length=3, max_length=5)
    what_appears_covered: tuple[str, ...] = Field(min_length=1)
    what_remains_unresolved: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    checked_at: datetime

    @field_validator("problem_id")
    @classmethod
    def valid_problem_id(cls, value: str) -> str:
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError("problem_id must use lowercase kebab-case")
        return value

    @field_validator("candidate_repositories", mode="before")
    @classmethod
    def unique_candidate_order(cls, value: Any) -> tuple[str, ...]:
        repositories = tuple(normalize_repository(str(item)) for item in value or ())
        if len(repositories) != len(set(repositories)):
            raise ValueError("brief candidates must be unique")
        return repositories

    @field_validator(
        "what_appears_covered", "what_remains_unresolved", "evidence_refs", mode="before"
    )
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        return tuple(dict.fromkeys(str(item).strip() for item in value or () if str(item).strip()))


class CurationEntry(FrozenModel):
    """Legacy v2 fact/context record retained only for migration and history."""

    schema_version: Literal["2.0"] = LEGACY_CURATION_SCHEMA_VERSION
    repository: str
    url: str
    description: str = Field(min_length=1)
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
    """Legacy v2 source document accepted for an evidence-preserving migration."""

    schema_version: Literal["2.0"] = LEGACY_CURATION_SCHEMA_VERSION
    entries: tuple[CurationEntry, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...] = ()


class CurationCorpusInput(FrozenModel):
    """Current source document with facts, screening, and projection intent separated."""

    schema_version: Literal["3.0"] = CURATION_SCHEMA_VERSION
    repository_evidence: tuple[RepositoryEvidence, ...]
    screenings: tuple[CandidateScreening, ...]
    projection_entries: tuple[CurationProjectionEntry, ...]
    excluded_candidates: tuple[ExcludedCandidate, ...] = ()


class CurationContextInput(FrozenModel):
    """Explicit problem and problem-by-repository assessment source."""

    schema_version: Literal["1.0", "2.0"] = CONTEXT_MODEL_VERSION
    problems: tuple[Problem, ...]
    assessments: tuple[Assessment, ...]
    briefs: tuple[Brief, ...] = ()

    @model_validator(mode="after")
    def legacy_context_has_no_briefs(self) -> CurationContextInput:
        if self.schema_version == LEGACY_CONTEXT_MODEL_VERSION and self.briefs:
            raise ValueError("context schema 1.0 cannot contain briefs")
        return self


class ContextCounts(FrozenModel):
    repositories: int = Field(ge=0)
    screenings: int = Field(ge=0)
    problems: int = Field(ge=0)
    assessments: int = Field(ge=0)
    briefs: int = Field(default=0, ge=0)
    screened_only_repositories: int = Field(ge=0)
    assessed_repositories: int = Field(ge=0)


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
    added_briefs: tuple[str, ...] = ()
    removed_briefs: tuple[str, ...] = ()
    changed_briefs: tuple[str, ...] = ()
    material: bool = False


class CurationSnapshot(FrozenModel):
    schema_version: Literal["2.0", "3.0"] = CURATION_SCHEMA_VERSION
    curation_snapshot_id: str
    profile_id: str
    profile_fingerprint: str
    compiler_version: str
    compiled_at: datetime
    collection_definitions: tuple[CollectionDefinition, ...]
    projection_policy: ProjectionPolicy
    mutation_policy: MutationPolicy
    source_snapshots: tuple[CurationSourceSnapshot, ...]
    # v2 snapshots keep their fused records readable here. Current v3 snapshots require this
    # compatibility field to be empty and use the separated structures below.
    entries: tuple[CurationEntry, ...]
    context_model_version: Literal["1.0", "2.0"] | None = None
    repository_evidence: tuple[RepositoryEvidence, ...] = ()
    screenings: tuple[CandidateScreening, ...] = ()
    projection_entries: tuple[CurationProjectionEntry, ...] = ()
    problems: tuple[Problem, ...] = ()
    assessments: tuple[Assessment, ...] = ()
    briefs: tuple[Brief, ...] = ()
    context_counts: ContextCounts | None = None
    excluded_candidates: tuple[ExcludedCandidate, ...]
    unresolved_inbox_entries: tuple[str, ...]
    stale_entries: tuple[str, ...]
    partial_entries: tuple[str, ...]
    blocked_entries: tuple[str, ...]
    collection_membership_map: dict[str, tuple[str, ...]]
    counts: CurationCounts
    semantic_diff: CurationSemanticDiff
    canonical_fingerprint: str = Field(pattern=r"^curation_[0-9a-f]{64}$")


def repository_evidence_records(snapshot: CurationSnapshot) -> tuple[RepositoryEvidence, ...]:
    """Return reusable evidence from current or historical curation snapshots."""

    if snapshot.schema_version == LEGACY_CURATION_SCHEMA_VERSION:
        return tuple(_repository_evidence_from_legacy(item) for item in snapshot.entries)
    return snapshot.repository_evidence


def candidate_screenings(snapshot: CurationSnapshot) -> tuple[CandidateScreening, ...]:
    """Return screening records without treating legacy rationale as assessment."""

    if snapshot.schema_version == LEGACY_CURATION_SCHEMA_VERSION:
        return tuple(_screening_from_legacy(item) for item in snapshot.entries)
    return snapshot.screenings


def curation_projection_entries(
    snapshot: CurationSnapshot,
) -> tuple[CurationProjectionEntry, ...]:
    """Return operator projection intent from current or historical snapshots."""

    if snapshot.schema_version == LEGACY_CURATION_SCHEMA_VERSION:
        return tuple(_projection_entry_from_legacy(item) for item in snapshot.entries)
    return snapshot.projection_entries


def validate_curation_snapshot(snapshot: CurationSnapshot) -> None:
    """Recompute derived fields and the sealed identity of a stored snapshot."""

    exclusions = tuple(sorted(snapshot.excluded_candidates, key=lambda item: item.repository))
    if exclusions != snapshot.excluded_candidates or len(
        {item.repository for item in exclusions}
    ) != len(exclusions):
        raise StateError(
            code="curation_snapshot_inconsistent",
            message="Curation exclusions are not a unique canonical repository sequence.",
        )

    collections = {item.slug: item for item in snapshot.collection_definitions}
    if snapshot.schema_version == LEGACY_CURATION_SCHEMA_VERSION:
        if any(
            (
                snapshot.context_model_version is not None,
                snapshot.repository_evidence,
                snapshot.screenings,
                snapshot.projection_entries,
                snapshot.problems,
                snapshot.assessments,
                snapshot.briefs,
                snapshot.context_counts is not None,
            )
        ):
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Legacy curation snapshots cannot contain v3 context fields.",
            )
        entries = tuple(sorted(snapshot.entries, key=lambda item: item.repository))
        if entries != snapshot.entries or len({item.repository for item in entries}) != len(
            entries
        ):
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Curation entries are not a unique canonical repository sequence.",
            )
        evidence = tuple(_repository_evidence_from_legacy(item) for item in entries)
        projection_entries = tuple(_projection_entry_from_legacy(item) for item in entries)
    else:
        if snapshot.entries or snapshot.context_model_version not in {
            LEGACY_CONTEXT_MODEL_VERSION,
            CONTEXT_MODEL_VERSION,
        }:
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Current curation snapshots require only the separated context model.",
            )
        if snapshot.context_model_version == LEGACY_CONTEXT_MODEL_VERSION and snapshot.briefs:
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Context model 1.0 cannot contain prior-art briefs.",
            )
        evidence = tuple(sorted(snapshot.repository_evidence, key=lambda item: item.repository))
        screenings = tuple(sorted(snapshot.screenings, key=lambda item: item.repository))
        projection_entries = tuple(
            sorted(snapshot.projection_entries, key=lambda item: item.repository)
        )
        problems = tuple(sorted(snapshot.problems, key=lambda item: item.problem_id))
        assessments = tuple(
            sorted(snapshot.assessments, key=lambda item: (item.problem_id, item.repository))
        )
        briefs = tuple(sorted(snapshot.briefs, key=lambda item: item.problem_id))
        if (
            evidence != snapshot.repository_evidence
            or screenings != snapshot.screenings
            or projection_entries != snapshot.projection_entries
            or problems != snapshot.problems
            or assessments != snapshot.assessments
            or briefs != snapshot.briefs
            or len({item.repository for item in evidence}) != len(evidence)
            or len({item.repository for item in screenings}) != len(screenings)
            or len({item.repository for item in projection_entries}) != len(projection_entries)
            or len({item.problem_id for item in problems}) != len(problems)
            or len({(item.problem_id, item.repository) for item in assessments}) != len(assessments)
            or len({item.problem_id for item in briefs}) != len(briefs)
        ):
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Separated curation records are not unique canonical sequences.",
            )
        repositories = {item.repository for item in evidence}
        if repositories != {item.repository for item in screenings} or repositories != {
            item.repository for item in projection_entries
        }:
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Evidence, screening, and projection repository sets must match.",
            )
        _validate_context_relationships(
            collections=collections,
            repositories=repositories,
            screenings=screenings,
            projection_entries=projection_entries,
            problems=problems,
            assessments=assessments,
            briefs=briefs,
        )

    expected_memberships = {
        slug: tuple(
            entry.repository for entry in projection_entries if slug in entry.collection_memberships
        )
        for slug in sorted(collections)
    }
    expected_inbox = tuple(
        item.repository
        for item in projection_entries
        if item.primary_disposition is CurationDisposition.INBOX
    )
    expected_stale = _repositories_with_freshness(evidence, FreshnessState.STALE)
    expected_partial = _repositories_with_freshness(evidence, FreshnessState.PARTIAL)
    expected_blocked = _repositories_with_freshness(evidence, FreshnessState.BLOCKED)
    expected_counts = CurationCounts(
        sources=len(snapshot.source_snapshots),
        entries=len(evidence),
        excluded=len(exclusions),
        inbox=len(expected_inbox),
        stale=len(expected_stale),
        partial=len(expected_partial),
        blocked=len(expected_blocked),
    )
    if (
        snapshot.collection_membership_map != expected_memberships
        or snapshot.unresolved_inbox_entries != expected_inbox
        or snapshot.stale_entries != expected_stale
        or snapshot.partial_entries != expected_partial
        or snapshot.blocked_entries != expected_blocked
        or snapshot.counts != expected_counts
    ):
        raise StateError(
            code="curation_snapshot_inconsistent",
            message="Curation snapshot derived fields do not match its sealed entries.",
        )

    if snapshot.schema_version == CURATION_SCHEMA_VERSION:
        assessed_repositories = {item.repository for item in snapshot.assessments}
        screened_repositories = {item.repository for item in snapshot.screenings}
        expected_context_counts = ContextCounts(
            repositories=len(snapshot.repository_evidence),
            screenings=len(snapshot.screenings),
            problems=len(snapshot.problems),
            assessments=len(snapshot.assessments),
            briefs=len(snapshot.briefs),
            screened_only_repositories=len(screened_repositories - assessed_repositories),
            assessed_repositories=len(assessed_repositories),
        )
        if snapshot.context_counts != expected_context_counts:
            raise StateError(
                code="curation_snapshot_inconsistent",
                message="Context counts do not match the separated curation records.",
            )

    semantic = _snapshot_semantic(
        schema_version=snapshot.schema_version,
        profile_fingerprint=snapshot.profile_fingerprint,
        compiler_version=snapshot.compiler_version,
        compiled_at=snapshot.compiled_at,
        collections=snapshot.collection_definitions,
        projection_policy=snapshot.projection_policy,
        mutation_policy=snapshot.mutation_policy,
        source_snapshots=snapshot.source_snapshots,
        entries=snapshot.entries,
        context_model_version=snapshot.context_model_version,
        repository_evidence=snapshot.repository_evidence,
        screenings=snapshot.screenings,
        projection_entries=snapshot.projection_entries,
        problems=snapshot.problems,
        assessments=snapshot.assessments,
        briefs=snapshot.briefs,
        context_counts=snapshot.context_counts,
        exclusions=exclusions,
        membership_map=expected_memberships,
        counts=expected_counts,
    )
    expected_fingerprint = digest(semantic, prefix="curation")
    expected_id = short_id(semantic, prefix="cur")
    if (
        snapshot.canonical_fingerprint != expected_fingerprint
        or snapshot.curation_snapshot_id != expected_id
    ):
        raise StateError(
            code="curation_snapshot_fingerprint_mismatch",
            message="Curation snapshot identity does not match its sealed semantic content.",
            details={
                "expected_id": expected_id,
                "expected_fingerprint": expected_fingerprint,
            },
        )


def profile_fingerprint(profile_payload: dict[str, Any]) -> str:
    """Return the canonical fingerprint for a profile payload without its fingerprint field."""

    semantic = {
        key: value for key, value in profile_payload.items() if key != "canonical_fingerprint"
    }
    return digest(semantic, prefix="profile")


def validate_curation_profile(profile: CurationProfile) -> None:
    """Verify that a validated profile still carries its normalized semantic identity."""

    expected = digest(profile.identity_view(), prefix="profile")
    if profile.canonical_fingerprint != expected:
        raise StateError(
            code="curation_profile_fingerprint_mismatch",
            message="Curation profile fingerprint does not match its normalized public intent.",
            details={"expected": expected, "actual": profile.canonical_fingerprint},
        )


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
    validate_curation_profile(profile)
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
    evidence_by_repository: dict[str, RepositoryEvidence] = {}
    screenings_by_repository: dict[str, CandidateScreening] = {}
    projection_by_repository: dict[str, CurationProjectionEntry] = {}
    problems_by_id: dict[str, Problem] = {}
    assessments_by_relation: dict[tuple[str, str], Assessment] = {}
    briefs_by_problem: dict[str, Brief] = {}
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
        corpus: CurationCorpusInput | None = None
        context: CurationContextInput | None = None
        try:
            if source.kind == "public-json":
                legacy = CurationInput.model_validate_json(payload_bytes)
                corpus = _migrate_legacy_input(legacy)
                record_count = len(legacy.entries)
            elif source.kind == "public-corpus-json":
                corpus = CurationCorpusInput.model_validate_json(payload_bytes)
                record_count = len(corpus.repository_evidence)
            else:
                context = CurationContextInput.model_validate_json(payload_bytes)
                record_count = (
                    len(context.problems) + len(context.assessments) + len(context.briefs)
                )
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
                entry_count=record_count,
            )
        )
        if corpus is not None:
            for raw_evidence in corpus.repository_evidence:
                evidence = _normalize_freshness(raw_evidence, profile)
                _merge_repository_record(
                    evidence_by_repository,
                    evidence.repository,
                    evidence,
                    conflict_code="curation_evidence_conflict",
                    label="repository evidence",
                )
            for screening in corpus.screenings:
                _merge_repository_record(
                    screenings_by_repository,
                    screening.repository,
                    screening,
                    conflict_code="curation_screening_conflict",
                    label="candidate screening",
                )
            for projection_entry in corpus.projection_entries:
                _merge_repository_record(
                    projection_by_repository,
                    projection_entry.repository,
                    projection_entry,
                    conflict_code="curation_disposition_conflict",
                    label="projection intent",
                )
            for candidate in corpus.excluded_candidates:
                _merge_repository_record(
                    excluded,
                    candidate.repository,
                    candidate,
                    conflict_code="curation_exclusion_conflict",
                    label="exclusion reason",
                )
        if context is not None:
            for problem in context.problems:
                _merge_repository_record(
                    problems_by_id,
                    problem.problem_id,
                    problem,
                    conflict_code="curation_problem_conflict",
                    label="problem definition",
                )
            for assessment in context.assessments:
                relation = (assessment.problem_id, assessment.repository)
                _merge_repository_record(
                    assessments_by_relation,
                    relation,
                    assessment,
                    conflict_code="curation_assessment_conflict",
                    label="contextual assessment",
                )
            for brief in context.briefs:
                _merge_repository_record(
                    briefs_by_problem,
                    brief.problem_id,
                    brief,
                    conflict_code="curation_brief_conflict",
                    label="prior-art brief",
                )

    stable_evidence = tuple(evidence_by_repository[key] for key in sorted(evidence_by_repository))
    stable_screenings = tuple(
        screenings_by_repository[key] for key in sorted(screenings_by_repository)
    )
    stable_projection_entries = tuple(
        projection_by_repository[key] for key in sorted(projection_by_repository)
    )
    stable_problems = tuple(problems_by_id[key] for key in sorted(problems_by_id))
    stable_assessments = tuple(
        assessments_by_relation[key] for key in sorted(assessments_by_relation)
    )
    stable_briefs = tuple(briefs_by_problem[key] for key in sorted(briefs_by_problem))
    _validate_context_relationships(
        collections=collection_by_slug,
        repositories={item.repository for item in stable_evidence},
        screenings=stable_screenings,
        projection_entries=stable_projection_entries,
        problems=stable_problems,
        assessments=stable_assessments,
        briefs=stable_briefs,
    )
    future_briefs = tuple(
        item.problem_id for item in stable_briefs if item.checked_at > profile.review_policy.as_of
    )
    if future_briefs:
        raise StateError(
            code="curation_brief_from_future",
            message="A prior-art brief was checked after the profile review time.",
            details={"problems": future_briefs},
        )
    if {item.repository for item in stable_evidence} != {
        item.repository for item in stable_projection_entries
    }:
        raise StateError(
            code="curation_projection_scope_mismatch",
            message="Every repository evidence record needs one operator projection entry.",
        )
    membership_map = {
        slug: tuple(
            entry.repository
            for entry in stable_projection_entries
            if slug in entry.collection_memberships
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
        for entry in stable_projection_entries
        if entry.primary_disposition is CurationDisposition.INBOX
    )
    stale = _repositories_with_freshness(stable_evidence, FreshnessState.STALE)
    partial = _repositories_with_freshness(stable_evidence, FreshnessState.PARTIAL)
    blocked = _repositories_with_freshness(stable_evidence, FreshnessState.BLOCKED)
    stable_excluded = tuple(excluded[key] for key in sorted(excluded))
    counts = CurationCounts(
        sources=len(source_snapshots),
        entries=len(stable_evidence),
        excluded=len(stable_excluded),
        inbox=len(inbox),
        stale=len(stale),
        partial=len(partial),
        blocked=len(blocked),
    )
    assessed_repositories = {item.repository for item in stable_assessments}
    screened_repositories = {item.repository for item in stable_screenings}
    context_counts = ContextCounts(
        repositories=len(stable_evidence),
        screenings=len(stable_screenings),
        problems=len(stable_problems),
        assessments=len(stable_assessments),
        briefs=len(stable_briefs),
        screened_only_repositories=len(screened_repositories - assessed_repositories),
        assessed_repositories=len(assessed_repositories),
    )
    semantic = _snapshot_semantic(
        schema_version=CURATION_SCHEMA_VERSION,
        profile_fingerprint=profile.canonical_fingerprint,
        compiler_version=__version__,
        compiled_at=profile.review_policy.as_of,
        collections=profile.collections,
        projection_policy=profile.projection_policy,
        mutation_policy=profile.mutation_policy,
        source_snapshots=tuple(source_snapshots),
        entries=(),
        context_model_version=CONTEXT_MODEL_VERSION,
        repository_evidence=stable_evidence,
        screenings=stable_screenings,
        projection_entries=stable_projection_entries,
        problems=stable_problems,
        assessments=stable_assessments,
        briefs=stable_briefs,
        context_counts=context_counts,
        exclusions=stable_excluded,
        membership_map=membership_map,
        counts=counts,
    )
    fingerprint = digest(semantic, prefix="curation")
    if previous is not None and previous.canonical_fingerprint == fingerprint:
        return previous
    diff = _semantic_diff(
        previous,
        profile_fingerprint=profile.canonical_fingerprint,
        current_evidence=stable_evidence,
        current_screenings=stable_screenings,
        current_projection_entries=stable_projection_entries,
        current_problems=stable_problems,
        current_assessments=stable_assessments,
        current_briefs=stable_briefs,
        current_exclusions=stable_excluded,
    )
    return CurationSnapshot(
        schema_version=CURATION_SCHEMA_VERSION,
        curation_snapshot_id=short_id(semantic, prefix="cur"),
        profile_id=profile.profile_id,
        profile_fingerprint=profile.canonical_fingerprint,
        compiler_version=__version__,
        compiled_at=profile.review_policy.as_of,
        collection_definitions=profile.collections,
        projection_policy=profile.projection_policy,
        mutation_policy=profile.mutation_policy,
        source_snapshots=tuple(source_snapshots),
        entries=(),
        context_model_version=CONTEXT_MODEL_VERSION,
        repository_evidence=stable_evidence,
        screenings=stable_screenings,
        projection_entries=stable_projection_entries,
        problems=stable_problems,
        assessments=stable_assessments,
        briefs=stable_briefs,
        context_counts=context_counts,
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


def _snapshot_semantic(
    *,
    schema_version: Literal["2.0", "3.0"] = LEGACY_CURATION_SCHEMA_VERSION,
    profile_fingerprint: str,
    compiler_version: str,
    compiled_at: datetime,
    collections: tuple[CollectionDefinition, ...],
    projection_policy: ProjectionPolicy,
    mutation_policy: MutationPolicy,
    source_snapshots: tuple[CurationSourceSnapshot, ...],
    entries: tuple[CurationEntry, ...],
    context_model_version: Literal["1.0", "2.0"] | None = None,
    repository_evidence: tuple[RepositoryEvidence, ...] = (),
    screenings: tuple[CandidateScreening, ...] = (),
    projection_entries: tuple[CurationProjectionEntry, ...] = (),
    problems: tuple[Problem, ...] = (),
    assessments: tuple[Assessment, ...] = (),
    briefs: tuple[Brief, ...] = (),
    context_counts: ContextCounts | None = None,
    exclusions: tuple[ExcludedCandidate, ...],
    membership_map: dict[str, tuple[str, ...]],
    counts: CurationCounts,
) -> dict[str, Any]:
    semantic: dict[str, Any] = {
        "profile_fingerprint": profile_fingerprint,
        "compiler_version": compiler_version,
        "compiled_at": compiled_at.isoformat(),
        "collection_definitions": [item.model_dump(mode="json") for item in collections],
        "projection_policy": projection_policy.model_dump(mode="json"),
        "mutation_policy": mutation_policy.model_dump(mode="json"),
        "source_snapshots": [item.model_dump(mode="json") for item in source_snapshots],
        "excluded_candidates": [item.model_dump(mode="json") for item in exclusions],
        "collection_membership_map": membership_map,
        "counts": counts.model_dump(mode="json"),
    }
    if schema_version == LEGACY_CURATION_SCHEMA_VERSION:
        semantic["entries"] = [item.model_dump(mode="json") for item in entries]
        return semantic
    semantic.update(
        {
            "schema_version": schema_version,
            "context_model_version": context_model_version,
            "repository_evidence": [item.model_dump(mode="json") for item in repository_evidence],
            "screenings": [item.model_dump(mode="json") for item in screenings],
            "projection_entries": [item.model_dump(mode="json") for item in projection_entries],
            "problems": [item.model_dump(mode="json") for item in problems],
            "assessments": [item.model_dump(mode="json") for item in assessments],
            "context_counts": _context_counts_semantic(
                context_counts, context_model_version=context_model_version
            ),
        }
    )
    if context_model_version == CONTEXT_MODEL_VERSION:
        semantic["briefs"] = [item.model_dump(mode="json") for item in briefs]
    return semantic


def _context_counts_semantic(
    context_counts: ContextCounts | None,
    *,
    context_model_version: Literal["1.0", "2.0"] | None,
) -> dict[str, Any] | None:
    if context_counts is None:
        return None
    payload = context_counts.model_dump(mode="json")
    if context_model_version == LEGACY_CONTEXT_MODEL_VERSION:
        payload.pop("briefs", None)
    return payload


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


def _repository_evidence_from_legacy(entry: CurationEntry) -> RepositoryEvidence:
    return RepositoryEvidence(
        repository=entry.repository,
        url=entry.url,
        description=entry.description,
        observed_license=entry.observed_license,
        archived=entry.archived,
        latest_release=entry.latest_release,
        latest_commit=entry.latest_commit,
        popularity=entry.popularity,
        last_checked_at=entry.last_checked_at,
        freshness_state=entry.freshness_state,
        source_provenance=entry.source_provenance,
        attribution_obligations=entry.attribution_obligations,
        field_classification=entry.field_classification,
    )


def _screening_from_legacy(entry: CurationEntry) -> CandidateScreening:
    evidence_refs = entry.evidence_receipt_ids or entry.decision_receipt_ids
    if not evidence_refs:
        evidence_refs = tuple(item.locator for item in entry.source_provenance)
    return CandidateScreening(
        repository=entry.repository,
        domain_tags=entry.collection_memberships,
        screening_basis=ScreeningBasis.LEGACY_MIGRATION,
        decision_receipt_ids=entry.decision_receipt_ids,
        evidence_receipt_ids=evidence_refs,
        screened_at=entry.last_checked_at,
    )


def _projection_entry_from_legacy(entry: CurationEntry) -> CurationProjectionEntry:
    return CurationProjectionEntry(
        repository=entry.repository,
        collection_memberships=entry.collection_memberships,
        primary_disposition=entry.primary_disposition,
    )


def _migrate_legacy_input(document: CurationInput) -> CurationCorpusInput:
    """Preserve v2 evidence while refusing to promote legacy prose into assessments."""

    return CurationCorpusInput(
        repository_evidence=tuple(
            _repository_evidence_from_legacy(item) for item in document.entries
        ),
        screenings=tuple(_screening_from_legacy(item) for item in document.entries),
        projection_entries=tuple(_projection_entry_from_legacy(item) for item in document.entries),
        excluded_candidates=document.excluded_candidates,
    )


def _merge_repository_record[KeyT: Hashable, RecordT](
    target: dict[KeyT, RecordT],
    key: KeyT,
    value: RecordT,
    *,
    conflict_code: str,
    label: str,
) -> None:
    existing = target.get(key)
    if existing is not None and existing != value:
        raise StateError(
            code=conflict_code,
            message=f"Conflicting {label} for {key}.",
        )
    target[key] = value


def _validate_context_relationships(
    *,
    collections: dict[str, CollectionDefinition],
    repositories: set[str],
    screenings: tuple[CandidateScreening, ...],
    projection_entries: tuple[CurationProjectionEntry, ...],
    problems: tuple[Problem, ...],
    assessments: tuple[Assessment, ...],
    briefs: tuple[Brief, ...] = (),
) -> None:
    screening_repositories = {item.repository for item in screenings}
    if screening_repositories != repositories:
        raise StateError(
            code="curation_screening_scope_mismatch",
            message="Every repository evidence record needs one candidate screening.",
        )
    collection_slugs = set(collections)
    for screening in screenings:
        unknown = sorted(set(screening.domain_tags) - collection_slugs)
        if unknown:
            raise StateError(
                code="curation_collection_unknown",
                message=f"{screening.repository} screening references unknown domains.",
                details={"collections": unknown},
            )
    for projection_entry in projection_entries:
        unknown = sorted(set(projection_entry.collection_memberships) - collection_slugs)
        if unknown:
            raise StateError(
                code="curation_collection_unknown",
                message=f"{projection_entry.repository} projection references unknown domains.",
                details={"collections": unknown},
            )
    domain_names = {
        value.casefold()
        for collection in collections.values()
        for value in (collection.slug, collection.title, *collection.aliases)
    }
    problem_by_id = {item.problem_id: item for item in problems}
    for problem in problems:
        unknown = sorted(set(problem.domain_tags) - collection_slugs)
        if unknown:
            raise StateError(
                code="curation_collection_unknown",
                message=f"Problem {problem.problem_id} references unknown domains.",
                details={"collections": unknown},
            )
        if problem.question.casefold().rstrip(".?") in domain_names:
            raise StateError(
                code="curation_problem_not_concrete",
                message=f"Problem {problem.problem_id} is only a domain label.",
            )
    for assessment in assessments:
        if assessment.repository not in repositories:
            raise StateError(
                code="curation_assessment_repository_unknown",
                message=(
                    f"Assessment {assessment.problem_id} references missing repository "
                    f"{assessment.repository}."
                ),
            )
        if assessment.problem_id not in problem_by_id:
            raise StateError(
                code="curation_assessment_problem_unknown",
                message=f"Assessment references missing problem {assessment.problem_id}.",
            )
    assessment_by_relation = {(item.problem_id, item.repository): item for item in assessments}
    for brief in briefs:
        if brief.problem_id not in problem_by_id:
            raise StateError(
                code="curation_brief_problem_unknown",
                message=f"Brief references missing problem {brief.problem_id}.",
            )
        selected: list[Assessment] = []
        for repository in brief.candidate_repositories:
            selected_assessment = assessment_by_relation.get((brief.problem_id, repository))
            if selected_assessment is None:
                raise StateError(
                    code="curation_brief_assessment_missing",
                    message=(f"Brief {brief.problem_id} lacks an assessment for {repository}."),
                )
            if not selected_assessment.covers or not (
                selected_assessment.watch or selected_assessment.unknowns
            ):
                raise StateError(
                    code="curation_brief_assessment_incomplete",
                    message=(
                        f"Brief candidate {repository} needs covers plus watch or uncertainty."
                    ),
                )
            body_words = sum(
                len(value.split())
                for value in (
                    *selected_assessment.covers,
                    *selected_assessment.watch,
                    *selected_assessment.unknowns,
                )
            )
            if body_words > 60:
                raise StateError(
                    code="curation_brief_candidate_too_long",
                    message=(
                        f"Brief candidate {repository} exceeds the 60-word information budget."
                    ),
                    details={"words": body_words},
                )
            selected.append(selected_assessment)
        repeated: dict[str, int] = {}
        for assessment in selected:
            for value in (*assessment.covers, *assessment.watch, *assessment.unknowns):
                normalized = " ".join(value.casefold().split())
                if len(normalized.split()) >= 4:
                    repeated[normalized] = repeated.get(normalized, 0) + 1
        excessive = tuple(text for text, count in repeated.items() if count > 3)
        if excessive:
            raise StateError(
                code="curation_brief_repeated_candidate_copy",
                message=(f"Brief {brief.problem_id} repeats substantive candidate copy too often."),
            )


def _normalize_freshness(
    evidence: RepositoryEvidence, profile: CurationProfile
) -> RepositoryEvidence:
    if evidence.last_checked_at > profile.review_policy.as_of:
        raise StateError(
            code="curation_entry_from_future",
            message=f"{evidence.repository} was checked after the profile review time.",
        )
    if evidence.freshness_state is not FreshnessState.CURRENT:
        return evidence
    maximum_age = timedelta(days=profile.review_policy.default_freshness_days)
    if profile.review_policy.as_of - evidence.last_checked_at > maximum_age:
        return evidence.model_copy(update={"freshness_state": FreshnessState.STALE})
    return evidence


def _repositories_with_freshness(
    entries: tuple[RepositoryEvidence, ...], state: FreshnessState
) -> tuple[str, ...]:
    return tuple(entry.repository for entry in entries if entry.freshness_state is state)


def _repository_semantics(
    *,
    evidence: tuple[RepositoryEvidence, ...],
    screenings: tuple[CandidateScreening, ...],
    projection_entries: tuple[CurationProjectionEntry, ...],
    problems: tuple[Problem, ...],
    assessments: tuple[Assessment, ...],
) -> dict[str, dict[str, Any]]:
    screening_by_repository = {item.repository: item for item in screenings}
    projection_by_repository = {item.repository: item for item in projection_entries}
    problem_by_id = {item.problem_id: item for item in problems}
    assessments_by_repository: dict[str, list[dict[str, Any]]] = {}
    for assessment in assessments:
        assessments_by_repository.setdefault(assessment.repository, []).append(
            {
                "problem": problem_by_id[assessment.problem_id].model_dump(mode="json"),
                "assessment": assessment.model_dump(mode="json"),
            }
        )
    return {
        item.repository: {
            "evidence": item.model_dump(mode="json"),
            "screening": screening_by_repository[item.repository].model_dump(mode="json"),
            "projection": projection_by_repository[item.repository].model_dump(mode="json"),
            "assessments": assessments_by_repository.get(item.repository, []),
        }
        for item in evidence
    }


def _snapshot_repository_semantics(snapshot: CurationSnapshot) -> dict[str, dict[str, Any]]:
    if snapshot.schema_version == LEGACY_CURATION_SCHEMA_VERSION:
        evidence = tuple(_repository_evidence_from_legacy(item) for item in snapshot.entries)
        screenings = tuple(_screening_from_legacy(item) for item in snapshot.entries)
        projections = tuple(_projection_entry_from_legacy(item) for item in snapshot.entries)
        return _repository_semantics(
            evidence=evidence,
            screenings=screenings,
            projection_entries=projections,
            problems=(),
            assessments=(),
        )
    return _repository_semantics(
        evidence=snapshot.repository_evidence,
        screenings=snapshot.screenings,
        projection_entries=snapshot.projection_entries,
        problems=snapshot.problems,
        assessments=snapshot.assessments,
    )


def _semantic_diff(
    previous: CurationSnapshot | None,
    *,
    profile_fingerprint: str,
    current_evidence: tuple[RepositoryEvidence, ...],
    current_screenings: tuple[CandidateScreening, ...],
    current_projection_entries: tuple[CurationProjectionEntry, ...],
    current_problems: tuple[Problem, ...],
    current_assessments: tuple[Assessment, ...],
    current_exclusions: tuple[ExcludedCandidate, ...],
    current_briefs: tuple[Brief, ...] = (),
) -> CurationSemanticDiff:
    current = _repository_semantics(
        evidence=current_evidence,
        screenings=current_screenings,
        projection_entries=current_projection_entries,
        problems=current_problems,
        assessments=current_assessments,
    )
    if previous is None:
        added_repositories = tuple(sorted(current))
        added_exclusions = tuple(item.repository for item in current_exclusions)
        added_briefs = tuple(item.problem_id for item in current_briefs)
        return CurationSemanticDiff(
            added_repositories=added_repositories,
            added_exclusions=added_exclusions,
            added_briefs=added_briefs,
            material=bool(added_repositories or added_exclusions or added_briefs),
        )
    before = _snapshot_repository_semantics(previous)
    added = tuple(sorted(set(current) - set(before)))
    removed = tuple(sorted(set(before) - set(current)))
    changed = tuple(
        repository
        for repository in sorted(set(before) & set(current))
        if before[repository] != current[repository]
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
    before_briefs = {item.problem_id: item for item in previous.briefs}
    after_briefs = {item.problem_id: item for item in current_briefs}
    added_briefs = tuple(sorted(set(after_briefs) - set(before_briefs)))
    removed_briefs = tuple(sorted(set(before_briefs) - set(after_briefs)))
    changed_briefs = tuple(
        problem_id
        for problem_id in sorted(set(before_briefs) & set(after_briefs))
        if before_briefs[problem_id] != after_briefs[problem_id]
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
        added_briefs=added_briefs,
        removed_briefs=removed_briefs,
        changed_briefs=changed_briefs,
        material=bool(
            profile_changed
            or added
            or removed
            or changed
            or added_exclusions
            or removed_exclusions
            or changed_exclusions
            or added_briefs
            or removed_briefs
            or changed_briefs
        ),
    )
