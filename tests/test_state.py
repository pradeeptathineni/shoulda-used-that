from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from shoulda_used_that.errors import StateError
from shoulda_used_that.models import Disposition, FilterSpec, SourceKind, SourceRequest
from shoulda_used_that.services import checked, remembered
from shoulda_used_that.state import StateStore
from tests.support import NOW, fixture_request


def _check(store: StateStore, fixture_path: Path):
    return checked(
        store,
        need="test state",
        source_requests=(fixture_request(fixture_path),),
        filter_spec=FilterSpec(limit=2),
        observed_at=NOW,
    )


def test_profiles_are_isolated_and_receipts_are_immutable(
    tmp_path: Path, fixture_path: Path
) -> None:
    first_store = StateStore(tmp_path / "state", profile="one")
    second_store = StateStore(tmp_path / "state", profile="two")
    receipt = _check(first_store, fixture_path)

    assert first_store.latest_check() == receipt
    with pytest.raises(StateError) as absent:
        second_store.latest_check()
    assert absent.value.code == "state_not_found"
    assert first_store.write_check(receipt) is False

    changed = receipt.model_copy(update={"need": "changed under the same id"})
    with pytest.raises(StateError) as conflict:
        first_store.write_check_snapshot(changed)
    assert conflict.value.code == "immutable_receipt_conflict"


def test_state_permissions_and_symlink_boundaries(tmp_path: Path) -> None:
    root = tmp_path / "state"
    store = StateStore(root)
    store.initialize()
    if os.name == "posix":
        assert root.stat().st_mode & 0o777 == 0o700
    assert not (store.profile_root / "saved").exists()
    assert not (store.profile_root / "plans" / "adoptions").exists()
    assert not (store.profile_root / "plans" / "projections").exists()
    assert not (store.profile_root / "plans" / "github-curation").exists()
    assert not (store.profile_root / "applies").exists()
    assert not (store.profile_root / "curations").exists()

    link = tmp_path / "state-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(StateError) as linked_root:
        StateStore(link)
    assert linked_root.value.code == "unsafe_state_root"

    real_profile = tmp_path / "elsewhere"
    real_profile.mkdir()
    unsafe_root = tmp_path / "unsafe"
    unsafe_root.mkdir()
    profiles = unsafe_root / "profiles"
    profiles.mkdir()
    (profiles / "default").symlink_to(real_profile, target_is_directory=True)
    with pytest.raises(StateError) as linked_profile:
        StateStore(unsafe_root).initialize()
    assert linked_profile.value.code == "unsafe_state_path"


@pytest.mark.parametrize("profile", ["", "bad/name", "-leading", "a" * 65])
def test_invalid_profile_is_rejected(tmp_path: Path, profile: str) -> None:
    with pytest.raises(StateError) as raised:
        StateStore(tmp_path, profile=profile)
    assert raised.value.code == "invalid_profile"


def test_invalid_ids_and_corrupt_state_are_typed(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    with pytest.raises(StateError) as bad_id:
        store.read_check("../../etc/passwd")
    assert bad_id.value.code == "invalid_identifier"

    store.initialize()
    latest = store.profile_root / "latest-check.json"
    latest.write_text("[]", encoding="utf-8")
    with pytest.raises(StateError) as wrong_shape:
        store.latest_check()
    assert wrong_shape.value.code == "state_schema_invalid"

    latest.write_text("{", encoding="utf-8")
    with pytest.raises(StateError) as malformed:
        store.latest_check()
    assert malformed.value.code == "state_unreadable"

    latest.unlink()
    latest.mkdir()
    with pytest.raises(StateError) as not_file:
        store.latest_check()
    assert not_file.value.code == "unsafe_state_path"


def test_invalid_current_schema_and_receipt_symlink_are_rejected(
    tmp_path: Path, fixture_path: Path
) -> None:
    store = StateStore(tmp_path / "state")
    receipt = _check(store, fixture_path)
    path = store.profile_root / "checks" / f"{receipt.check_id}.json"
    original = path.read_text(encoding="utf-8")
    path.write_text(json.dumps({"check_id": receipt.check_id}), encoding="utf-8")
    with pytest.raises(StateError) as invalid:
        store.read_check(receipt.check_id)
    assert invalid.value.code == "state_schema_invalid"
    path.write_text(original, encoding="utf-8")

    path.unlink()
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    path.symlink_to(target)
    with pytest.raises(StateError) as linked:
        store.write_check_snapshot(receipt)
    assert linked.value.code == "unsafe_state_path"


def test_decision_without_check_cannot_be_revalidated(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state")
    decision = remembered(
        store,
        repository="fixture-labs/manual",
        need="manual evidence",
        disposition=Disposition.WATCH,
        rationale=("Not bound to a check",),
        evidence_ids=("manual",),
        reconsider_when=("A check exists",),
        created_at=NOW,
    )
    with pytest.raises(StateError) as raised:
        store.resolve_check_for_target(decision.decision_id)
    assert raised.value.code == "decision_has_no_check"


def test_source_request_helper_is_explicit(fixture_path: Path) -> None:
    request = fixture_request(fixture_path)
    assert request == SourceRequest(kind=SourceKind.FIXTURE, locator=str(fixture_path))
