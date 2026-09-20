"""Versioned public records for the deterministic coordinator core."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION: Literal["1.0"] = "1.0"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def normalize_repository(value: str) -> str:
    """Return the canonical lowercase owner/repository identity."""

    normalized = value.strip().strip("/")
    if normalized.startswith("https://github.com/"):
        normalized = normalized.removeprefix("https://github.com/")
    normalized = normalized.strip("/").removesuffix(".git")
    if not REPOSITORY_PATTERN.fullmatch(normalized):
        raise ValueError("repository must use owner/name GitHub identity")
    return normalized.lower()


class FrozenModel(BaseModel):
    """Strict immutable base for receipt data."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @model_validator(mode="after")
    def timestamps_are_aware(self) -> FrozenModel:
        for name, value in self.__dict__.items():
            if isinstance(value, datetime) and value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
        return self


class EvidenceState(StrEnum):
    VERIFIED = "verified"
    CLAIM = "claim"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    STALE = "stale"
    ERROR = "error"


class SourceKind(StrEnum):
    FIXTURE = "fixture"
    STARS = "stars"
    GITHUB_SEARCH = "github-search"
    REPOSITORY = "repository"


class Disposition(StrEnum):
    ADOPT = "adopt"
    TRIAL = "trial"
    REFERENCE = "reference"
    LEARN = "learn"
    WATCH = "watch"
    REJECT = "reject"
    BUILD = "build"


class NetworkBoundary(StrEnum):
    LOCAL = "local"
    PUBLIC_API = "public-api"
    HOSTED = "hosted"
    UNKNOWN = "unknown"


class SecurityState(StrEnum):
    AVAILABLE = "available"
    VERIFIED = "verified"
    UNKNOWN = "unknown"
    STALE = "stale"
    ERROR = "error"


class DiffMateriality(StrEnum):
    IMMATERIAL = "immaterial"
    REFRESH_ONLY = "refresh-only"
    MATERIAL_REVIEW = "material-review"


class RecheckOutcome(StrEnum):
    SEMANTIC_NOOP = "semantic-no-op"
    REFRESH_ONLY = "refresh-only"
    MATERIAL_REVIEW_REQUIRED = "material-review-required"


class SourceRank(FrozenModel):
    """One upstream position preserved independently of local filtering and sorting."""

    source: str = Field(min_length=1)
    rank: int = Field(gt=0)


class Candidate(FrozenModel):
    """Canonical, source-neutral candidate used by filters and receipts."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    repository: str
    role: str = "repository"
    description: str | None = None
    language: str | None = None
    ecosystems: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    license: str | None = None
    archived: bool | None = None
    disabled: bool | None = None
    pushed_at: datetime | None = None
    released_at: datetime | None = None
    starred_at: datetime | None = None
    is_starred: bool | None = None
    platforms: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()
    evidence_state: EvidenceState = EvidenceState.UNKNOWN
    network_boundary: NetworkBoundary = NetworkBoundary.UNKNOWN
    security_state: SecurityState = SecurityState.UNKNOWN
    stars: int | None = Field(default=None, ge=0)
    url: str | None = None
    sources: tuple[str, ...] = ()
    source_ranks: tuple[SourceRank, ...] = ()
    conflicts: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        return normalize_repository(value)

    @field_validator(
        "ecosystems", "topics", "platforms", "runtimes", "sources", "conflicts", mode="before"
    )
    @classmethod
    def stable_strings(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = [value]
        try:
            items = list(value)
        except TypeError as exc:
            raise ValueError("set-like fields must be a string or iterable of strings") from exc
        return tuple(
            sorted({str(item).strip() for item in items if str(item).strip()}, key=str.casefold)
        )

    @field_validator("source_ranks")
    @classmethod
    def stable_source_ranks(cls, value: tuple[SourceRank, ...]) -> tuple[SourceRank, ...]:
        sources = [item.source for item in value]
        if len(sources) != len(set(sources)):
            raise ValueError("source ranks must contain at most one position per source")
        return tuple(sorted(value, key=lambda item: (item.source, item.rank)))

    def filter_view(self) -> dict[str, Any]:
        """Return the stable public shape exposed to JMESPath."""

        base = self.model_dump(mode="json", exclude={"conflicts"})
        base["repo"] = self.repository
        base["updated"] = base.pop("pushed_at")
        base["released"] = base.pop("released_at")
        base["security"] = {
            "state": self.security_state.value,
            **_json_mapping(self.metadata.get("security", {})),
        }
        base["evidence"] = {
            "state": self.evidence_state.value,
            **_json_mapping(self.metadata.get("evidence", {})),
        }
        return base


def _json_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class SourceRequest(FrozenModel):
    kind: SourceKind
    locator: str | None = None
    query: str | None = None


class SourceObservation(FrozenModel):
    kind: SourceKind
    locator: str | None = None
    query: str | None = None
    observed_at: datetime
    tool_version: str
    payload_fingerprint: str
    candidate_count: int = Field(ge=0)
    state: EvidenceState = EvidenceState.VERIFIED
    error_code: str | None = None
    error_message: str | None = None

    def identity_view(self) -> dict[str, Any]:
        """Exclude fetch time and error prose from semantic source identity."""

        return {
            "kind": self.kind.value,
            "locator": self.locator,
            "query": self.query,
            "tool_version": self.tool_version,
            "payload_fingerprint": self.payload_fingerprint,
            "candidate_count": self.candidate_count,
            "state": self.state.value,
            "error_code": self.error_code,
        }


class FilterSpec(FrozenModel):
    roles: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    ecosystems: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    license_allow: tuple[str, ...] = ()
    license_deny: tuple[str, ...] = ()
    not_archived: bool = False
    maintained_within_days: int | None = Field(default=None, gt=0)
    released_within_days: int | None = Field(default=None, gt=0)
    starred_within_days: int | None = Field(default=None, gt=0)
    platforms: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()
    evidence_states: tuple[EvidenceState, ...] = ()
    network_boundaries: tuple[NetworkBoundary, ...] = ()
    security_states: tuple[SecurityState, ...] = ()
    min_stars: int | None = Field(default=None, ge=0)
    where: str | None = None
    sort: tuple[str, ...] = ("repo",)
    limit: int = Field(default=5, gt=0, le=1000)

    _string_fields: ClassVar[tuple[str, ...]] = (
        "roles",
        "languages",
        "ecosystems",
        "topics",
        "license_allow",
        "license_deny",
        "platforms",
        "runtimes",
        "sort",
    )

    @field_validator(*_string_fields, mode="before")
    @classmethod
    def normalize_values(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str):
            value = [value]
        try:
            items = list(value)
        except TypeError as exc:
            raise ValueError("filter values must be a string or iterable of strings") from exc
        normalized = [str(item).strip() for item in items if str(item).strip()]
        return tuple(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def license_policy_is_coherent(self) -> FilterSpec:
        allowed = {item.casefold() for item in self.license_allow}
        denied = {item.casefold() for item in self.license_deny}
        overlap = allowed & denied
        if overlap:
            raise ValueError(f"license values cannot be both allowed and denied: {sorted(overlap)}")
        return self


class PredicateResult(FrozenModel):
    field: str
    operation: str
    expected: Any
    actual: Any = None
    category: Literal["hard-gate", "filter"]
    passed: bool
    unknown: bool = False
    reason: str


class ApplicabilityEvidence(FrozenModel):
    """Visible project/candidate comparison that never changes global popularity."""

    field: Literal["ecosystem", "language"]
    candidate_values: tuple[str, ...]
    project_values: tuple[str, ...]
    relationship: Literal["match", "mismatch", "unknown"]
    effect: Literal["evidence-only"] = "evidence-only"
    reason: str = Field(min_length=1)


class CandidateEvaluation(FrozenModel):
    candidate: Candidate
    included: bool
    reasons: tuple[PredicateResult, ...]
    applicability: tuple[ApplicabilityEvidence, ...] = ()


class CheckCounts(FrozenModel):
    raw: int = Field(ge=0)
    deduplicated: int = Field(ge=0)
    included_before_limit: int = Field(ge=0)
    visible: int = Field(ge=0)
    excluded: int = Field(ge=0)


class CheckReceipt(FrozenModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    check_id: str
    need: str = Field(min_length=1)
    profile: str
    created_at: datetime
    normalizer_version: str
    source_requests: tuple[SourceRequest, ...]
    source_observations: tuple[SourceObservation, ...]
    source_snapshot_fingerprint: str
    filter_spec: FilterSpec
    normalized_predicate_tree: dict[str, Any]
    unknown_policy: dict[str, str]
    evaluations: tuple[CandidateEvaluation, ...]
    result_repositories: tuple[str, ...]
    result_set_fingerprint: str
    ordering: tuple[str, ...]
    counts: CheckCounts
    project_snapshot_id: str | None = None
    project_snapshot_fingerprint: str | None = None
    project_target_identity: str | None = None

    @model_validator(mode="after")
    def project_context_is_complete(self) -> CheckReceipt:
        context = (
            self.project_snapshot_id,
            self.project_snapshot_fingerprint,
            self.project_target_identity,
        )
        if any(context) and not all(context):
            raise ValueError("project context identifiers must be present together")
        if self.project_snapshot_id and not re.fullmatch(
            r"psn_[0-9a-f]{24}", self.project_snapshot_id
        ):
            raise ValueError("project_snapshot_id has an invalid content identity")
        if self.project_snapshot_fingerprint and not re.fullmatch(
            r"project_[0-9a-f]{64}", self.project_snapshot_fingerprint
        ):
            raise ValueError("project_snapshot_fingerprint has an invalid content identity")
        return self


class DecisionReceipt(FrozenModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    decision_id: str
    created_at: datetime
    profile: str
    repository: str
    need: str = Field(min_length=1)
    disposition: Disposition
    rationale: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    alternatives: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()
    reconsider_when: tuple[str, ...]
    source_check_id: str | None = None
    source_result_fingerprint: str | None = None
    supersedes: str | None = None

    _normalize_repository = field_validator("repository")(normalize_repository)


class FieldDiff(FrozenModel):
    repository: str
    field: str
    before: Any = None
    after: Any = None
    materiality: DiffMateriality
    reason: str


class RecheckReceipt(FrozenModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    recheck_id: str
    checked_at: datetime
    profile: str
    target_id: str
    prior_check_id: str
    outcome: RecheckOutcome
    last_known_good_fingerprint: str
    current_fingerprint: str
    last_known_good_preserved: bool
    source_observations: tuple[SourceObservation, ...]
    diffs: tuple[FieldDiff, ...]
    source_errors: tuple[str, ...] = ()
