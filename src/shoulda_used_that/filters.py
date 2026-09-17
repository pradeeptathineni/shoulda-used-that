"""Deterministic gate, filter, explanation, and ordering semantics."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timedelta
from typing import Any, Literal

import jmespath
from jmespath.exceptions import JMESPathError

from shoulda_used_that.canonical import digest
from shoulda_used_that.errors import FilterError
from shoulda_used_that.models import (
    Candidate,
    CandidateEvaluation,
    CheckCounts,
    EvidenceState,
    FilterSpec,
    NetworkBoundary,
    PredicateResult,
    SecurityState,
)

SUPPORTED_SORTS = {
    "repo",
    "updated",
    "released",
    "starred",
    "stars",
    "role",
    "language",
    "license",
}


def normalized_predicate_tree(spec: FilterSpec) -> dict[str, Any]:
    """Return the public normalized AND/OR tree stored in a check receipt."""

    predicates: list[dict[str, Any]] = []
    repeated = {
        "role": spec.roles,
        "language": spec.languages,
        "ecosystem": spec.ecosystems,
        "topic": spec.topics,
        "license_allow": spec.license_allow,
        "license_deny": spec.license_deny,
        "platform": spec.platforms,
        "runtime": spec.runtimes,
        "evidence_state": tuple(value.value for value in spec.evidence_states),
        "network_boundary": tuple(value.value for value in spec.network_boundaries),
        "security_state": tuple(value.value for value in spec.security_states),
    }
    for field, values in repeated.items():
        if values:
            predicates.append({"field": field, "operator": "or", "values": list(values)})
    scalar = {
        "not_archived": spec.not_archived or None,
        "maintained_within_days": spec.maintained_within_days,
        "released_within_days": spec.released_within_days,
        "starred_within_days": spec.starred_within_days,
        "min_stars": spec.min_stars,
        "where": spec.where,
    }
    for field, value in scalar.items():
        if value is not None:
            predicates.append({"field": field, "operator": "value", "value": value})
    return {
        "operator": "and",
        "precedence": ["explicit-exclusions", "hard-gates", "typed-filters", "where", "limit"],
        "predicates": predicates,
        "unknown_policy": {
            "hard_gate": "exclude",
            "soft_evidence": "retain unless explicitly filtered",
        },
        "pushdown": "source-specific optimization only; every predicate is re-evaluated locally",
    }


def evaluate_candidates(
    candidates: Sequence[Candidate],
    spec: FilterSpec,
    *,
    observed_at: datetime,
    raw_count: int,
) -> tuple[
    tuple[CandidateEvaluation, ...],
    tuple[Candidate, ...],
    str,
    CheckCounts,
]:
    """Apply exclusions, hard gates, filters, JMESPath, sorting, and limit."""

    compiled_where = None
    if spec.where:
        try:
            compiled_where = jmespath.compile(spec.where)
        except JMESPathError as exc:
            raise FilterError(
                code="invalid_where",
                message=f"Invalid JMESPath expression: {exc}",
                details={"expression": spec.where},
            ) from exc

    provisional: list[CandidateEvaluation] = []
    passing: list[Candidate] = []
    for candidate in candidates:
        reasons = list(_evaluate_typed(candidate, spec, observed_at=observed_at))
        if compiled_where is not None:
            try:
                where_value = compiled_where.search(candidate.filter_view())
            except JMESPathError as exc:
                raise FilterError(
                    code="where_evaluation_failed",
                    message=f"JMESPath evaluation failed for {candidate.repository}: {exc}",
                    details={"expression": spec.where, "repository": candidate.repository},
                ) from exc
            passed = bool(where_value)
            reasons.append(
                PredicateResult(
                    field="where",
                    operation="jmespath",
                    expected=spec.where,
                    actual=where_value,
                    category="filter",
                    passed=passed,
                    unknown=where_value is None,
                    reason=(
                        "advanced expression matched"
                        if passed
                        else "advanced expression did not match"
                    ),
                )
            )
        included = all(reason.passed for reason in reasons)
        provisional.append(
            CandidateEvaluation(candidate=candidate, included=included, reasons=tuple(reasons))
        )
        if included:
            passing.append(candidate)

    ordered = _stable_sort(passing, spec.sort)
    visible = ordered[: spec.limit]
    visible_ids = {candidate.repository for candidate in visible}
    evaluations: list[CandidateEvaluation] = []
    for evaluation in provisional:
        if evaluation.included and evaluation.candidate.repository not in visible_ids:
            evaluations.append(
                CandidateEvaluation(
                    candidate=evaluation.candidate,
                    included=False,
                    reasons=(
                        *evaluation.reasons,
                        PredicateResult(
                            field="limit",
                            operation="first_n",
                            expected=spec.limit,
                            actual="outside visible result window",
                            category="filter",
                            passed=False,
                            reason=(
                                "candidate passed predicates but was excluded by the stable limit"
                            ),
                        ),
                    ),
                )
            )
        else:
            evaluations.append(evaluation)

    result_fingerprint = digest(
        [candidate.model_dump(mode="json") for candidate in visible], prefix="rs"
    )
    counts = CheckCounts(
        raw=raw_count,
        deduplicated=len(candidates),
        included_before_limit=len(passing),
        visible=len(visible),
        excluded=len(candidates) - len(visible),
    )
    return tuple(evaluations), tuple(visible), result_fingerprint, counts


def _evaluate_typed(
    candidate: Candidate, spec: FilterSpec, *, observed_at: datetime
) -> Iterable[PredicateResult]:
    if spec.roles:
        yield _scalar_membership(
            "role", candidate.role, spec.roles, category="hard-gate", unknown=False
        )
    if spec.languages:
        yield _scalar_membership("language", candidate.language, spec.languages, category="filter")
    if spec.ecosystems:
        yield _set_membership("ecosystem", candidate.ecosystems, spec.ecosystems, category="filter")
    if spec.topics:
        yield _set_membership("topic", candidate.topics, spec.topics, category="filter")

    if spec.license_deny:
        denied = _fold(spec.license_deny)
        actual = candidate.license
        unknown = actual is None
        passed = actual is not None and actual.casefold() not in denied
        yield PredicateResult(
            field="license",
            operation="not_in",
            expected=list(spec.license_deny),
            actual=actual,
            category="hard-gate",
            passed=passed,
            unknown=unknown,
            reason=(
                "license is unknown and cannot pass a deny policy"
                if unknown
                else "license is explicitly denied"
                if not passed
                else "license is not denied"
            ),
        )
    if spec.license_allow:
        yield _scalar_membership(
            "license",
            candidate.license,
            spec.license_allow,
            category="hard-gate",
        )

    if spec.not_archived:
        unknown = candidate.archived is None or candidate.disabled is None
        passed = not unknown and not candidate.archived and not candidate.disabled
        yield PredicateResult(
            field="archived",
            operation="is_false",
            expected=False,
            actual={"archived": candidate.archived, "disabled": candidate.disabled},
            category="hard-gate",
            passed=passed,
            unknown=unknown,
            reason=(
                "archive or disabled state is unknown"
                if unknown
                else "repository is archived or disabled"
                if not passed
                else "repository is active"
            ),
        )

    yield from _freshness_predicate(
        "maintained_within_days",
        candidate.pushed_at,
        spec.maintained_within_days,
        observed_at,
    )
    yield from _freshness_predicate(
        "released_within_days",
        candidate.released_at,
        spec.released_within_days,
        observed_at,
    )
    yield from _freshness_predicate(
        "starred_within_days",
        candidate.starred_at,
        spec.starred_within_days,
        observed_at,
        category="filter",
    )

    if spec.platforms:
        yield _set_membership("platform", candidate.platforms, spec.platforms, category="hard-gate")
    if spec.runtimes:
        yield _set_membership("runtime", candidate.runtimes, spec.runtimes, category="hard-gate")
    if spec.evidence_states:
        yield _scalar_membership(
            "evidence_state",
            candidate.evidence_state,
            spec.evidence_states,
            category="filter",
            unknown=candidate.evidence_state is EvidenceState.UNKNOWN,
        )
    if spec.network_boundaries:
        yield _scalar_membership(
            "network_boundary",
            candidate.network_boundary,
            spec.network_boundaries,
            category="hard-gate",
            unknown=candidate.network_boundary is NetworkBoundary.UNKNOWN,
        )
    if spec.security_states:
        yield _scalar_membership(
            "security_state",
            candidate.security_state,
            spec.security_states,
            category="hard-gate",
            unknown=candidate.security_state is SecurityState.UNKNOWN,
        )
    if spec.min_stars is not None:
        unknown = candidate.stars is None
        passed = candidate.stars is not None and candidate.stars >= spec.min_stars
        yield PredicateResult(
            field="stars",
            operation="greater_than_or_equal",
            expected=spec.min_stars,
            actual=candidate.stars,
            category="filter",
            passed=passed,
            unknown=unknown,
            reason=(
                "star count is unknown"
                if unknown
                else "star count meets the weak popularity threshold"
                if passed
                else "star count is below the requested weak popularity threshold"
            ),
        )


def _scalar_membership(
    field: str,
    actual: Any,
    expected: Sequence[Any],
    *,
    category: Literal["hard-gate", "filter"],
    unknown: bool | None = None,
) -> PredicateResult:
    if unknown is None:
        unknown = actual is None
    actual_value = actual.value if hasattr(actual, "value") else actual
    expected_values = [value.value if hasattr(value, "value") else value for value in expected]
    passed = not unknown and str(actual_value).casefold() in _fold(expected_values)
    return PredicateResult(
        field=field,
        operation="in",
        expected=expected_values,
        actual=actual_value,
        category=category,
        passed=passed,
        unknown=unknown,
        reason=(
            f"{field} is unknown"
            if unknown
            else f"{field} matches one requested value"
            if passed
            else f"{field} does not match any requested value"
        ),
    )


def _set_membership(
    field: str,
    actual: Sequence[str],
    expected: Sequence[str],
    *,
    category: Literal["hard-gate", "filter"],
) -> PredicateResult:
    unknown = not actual
    matched = sorted(_fold(actual) & _fold(expected))
    passed = bool(matched)
    return PredicateResult(
        field=field,
        operation="intersects",
        expected=list(expected),
        actual=list(actual),
        category=category,
        passed=passed,
        unknown=unknown,
        reason=(
            f"{field} evidence is unknown"
            if unknown
            else f"{field} matched {matched}"
            if passed
            else f"{field} has no requested value"
        ),
    )


def _freshness_predicate(
    field: str,
    actual: datetime | None,
    days: int | None,
    observed_at: datetime,
    *,
    category: Literal["hard-gate", "filter"] = "hard-gate",
) -> Iterable[PredicateResult]:
    if days is None:
        return
    unknown = actual is None
    threshold = observed_at - timedelta(days=days)
    passed = actual is not None and actual >= threshold
    yield PredicateResult(
        field=field,
        operation="on_or_after",
        expected=threshold.isoformat(),
        actual=actual.isoformat() if actual else None,
        category=category,
        passed=passed,
        unknown=unknown,
        reason=(
            f"{field} evidence is unknown"
            if unknown
            else "freshness requirement passed"
            if passed
            else "freshness requirement failed"
        ),
    )


def _stable_sort(candidates: Sequence[Candidate], sort_fields: Sequence[str]) -> list[Candidate]:
    parsed: list[tuple[str, bool]] = []
    for raw in sort_fields or ("repo",):
        descending = raw.startswith("-")
        field = raw[1:] if descending else raw
        if field not in SUPPORTED_SORTS:
            raise FilterError(
                code="unsupported_sort",
                message=(
                    f"Unsupported sort field '{field}'. Supported: "
                    f"{', '.join(sorted(SUPPORTED_SORTS))}"
                ),
                details={"field": field},
            )
        if field != "repo":
            parsed.append((field, descending))

    ordered = sorted(candidates, key=lambda candidate: candidate.repository)
    for field, descending in reversed(parsed):
        known = [candidate for candidate in ordered if _sort_value(candidate, field) is not None]
        missing = [candidate for candidate in ordered if _sort_value(candidate, field) is None]
        known.sort(key=lambda candidate: _sort_value(candidate, field), reverse=descending)
        ordered = [*known, *missing]
    return ordered


def _sort_value(candidate: Candidate, field: str) -> Any:
    getters: dict[str, Callable[[Candidate], Any]] = {
        "repo": lambda item: item.repository,
        "updated": lambda item: item.pushed_at,
        "released": lambda item: item.released_at,
        "starred": lambda item: item.starred_at,
        "stars": lambda item: item.stars,
        "role": lambda item: item.role.casefold(),
        "language": lambda item: item.language.casefold() if item.language else None,
        "license": lambda item: item.license.casefold() if item.license else None,
    }
    return getters[field](candidate)


def _fold(values: Sequence[Any]) -> set[str]:
    return {str(value).casefold() for value in values}
