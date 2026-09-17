"""Explicit discovery source loading and deterministic normalization."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from shoulda_used_that import __version__
from shoulda_used_that.canonical import digest
from shoulda_used_that.errors import SourceError
from shoulda_used_that.github import GhClient
from shoulda_used_that.models import (
    Candidate,
    EvidenceState,
    NetworkBoundary,
    SourceKind,
    SourceObservation,
    SourceRequest,
    normalize_repository,
    utc_now,
)

MAX_FIXTURE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceBatch:
    request: SourceRequest
    observation: SourceObservation
    candidates: tuple[Candidate, ...]


def load_sources(
    requests: tuple[SourceRequest, ...],
    *,
    github: GhClient | None = None,
    observed_at: datetime | None = None,
) -> tuple[SourceBatch, ...]:
    """Load only the sources explicitly named in a check request."""

    timestamp = observed_at or utc_now()
    client = github or GhClient()
    batches: list[SourceBatch] = []
    for request in requests:
        if request.kind is SourceKind.FIXTURE:
            if not request.locator:
                raise SourceError(
                    code="fixture_required",
                    message="--source fixture requires at least one --fixture path.",
                )
            batches.append(_load_fixture(request, timestamp))
        elif request.kind is SourceKind.STARS:
            batches.append(_load_stars(request, client, timestamp))
        elif request.kind is SourceKind.GITHUB_SEARCH:
            if not request.query:
                raise SourceError(
                    code="query_required",
                    message="--source github-search requires at least one --query value.",
                )
            batches.append(_load_search(request, client, timestamp))
        elif request.kind is SourceKind.REPOSITORY:
            if not request.locator:
                raise SourceError(
                    code="repository_required",
                    message="--source repository requires at least one --repo owner/name.",
                )
            batches.append(_load_repository(request, client, timestamp))
        else:  # pragma: no cover - exhaustive StrEnum guard
            raise SourceError(
                code="unsupported_source", message=f"Unsupported source {request.kind}."
            )
    return tuple(batches)


def merge_batches(batches: tuple[SourceBatch, ...]) -> tuple[tuple[Candidate, ...], int]:
    """Deduplicate by canonical identity and preserve deterministic conflicts."""

    raw_count = sum(len(batch.candidates) for batch in batches)
    merged: dict[str, Candidate] = {}
    for batch in batches:
        for candidate in batch.candidates:
            existing = merged.get(candidate.repository)
            merged[candidate.repository] = (
                candidate if existing is None else _merge(existing, candidate)
            )
    return tuple(merged[key] for key in sorted(merged)), raw_count


def _load_fixture(request: SourceRequest, observed_at: datetime) -> SourceBatch:
    path = Path(request.locator or "")
    try:
        initial_stat = path.lstat()
    except OSError as exc:
        raise SourceError(
            code="fixture_unreadable",
            message=f"Fixture cannot be read: {path}: {exc}",
            details={"path": str(path)},
        ) from exc
    if stat.S_ISLNK(initial_stat.st_mode) or not stat.S_ISREG(initial_stat.st_mode):
        raise SourceError(
            code="fixture_not_regular_file",
            message=f"Fixture must be a regular non-symlink file: {path}",
            details={"path": str(path)},
        )
    try:
        with path.open("rb") as stream:
            opened_stat = os.fstat(stream.fileno())
            same_file = (initial_stat.st_dev, initial_stat.st_ino) == (
                opened_stat.st_dev,
                opened_stat.st_ino,
            )
            if not stat.S_ISREG(opened_stat.st_mode) or not same_file:
                raise SourceError(
                    code="fixture_changed_during_read",
                    message=f"Fixture identity changed while it was opened: {path}",
                    details={"path": str(path)},
                )
            raw = stream.read(MAX_FIXTURE_BYTES + 1)
    except SourceError:
        raise
    except OSError as exc:
        raise SourceError(
            code="fixture_unreadable",
            message=f"Fixture cannot be read: {path}: {exc}",
            details={"path": str(path)},
        ) from exc
    if len(raw) > MAX_FIXTURE_BYTES:
        raise SourceError(
            code="fixture_too_large",
            message=f"Fixture exceeds the {MAX_FIXTURE_BYTES}-byte safety limit: {path}",
            details={"path": str(path), "size": len(raw)},
        )
    try:
        if path.suffix.casefold() in {".yaml", ".yml"}:
            payload = yaml.safe_load(raw)
        else:
            payload = json.loads(raw)
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise SourceError(
            code="fixture_invalid",
            message=f"Fixture is not valid JSON or safe YAML: {path}: {exc}",
            details={"path": str(path)},
        ) from exc
    items = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise SourceError(
            code="fixture_schema_invalid",
            message=f"Fixture must be a list or an object with a candidates list: {path}",
        )
    source_id = f"fixture:{digest(raw.decode('utf-8'), prefix='src')}"
    candidates = _validate_candidates(items, source_id=source_id)
    observation = SourceObservation(
        kind=request.kind,
        locator=str(path),
        observed_at=observed_at,
        tool_version=f"shoulda/{__version__}",
        payload_fingerprint=digest(payload, prefix="payload"),
        candidate_count=len(candidates),
    )
    return SourceBatch(request, observation, candidates)


def _load_stars(request: SourceRequest, github: GhClient, observed_at: datetime) -> SourceBatch:
    result = github.starred()
    candidates: list[Candidate] = []
    for entry in result.payload:
        if not isinstance(entry, dict) or not isinstance(entry.get("repo"), dict):
            raise SourceError(
                code="github_star_schema_invalid",
                message="GitHub star response omitted the documented repo object.",
            )
        candidate = _github_candidate(
            entry["repo"],
            source_id="github:stars",
            starred_at=entry.get("starred_at"),
            is_starred=True,
        )
        candidates.append(candidate)
    observation = SourceObservation(
        kind=request.kind,
        observed_at=observed_at,
        tool_version=f"gh/{result.tool_version}",
        payload_fingerprint=digest(result.payload, prefix="payload"),
        candidate_count=len(candidates),
    )
    return SourceBatch(request, observation, tuple(candidates))


def _load_search(request: SourceRequest, github: GhClient, observed_at: datetime) -> SourceBatch:
    result = github.search(request.query or "", maximum=100)
    candidates = tuple(
        _github_candidate(item, source_id=f"github:search:{request.query}")
        for item in result.payload
    )
    observation = SourceObservation(
        kind=request.kind,
        query=request.query,
        observed_at=observed_at,
        tool_version=f"gh/{result.tool_version}",
        payload_fingerprint=digest(result.payload, prefix="payload"),
        candidate_count=len(candidates),
    )
    return SourceBatch(request, observation, candidates)


def _load_repository(
    request: SourceRequest, github: GhClient, observed_at: datetime
) -> SourceBatch:
    try:
        repository = normalize_repository(request.locator or "")
    except ValueError as exc:
        raise SourceError(
            code="repository_invalid",
            message="--repo must use an owner/name GitHub identity.",
            details={"repository": request.locator},
        ) from exc
    result = github.repository(repository)
    candidate = _github_candidate(result.payload, source_id=f"github:repo:{repository}")
    observation = SourceObservation(
        kind=request.kind,
        locator=repository,
        observed_at=observed_at,
        tool_version=f"gh/{result.tool_version}",
        payload_fingerprint=digest(result.payload, prefix="payload"),
        candidate_count=1,
    )
    return SourceBatch(request, observation, (candidate,))


def _github_candidate(
    item: Any,
    *,
    source_id: str,
    starred_at: str | None = None,
    is_starred: bool | None = None,
) -> Candidate:
    if not isinstance(item, dict) or not isinstance(item.get("full_name"), str):
        raise SourceError(
            code="github_repository_schema_invalid",
            message="GitHub repository response omitted the documented full_name field.",
        )
    license_data = item.get("license")
    license_id = license_data.get("spdx_id") if isinstance(license_data, dict) else None
    if license_id in {"NOASSERTION", "OTHER"}:
        license_id = None
    try:
        return Candidate(
            repository=item["full_name"],
            role="repository",
            description=item.get("description"),
            language=item.get("language"),
            topics=item.get("topics") or (),
            license=license_id,
            archived=item.get("archived"),
            disabled=item.get("disabled"),
            pushed_at=item.get("pushed_at"),
            starred_at=starred_at,
            is_starred=is_starred,
            evidence_state=EvidenceState.VERIFIED,
            network_boundary=NetworkBoundary.PUBLIC_API,
            stars=item.get("stargazers_count"),
            url=item.get("html_url"),
            sources=(source_id,),
        )
    except ValidationError as exc:
        raise SourceError(
            code="github_repository_schema_invalid",
            message="GitHub repository evidence did not match the canonical candidate schema.",
            details={"repository": item.get("full_name")},
        ) from exc


def _validate_candidates(items: list[Any], *, source_id: str) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SourceError(
                code="fixture_candidate_invalid",
                message=f"Fixture candidate {index} must be an object.",
            )
        try:
            candidate = Candidate.model_validate(item)
            candidates.append(
                Candidate.model_validate(
                    {
                        **candidate.model_dump(mode="python"),
                        "sources": (*candidate.sources, source_id),
                    }
                )
            )
        except ValidationError as exc:
            raise SourceError(
                code="fixture_candidate_invalid",
                message=f"Fixture candidate {index} is invalid: {exc}",
                details={"index": index},
            ) from exc
    return tuple(candidates)


def _merge(first: Candidate, second: Candidate) -> Candidate:
    first_data = first.model_dump(mode="python")
    second_data = second.model_dump(mode="python")
    conflicts = list(first.conflicts)
    scalar_fields = (
        "role",
        "description",
        "language",
        "license",
        "archived",
        "disabled",
        "pushed_at",
        "released_at",
        "starred_at",
        "is_starred",
        "network_boundary",
        "security_state",
        "stars",
        "url",
    )
    for field in scalar_fields:
        current = first_data[field]
        incoming = second_data[field]
        if _is_unknown(current) and not _is_unknown(incoming):
            first_data[field] = incoming
        elif not _is_unknown(current) and not _is_unknown(incoming) and current != incoming:
            conflicts.append(f"{field}: retained first observed value")
    for field in ("ecosystems", "topics", "platforms", "runtimes", "sources"):
        first_data[field] = tuple({*first_data[field], *second_data[field]})
    state_order = {
        EvidenceState.ERROR: 0,
        EvidenceState.UNKNOWN: 1,
        EvidenceState.STALE: 2,
        EvidenceState.CLAIM: 3,
        EvidenceState.INFERRED: 4,
        EvidenceState.VERIFIED: 5,
    }
    if state_order[second.evidence_state] > state_order[first.evidence_state]:
        first_data["evidence_state"] = second.evidence_state
    first_data["conflicts"] = tuple(conflicts)
    first_data["metadata"] = {**second.metadata, **first.metadata}
    return Candidate.model_validate(first_data)


def _is_unknown(value: Any) -> bool:
    if value is None or value == "":
        return True
    return hasattr(value, "value") and value.value == "unknown"
