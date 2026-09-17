from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from shoulda_used_that.cli import cli
from shoulda_used_that.curation import (
    MAX_SOURCE_BYTES,
    CurationProfile,
    compile_profile,
    load_profile,
    profile_fingerprint,
)
from shoulda_used_that.errors import StateError
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.state import StateStore

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PROFILE = ROOT / "curation" / "profiles" / "shoulda-used-that.json"
PUBLIC_ENTRIES = ROOT / "curation" / "entries" / "shoulda-used-that.json"
PERSONAL_ENTRIES = ROOT / "curation" / "entries" / "personal-interests.json"


def _payload(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_tree(
    root: Path,
    *,
    profile: dict[str, Any] | None = None,
    entries: dict[str, Any] | None = None,
) -> Path:
    profile_payload = deepcopy(profile or _payload(PUBLIC_PROFILE))
    entries_payload = deepcopy(entries or _payload(PUBLIC_ENTRIES))
    entries_path = root / "curation" / "entries" / "shoulda-used-that.json"
    personal_entries_path = root / "curation" / "entries" / "personal-interests.json"
    profile_path = root / "curation" / "profiles" / "shoulda-used-that.json"
    entries_path.parent.mkdir(parents=True)
    profile_path.parent.mkdir(parents=True)
    encoded_entries = (
        json.dumps(entries_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    entries_path.write_bytes(encoded_entries)
    personal_entries = PERSONAL_ENTRIES.read_bytes()
    personal_entries_path.write_bytes(personal_entries)
    source_payloads = {
        "curation/entries/shoulda-used-that.json": encoded_entries,
        "curation/entries/personal-interests.json": personal_entries,
    }
    for source in profile_payload["source_specifications"]:
        source["content_sha256"] = hashlib.sha256(source_payloads[source["locator"]]).hexdigest()
    profile_payload["canonical_fingerprint"] = profile_fingerprint(profile_payload)
    profile_path.write_text(
        json.dumps(profile_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return profile_path


def test_public_profile_compiles_deterministically_and_preserves_semantics() -> None:
    profile = load_profile(PUBLIC_PROFILE)
    first = compile_profile(PUBLIC_PROFILE)
    second = compile_profile(PUBLIC_PROFILE, previous=first)

    assert second == first
    assert first.profile_fingerprint == profile.canonical_fingerprint
    assert first.counts.model_dump() == {
        "sources": 2,
        "entries": 221,
        "excluded": 1,
        "inbox": 0,
        "stale": 0,
        "partial": 0,
        "blocked": 0,
    }
    assert first.semantic_diff.material is True
    assert first.semantic_diff.added_exclusions == ("morehao/starman",)
    assert tuple(first.collection_membership_map) == tuple(sorted(first.collection_membership_map))
    assert first.entries == tuple(sorted(first.entries, key=lambda item: item.repository))
    assert profile.projection_policy.selected_collection_slugs == (
        "generative-ai-agents",
        "rag-search-knowledge",
        "computer-vision-multimodal",
        "cloud-infrastructure-iac",
        "platform-engineering-delivery",
        "software-supply-chain",
        "python-engineering",
        "homelab-self-hosting",
        "creative-coding-visualization",
        "nature-physics-simulation",
        "web-engineering-interfaces",
        "oss-curation-foundations",
    )
    first_five = tuple(collection.slug for collection in profile.collections[:5])
    assert first_five == (
        "generative-ai-agents",
        "rag-search-knowledge",
        "computer-vision-multimodal",
        "cloud-infrastructure-iac",
        "platform-engineering-delivery",
    )
    searchable = {
        value.casefold()
        for collection in profile.collections
        for value in (collection.title, *collection.aliases)
    }
    assert {
        "devops",
        "genai",
        "home lab",
        "vlm",
        "nature simulation",
        "terraform",
        "vector search",
        "web development",
    } <= searchable


def test_curation_state_is_immutable_idempotent_and_profile_scoped(tmp_path: Path) -> None:
    snapshot = compile_profile(PUBLIC_PROFILE)
    store = StateStore(tmp_path / "state")

    assert store.latest_curation(snapshot.profile_id) is None
    assert store.write_curation(snapshot) is True
    assert store.write_curation(snapshot) is False
    assert store.latest_curation() == snapshot
    assert store.latest_curation(snapshot.profile_id) == snapshot
    assert store.latest_curation("another-profile") is None


def test_source_drift_and_profile_fingerprint_drift_fail_closed(tmp_path: Path) -> None:
    profile_path = _write_tree(tmp_path)
    entries_path = tmp_path / "curation" / "entries" / "shoulda-used-that.json"
    entries_path.write_bytes(entries_path.read_bytes() + b"\n")
    with pytest.raises(StateError) as source_drift:
        compile_profile(profile_path)
    assert source_drift.value.code == "curation_source_drift"

    profile_path = _write_tree(tmp_path / "second")
    profile_payload = _payload(profile_path)
    profile_payload["title"] = "Changed without resealing"
    profile_path.write_text(json.dumps(profile_payload), encoding="utf-8")
    with pytest.raises(StateError) as profile_drift:
        load_profile(profile_path)
    assert profile_drift.value.code == "curation_profile_fingerprint_mismatch"


def test_changed_entries_exclusions_and_profile_are_a_material_diff(tmp_path: Path) -> None:
    previous = compile_profile(PUBLIC_PROFILE)
    entries = _payload(PUBLIC_ENTRIES)
    entries["entries"][0]["rationale"] = "A newly reviewed rationale."
    entries["excluded_candidates"][0]["reason"] = "A newly reviewed exclusion."
    profile_path = _write_tree(tmp_path, entries=entries)

    current = compile_profile(profile_path, previous=previous)

    assert current.semantic_diff.previous_snapshot_id == previous.curation_snapshot_id
    assert current.semantic_diff.profile_changed is True
    assert current.semantic_diff.changed_repositories == ("pallets/click",)
    assert current.semantic_diff.changed_exclusions == ("morehao/starman",)
    assert current.semantic_diff.material is True


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_source_path_boundaries_and_size_are_typed(tmp_path: Path) -> None:
    profile_path = _write_tree(tmp_path / "symlink")
    entries_path = tmp_path / "symlink" / "curation" / "entries" / "shoulda-used-that.json"
    real_entries = entries_path.with_name("real.json")
    entries_path.rename(real_entries)
    try:
        entries_path.symlink_to(real_entries)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(StateError) as linked:
        compile_profile(profile_path)
    assert linked.value.code == "curation_source_unsafe"

    oversized_root = tmp_path / "oversized"
    oversized_profile = _write_tree(oversized_root)
    oversized_entries = oversized_root / "curation" / "entries" / "shoulda-used-that.json"
    oversized_entries.write_bytes(b"x" * (MAX_SOURCE_BYTES + 1))
    with pytest.raises(StateError) as oversized:
        compile_profile(oversized_profile)
    assert oversized.value.code == "curation_source_too_large"

    unsafe_root = tmp_path / "unsafe"
    unsafe_path = _write_tree(unsafe_root)
    unsafe_profile = _payload(unsafe_path)
    unsafe_profile["source_specifications"][0]["locator"] = "../outside.json"
    for collection in unsafe_profile["collections"]:
        collection["exact_bound_sources"] = ["../outside.json"]
    unsafe_profile["canonical_fingerprint"] = profile_fingerprint(unsafe_profile)
    unsafe_path.write_text(json.dumps(unsafe_profile), encoding="utf-8")
    (tmp_path / "outside.json").write_bytes(
        (unsafe_root / "curation" / "entries" / "shoulda-used-that.json").read_bytes()
    )
    with pytest.raises(StateError) as escaped:
        compile_profile(unsafe_path)
    assert escaped.value.code == "curation_source_unsafe"

    profile_link = tmp_path / "profile-link.json"
    try:
        profile_link.symlink_to(PUBLIC_PROFILE)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(StateError) as linked_profile:
        compile_profile(profile_link)
    assert linked_profile.value.code == "curation_source_unsafe"


def test_entry_review_time_cannot_be_after_profile_review_time(tmp_path: Path) -> None:
    entries = _payload(PUBLIC_ENTRIES)
    entries["entries"][0]["last_checked_at"] = "2026-09-18T00:00:00Z"
    profile_path = _write_tree(tmp_path, entries=entries)
    with pytest.raises(StateError) as raised:
        compile_profile(profile_path)
    assert raised.value.code == "curation_entry_from_future"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("unknown-collection", "curation_collection_unknown"),
        ("conflicting-disposition", "curation_disposition_conflict"),
    ],
)
def test_invalid_entry_relationships_are_typed(tmp_path: Path, mutation: str, code: str) -> None:
    entries = _payload(PUBLIC_ENTRIES)
    if mutation == "unknown-collection":
        entries["entries"][0]["collection_memberships"].append("not-a-collection")
    else:
        conflict = deepcopy(entries["entries"][0])
        conflict["primary_disposition"] = "reject"
        conflict["rationale"] = "Conflicting fixture claim."
        entries["entries"].append(conflict)
    profile_path = _write_tree(tmp_path, entries=entries)

    with pytest.raises(StateError) as raised:
        compile_profile(profile_path)
    assert raised.value.code == code


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["collections"][1]["aliases"].append("DevOps"),
        lambda payload: payload["projection_policy"].update({"account": None}),
        lambda payload: payload["collections"][0].update({"max_repositories": 301}),
        lambda payload: payload["collections"][0]["exact_bound_sources"].append(
            "curation/entries/missing.json"
        ),
    ],
)
def test_profile_rejects_ambiguous_or_incoherent_intent(mutate: Any) -> None:
    payload = _payload(PUBLIC_PROFILE)
    mutate(payload)
    with pytest.raises(ValidationError):
        CurationProfile.model_validate(payload)


def test_unknown_profile_and_input_schema_versions_fail_closed(tmp_path: Path) -> None:
    profile = _payload(PUBLIC_PROFILE)
    profile["schema_version"] = "99.0"
    profile["canonical_fingerprint"] = profile_fingerprint(profile)
    profile_path = _write_tree(tmp_path / "profile", profile=profile)
    with pytest.raises(StateError) as invalid_profile:
        load_profile(profile_path)
    assert invalid_profile.value.code == "curation_profile_invalid"

    entries = _payload(PUBLIC_ENTRIES)
    entries["schema_version"] = "99.0"
    source_path = _write_tree(tmp_path / "entries", entries=entries)
    with pytest.raises(StateError) as invalid_source:
        compile_profile(source_path)
    assert invalid_source.value.code == "curation_source_invalid"


def test_cli_emits_machine_record_and_readable_summary(tmp_path: Path) -> None:
    runner = CliRunner()
    base = ["--state-dir", str(tmp_path / "state")]
    machine = runner.invoke(
        cli,
        [*base, "--format", "json", "curated", str(PUBLIC_PROFILE)],
    )
    assert machine.exit_code == 0, machine.output
    assert json.loads(machine.stdout)["counts"]["entries"] == 221

    human = runner.invoke(
        cli,
        [*base, "--format", "table", "curated", str(PUBLIC_PROFILE)],
    )
    assert human.exit_code == 0, human.output
    assert "pradeeptathineni/shoulda-used-that" in human.stdout
    assert "entries=221 excluded=1 inbox=0 stale=0" in human.stdout
    assert "canonical_fingerprint" not in human.stdout

    markdown = render(compile_profile(PUBLIC_PROFILE), OutputFormat.MARKDOWN)
    assert "| Repository | Disposition | Collections | Freshness |" in markdown
    assert "platform-engineering-delivery" in markdown
