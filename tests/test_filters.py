from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from shoulda_used_that.errors import FilterError
from shoulda_used_that.filters import evaluate_candidates, normalized_predicate_tree
from shoulda_used_that.models import Candidate, FilterSpec

NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def _candidate(name: str, **changes: object) -> Candidate:
    values: dict[str, object] = {
        "repository": f"fixtures/{name}",
        "role": "library",
        "language": "Python",
        "ecosystems": ("pypi",),
        "topics": ("receipts",),
        "license": "Apache-2.0",
        "archived": False,
        "disabled": False,
        "pushed_at": NOW - timedelta(days=10),
        "released_at": NOW - timedelta(days=20),
        "platforms": ("linux",),
        "runtimes": ("python",),
        "evidence_state": "verified",
        "network_boundary": "local",
        "security_state": "verified",
        "stars": 10,
    }
    values.update(changes)
    return Candidate.model_validate(values)


def _visible(candidates: list[Candidate], spec: FilterSpec) -> tuple[str, ...]:
    _, visible, _, _ = evaluate_candidates(
        candidates, spec, observed_at=NOW, raw_count=len(candidates)
    )
    return tuple(item.repository for item in visible)


def test_default_result_window_is_five() -> None:
    candidates = [_candidate(str(index)) for index in range(7)]
    assert FilterSpec().limit == 5
    assert len(_visible(candidates, FilterSpec())) == 5


def test_repeated_values_are_or_and_fields_are_and() -> None:
    candidates = [
        _candidate("python", language="Python", topics=("receipts",)),
        _candidate("go", language="Go", topics=("receipts",)),
        _candidate("wrong-topic", language="Python", topics=("other",)),
    ]
    spec = FilterSpec(languages=("Python", "Go"), topics=("receipts",))

    assert _visible(candidates, spec) == ("fixtures/go", "fixtures/python")
    tree = normalized_predicate_tree(spec)
    assert tree["operator"] == "and"
    assert tree["predicates"][0]["operator"] == "or"


def test_unknown_soft_evidence_stays_until_explicitly_filtered() -> None:
    unknown = _candidate(
        "unknown", language=None, license=None, archived=None, disabled=None, stars=None
    )
    assert _visible([unknown], FilterSpec()) == ("fixtures/unknown",)
    assert _visible([unknown], FilterSpec(languages=("Python",))) == ()
    assert _visible([unknown], FilterSpec(min_stars=1)) == ()


def test_unknown_and_negative_hard_facts_fail_closed() -> None:
    unknown = _candidate("unknown", license=None, archived=None, disabled=None)
    archived = _candidate("archived", archived=True)
    good = _candidate("good")
    spec = FilterSpec(license_allow=("Apache-2.0",), not_archived=True)

    evaluations, visible, _, _ = evaluate_candidates(
        [unknown, archived, good], spec, observed_at=NOW, raw_count=3
    )

    assert tuple(item.repository for item in visible) == ("fixtures/good",)
    failed = {
        item.candidate.repository: [reason for reason in item.reasons if not reason.passed]
        for item in evaluations
    }
    assert any(reason.unknown for reason in failed["fixtures/unknown"])
    assert any(reason.category == "hard-gate" for reason in failed["fixtures/archived"])


def test_hard_gate_explanations_precede_soft_filters() -> None:
    spec = FilterSpec(
        languages=("Python",),
        topics=("receipts",),
        license_allow=("Apache-2.0",),
        not_archived=True,
        evidence_states=("verified",),
    )
    evaluations, _, _, _ = evaluate_candidates(
        [_candidate("ordered")], spec, observed_at=NOW, raw_count=1
    )

    categories = [reason.category for reason in evaluations[0].reasons]
    first_filter = categories.index("filter")
    assert all(category == "hard-gate" for category in categories[:first_filter])
    assert all(category == "filter" for category in categories[first_filter:])
    assert [item["field"] for item in normalized_predicate_tree(spec)["predicates"]] == [
        "license_allow",
        "not_archived",
        "language",
        "topic",
        "evidence_state",
    ]


def test_deny_policy_and_freshness_gates() -> None:
    candidates = [
        _candidate("good"),
        _candidate("denied", license="GPL-3.0-only"),
        _candidate("stale", pushed_at=NOW - timedelta(days=366)),
        _candidate("no-release", released_at=None),
    ]
    spec = FilterSpec(
        license_deny=("GPL-3.0-only",),
        maintained_within_days=365,
        released_within_days=365,
    )
    assert _visible(candidates, spec) == ("fixtures/good",)


def test_where_sort_limit_and_explanations() -> None:
    candidates = [
        _candidate("b", stars=20),
        _candidate("a", stars=20),
        _candidate("missing", stars=None),
    ]
    spec = FilterSpec(where="language == 'Python'", sort=("-stars",), limit=1)
    evaluations, visible, fingerprint, counts = evaluate_candidates(
        candidates, spec, observed_at=NOW, raw_count=4
    )

    assert tuple(item.repository for item in visible) == ("fixtures/a",)
    assert fingerprint.startswith("rs_")
    assert counts.model_dump() == {
        "raw": 4,
        "deduplicated": 3,
        "included_before_limit": 3,
        "visible": 1,
        "excluded": 2,
    }
    limited = next(item for item in evaluations if item.candidate.repository == "fixtures/b")
    assert limited.reasons[-1].field == "limit"


@pytest.mark.parametrize("expression", ["[", "foo."])
def test_invalid_where_is_typed_failure(expression: str) -> None:
    with pytest.raises(FilterError) as raised:
        evaluate_candidates(
            [_candidate("one")],
            FilterSpec(where=expression),
            observed_at=NOW,
            raw_count=1,
        )
    assert raised.value.code == "invalid_where"


def test_unsupported_sort_is_typed_failure() -> None:
    with pytest.raises(FilterError) as raised:
        _visible([_candidate("one")], FilterSpec(sort=("score",)))
    assert raised.value.code == "unsupported_sort"


@given(st.permutations(["c", "a", "b"]))
def test_input_permutation_does_not_change_stable_result(names: list[str]) -> None:
    candidates = [_candidate(name, stars=1) for name in names]
    assert _visible(candidates, FilterSpec(sort=("stars",))) == (
        "fixtures/a",
        "fixtures/b",
        "fixtures/c",
    )
