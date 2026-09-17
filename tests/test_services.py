from __future__ import annotations

import json
from pathlib import Path

import pytest

from shoulda_used_that.errors import SourceError, StateError
from shoulda_used_that.models import Disposition, FilterSpec, RecheckOutcome
from shoulda_used_that.services import (
    checked,
    rechecked,
    remembered,
    saved,
    used,
    validate_unapplied_plan,
)
from shoulda_used_that.state import StateStore
from tests.support import LATER, NOW, fixture_request


def _checked(store: StateStore, path: Path, *, limit: int = 50):
    return checked(
        store,
        need="find reusable receipt machinery",
        source_requests=(fixture_request(path),),
        filter_spec=FilterSpec(
            languages=("Python", "TypeScript"),
            license_deny=("GPL-3.0-only",),
            not_archived=True,
            sort=("-stars",),
            limit=limit,
        ),
        observed_at=NOW,
    )


def test_checked_records_exact_visible_result_and_explanations(
    tmp_path: Path, fixture_path: Path
) -> None:
    store = StateStore(tmp_path / "state")
    receipt = _checked(store, fixture_path, limit=2)

    assert receipt.result_repositories == (
        "fixture-labs/canonical-kit",
        "fixture-labs/js-helper",
    )
    assert receipt.ordering == ("-stars", "repo")
    assert receipt.counts.raw == 5
    assert receipt.counts.visible == 2
    assert store.latest_check().result_set_fingerprint == receipt.result_set_fingerprint
    assert all(evaluation.reasons for evaluation in receipt.evaluations)
    with pytest.raises(SourceError) as source_required:
        checked(
            store,
            need="implicit discovery is forbidden",
            source_requests=(),
            filter_spec=FilterSpec(),
        )
    assert source_required.value.code == "source_required"


def test_saved_all_is_exact_local_and_idempotent(tmp_path: Path, fixture_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    check = _checked(store, fixture_path, limit=2)

    first, projection = saved(
        store,
        repositories=(),
        save_all=True,
        from_check_id=check.check_id,
        disposition=Disposition.TRIAL,
        list_name="Reusable",
        created_at=NOW,
    )
    second, _ = saved(
        store,
        repositories=(),
        save_all=True,
        from_check_id=check.check_id,
        disposition=Disposition.TRIAL,
        list_name=None,
        created_at=LATER,
    )

    assert first.created == check.result_repositories
    assert first.already_saved == ()
    assert second.created == ()
    assert second.already_saved == check.result_repositories
    assert projection is not None
    assert [item.classification for item in projection.operations] == [
        "already_starred",
        "requires_star",
    ]
    assert [item.status for item in projection.operations] == ["planned", "blocked"]
    assert validate_unapplied_plan(store, projection.plan_id) == projection
    assert store.saved_item("fixture-labs/canonical-kit") is not None


def test_save_scope_errors_fail_before_side_effects(tmp_path: Path, fixture_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    with pytest.raises(StateError) as missing:
        saved(
            store,
            repositories=(),
            save_all=False,
            from_check_id=None,
            disposition=None,
            list_name=None,
        )
    assert missing.value.code == "save_scope_missing"
    with pytest.raises(StateError) as ambiguous:
        saved(
            store,
            repositories=("fixture-labs/a",),
            save_all=True,
            from_check_id=None,
            disposition=None,
            list_name=None,
        )
    assert ambiguous.value.code == "save_scope_ambiguous"

    check = _checked(store, fixture_path, limit=1)
    with pytest.raises(StateError) as outside:
        saved(
            store,
            repositories=("fixture-labs/query-needle",),
            save_all=False,
            from_check_id=check.check_id,
            disposition=None,
            list_name=None,
        )
    assert outside.value.code == "save_outside_check_scope"
    assert store.saved_item("fixture-labs/query-needle") is None

    standalone = StateStore(tmp_path / "standalone")
    with pytest.raises(StateError) as plan_without_check:
        saved(
            standalone,
            repositories=("fixture-labs/a",),
            save_all=False,
            from_check_id=None,
            disposition=None,
            list_name="Nope",
        )
    assert plan_without_check.value.code == "projection_requires_check"
    assert standalone.saved_item("fixture-labs/a") is None

    validation_store = StateStore(tmp_path / "plan-validation")
    validation_check = _checked(validation_store, fixture_path, limit=1)
    selected = validation_check.result_repositories[0]
    with pytest.raises(ValueError, match="at most 100"):
        saved(
            validation_store,
            repositories=(selected,),
            save_all=False,
            from_check_id=validation_check.check_id,
            disposition=None,
            list_name="x" * 101,
        )
    assert validation_store.saved_item(selected) is None


def test_remembered_binds_evidence_and_supersedes_explicitly(
    tmp_path: Path, fixture_path: Path
) -> None:
    store = StateStore(tmp_path / "state")
    check = _checked(store, fixture_path)
    first = remembered(
        store,
        repository="Fixture-Labs/Canonical-Kit",
        need="canonical bytes",
        disposition=Disposition.ADOPT,
        rationale=("Published behavior matches",),
        evidence_ids=("manual-vector",),
        alternatives=("custom serializer",),
        unknowns=("future maintenance",),
        reconsider_when=("vectors fail",),
        from_check_id=check.check_id,
        created_at=NOW,
    )
    second = remembered(
        store,
        repository="fixture-labs/canonical-kit",
        need="canonical bytes",
        disposition=Disposition.WATCH,
        rationale=("Maintenance changed",),
        evidence_ids=("new-evidence",),
        reconsider_when=("maintenance resumes",),
        supersedes=first.decision_id,
        created_at=LATER,
    )

    assert first.source_check_id == check.check_id
    assert "manual-vector" in first.evidence_ids
    assert check.source_observations[0].payload_fingerprint in first.evidence_ids
    assert second.supersedes == first.decision_id
    assert store.read_decision(second.decision_id) == second

    with pytest.raises(StateError) as outside:
        remembered(
            store,
            repository="fixture-labs/not-observed",
            need="unrelated",
            disposition=Disposition.REJECT,
            rationale=("No evidence",),
            evidence_ids=(),
            reconsider_when=("evidence appears",),
            from_check_id=check.check_id,
        )
    assert outside.value.code == "decision_outside_check_scope"

    with pytest.raises(StateError) as mismatch:
        remembered(
            store,
            repository="fixture-labs/other",
            need="other",
            disposition=Disposition.REJECT,
            rationale=("Different subject",),
            evidence_ids=(),
            reconsider_when=("never",),
            supersedes=first.decision_id,
        )
    assert mismatch.value.code == "supersession_subject_mismatch"


@pytest.mark.parametrize(
    ("rationale", "triggers", "code"),
    [
        ((), ("later",), "rationale_required"),
        (("because",), (), "reconsideration_required"),
    ],
)
def test_remembered_requires_reason_and_trigger(
    tmp_path: Path, rationale: tuple[str, ...], triggers: tuple[str, ...], code: str
) -> None:
    with pytest.raises(StateError) as raised:
        remembered(
            StateStore(tmp_path / "state"),
            repository="fixture-labs/a",
            need="test",
            disposition=Disposition.WATCH,
            rationale=rationale,
            evidence_ids=(),
            reconsider_when=triggers,
        )
    assert raised.value.code == code


def test_recheck_noop_replay_then_preserves_last_known_good_on_failure(
    tmp_path: Path, fixture_path: Path
) -> None:
    copied = tmp_path / "fixture.json"
    copied.write_bytes(fixture_path.read_bytes())
    store = StateStore(tmp_path / "state")
    check = _checked(store, copied)

    first = rechecked(store, target_id=check.check_id, checked_at=LATER)
    second = rechecked(
        store,
        target_id=check.check_id,
        checked_at=LATER.replace(minute=1),
    )
    copied.unlink()
    failed = rechecked(
        store,
        target_id=check.check_id,
        checked_at=LATER.replace(minute=2),
    )

    assert first.outcome is RecheckOutcome.SEMANTIC_NOOP
    assert second.outcome is RecheckOutcome.SEMANTIC_NOOP
    assert failed.outcome is RecheckOutcome.MATERIAL_REVIEW_REQUIRED
    assert failed.last_known_good_preserved is True
    assert failed.current_fingerprint == first.current_fingerprint
    assert failed.source_errors[0].startswith("fixture: fixture_unreadable")


def test_recheck_classifies_refresh_and_material_changes(
    tmp_path: Path, fixture_path: Path
) -> None:
    copied = tmp_path / "fixture.json"
    copied.write_bytes(fixture_path.read_bytes())
    store = StateStore(tmp_path / "state")
    check = _checked(store, copied)

    payload = json.loads(copied.read_text(encoding="utf-8"))
    payload["candidates"][0]["stars"] = 121
    copied.write_text(json.dumps(payload), encoding="utf-8")
    refresh = rechecked(store, target_id=check.check_id, checked_at=LATER)
    assert refresh.outcome is RecheckOutcome.REFRESH_ONLY
    assert [(item.field, item.materiality.value) for item in refresh.diffs] == [
        ("stars", "refresh-only")
    ]

    payload["candidates"][0]["license"] = "MIT"
    copied.write_text(json.dumps(payload), encoding="utf-8")
    material = rechecked(
        store,
        target_id=check.check_id,
        checked_at=LATER.replace(minute=1),
    )
    assert material.outcome is RecheckOutcome.MATERIAL_REVIEW_REQUIRED
    assert material.last_known_good_preserved is True
    assert any(item.field == "license" for item in material.diffs)

    repeated = rechecked(
        store,
        target_id=check.check_id,
        checked_at=LATER.replace(minute=2),
    )
    assert repeated.outcome is RecheckOutcome.MATERIAL_REVIEW_REQUIRED
    assert repeated.prior_check_id == material.prior_check_id
    assert repeated.last_known_good_fingerprint == material.last_known_good_fingerprint
    assert any(item.field == "license" for item in repeated.diffs)


def test_used_is_plan_only_and_replayable(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "sentinel.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    store = StateStore(tmp_path / "state")
    plan = used(
        store,
        repository="Fixture-Labs/Canonical-Kit",
        need="canonical bytes",
        target=str(target),
        proposed_files=("adapter.py",),
        native_tools=("pytest",),
        tests=("published vectors",),
        expected_postconditions=("vectors pass",),
        rollback=("remove adapter",),
        remaining_evidence=("hosted CI",),
        created_at=NOW,
    )

    assert plan.mutation_state == "planning-only"
    assert validate_unapplied_plan(store, plan.plan_id) == plan
    assert sentinel.read_text(encoding="utf-8") == "unchanged"
    assert tuple(target.iterdir()) == (sentinel,)
    with pytest.raises(StateError, match="use_ or prj_"):
        validate_unapplied_plan(store, "bad_1234567890123456")


@pytest.mark.parametrize(
    ("postconditions", "rollback", "code"),
    [
        ((), ("undo",), "postcondition_required"),
        (("done",), (), "rollback_required"),
    ],
)
def test_used_requires_typed_safety_boundaries(
    tmp_path: Path,
    postconditions: tuple[str, ...],
    rollback: tuple[str, ...],
    code: str,
) -> None:
    with pytest.raises(StateError) as raised:
        used(
            StateStore(tmp_path / "state"),
            repository="fixture-labs/a",
            need="test",
            target="target",
            proposed_files=(),
            native_tools=(),
            tests=(),
            expected_postconditions=postconditions,
            rollback=rollback,
            remaining_evidence=(),
        )
    assert raised.value.code == code
