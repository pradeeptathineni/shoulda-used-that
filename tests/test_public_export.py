from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from shoulda_used_that.cli import cli
from shoulda_used_that.curation import compile_profile, load_profile, profile_fingerprint
from shoulda_used_that.errors import StateError
from shoulda_used_that.public_export import (
    MANIFEST_NAME,
    GeneratedFileDigest,
    PublicCatalogExport,
    render_public_catalog,
    validate_public_catalog_directory,
    validate_public_catalog_files,
    write_public_catalog,
)
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.services import curated, exported
from shoulda_used_that.state import StateStore

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PROFILE = ROOT / "curation" / "profiles" / "shoulda-used-that.json"
PUBLIC_ENTRIES = ROOT / "curation" / "entries" / "shoulda-used-that.json"
PERSONAL_ENTRIES = ROOT / "curation" / "entries" / "personal-interests.json"
PUBLIC_CONTEXT = ROOT / "curation" / "assessments" / "shoulda-used-that.json"


def _payload(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_profile_tree(
    root: Path,
    *,
    mutate_profile: Callable[[dict[str, Any]], None] | None = None,
    mutate_entries: Callable[[dict[str, Any]], None] | None = None,
    mutate_context: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    profile = deepcopy(_payload(PUBLIC_PROFILE))
    entries = deepcopy(_payload(PUBLIC_ENTRIES))
    context = deepcopy(_payload(PUBLIC_CONTEXT))
    if mutate_entries is not None:
        mutate_entries(entries)
    if mutate_context is not None:
        mutate_context(context)
    entries_path = root / "curation" / "entries" / "shoulda-used-that.json"
    personal_entries_path = root / "curation" / "entries" / "personal-interests.json"
    profile_path = root / "curation" / "profiles" / "shoulda-used-that.json"
    context_path = root / "curation" / "assessments" / "shoulda-used-that.json"
    entries_path.parent.mkdir(parents=True)
    context_path.parent.mkdir(parents=True)
    profile_path.parent.mkdir(parents=True)
    encoded_entries = (
        json.dumps(entries, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    entries_path.write_bytes(encoded_entries)
    personal_entries = PERSONAL_ENTRIES.read_bytes()
    personal_entries_path.write_bytes(personal_entries)
    encoded_context = (
        json.dumps(context, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    context_path.write_bytes(encoded_context)
    source_payloads = {
        "curation/entries/shoulda-used-that.json": encoded_entries,
        "curation/entries/personal-interests.json": personal_entries,
        "curation/assessments/shoulda-used-that.json": encoded_context,
    }
    for source in profile["source_specifications"]:
        source["content_sha256"] = hashlib.sha256(source_payloads[source["locator"]]).hexdigest()
    if mutate_profile is not None:
        mutate_profile(profile)
    profile["canonical_fingerprint"] = profile_fingerprint(profile)
    profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return profile_path


@pytest.fixture(scope="module")
def valid_public_export_payload() -> dict[str, Any]:
    profile = load_profile(PUBLIC_PROFILE)
    export, _ = render_public_catalog(compile_profile(PUBLIC_PROFILE), profile)
    return export.model_dump(mode="json")


def test_public_catalog_is_complete_deterministic_and_allowlisted() -> None:
    profile = load_profile(PUBLIC_PROFILE)
    snapshot = compile_profile(PUBLIC_PROFILE)

    first_export, first_files = render_public_catalog(snapshot, profile)
    second_export, second_files = render_public_catalog(snapshot, profile)

    assert first_export == second_export
    assert first_files == second_files
    assert first_export.reproducibility_status == "verified-deterministic"
    assert len(first_export.exported_records) == 222
    assert len(first_export.collections) == 12
    assert len(first_export.problems) == 5
    assert len(first_export.assessments) == 17
    assert len(first_export.briefs) == 5
    assert sum(item.publication_state == "assessed" for item in first_export.exported_records) == 17
    assert set(first_export.omitted_private_field_counts.values()) == {0}
    assert {item.repository for item in first_export.license_attribution_inventory} == {
        item.repository for item in first_export.exported_records
    }
    assert all(item.source_locators for item in first_export.license_attribution_inventory)
    assert set(first_files) == {
        MANIFEST_NAME,
        *(item.path for item in first_export.generated_file_manifest),
    }
    assert PublicCatalogExport.model_validate_json(first_files[MANIFEST_NAME]) == first_export
    assert b"Explore prior-art briefs" in first_files["index.md"]
    assert b"briefs/deterministic-python-research-core.md" in first_files["index.md"]
    assert b"screened metadata never becomes contextual fit" in first_files["index.md"]
    assert b"pallets/click" not in first_files["index.md"]
    brief = first_files["briefs/deterministic-python-research-core.md"]
    assert b"pallets/click" in brief
    assert b"Owns mature command parsing" in brief
    assert b"What still appears unresolved" in brief
    assert b"decision_state" not in brief
    evidence = first_files["evidence/pallets--click.md"]
    assert b"Evidence for pallets/click" in evidence
    assert b"Observed repository and provenance details" in evidence
    assert all(not path.startswith(("entries/", "collections/")) for path in first_files)
    screened_slug = "langchain-ai--langchain"
    assert all(screened_slug not in path for path in first_files)
    assert len([path for path in first_files if path.startswith("briefs/")]) == 5
    assert len([path for path in first_files if path.startswith("evidence/")]) == 17
    assert "public catalog ready" in render(first_export, OutputFormat.TABLE)
    assert "Private field classes omitted" in render(first_export, OutputFormat.MARKDOWN)
    combined = b"\n".join(first_files.values())
    assert str(ROOT).encode() not in combined
    assert b"github_pat_" not in combined


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing-private-class", "private-field count classes"),
        ("negative-private-count", "private-field counts cannot be negative"),
        ("record-order", "records must use unique canonical repository order"),
        ("problem-order", "problems must use unique canonical problem order"),
        ("assessment-order", "assessments must use unique canonical relation order"),
        ("assessment-reference", "assessments must reference exported"),
        ("brief-order", "briefs must use unique canonical problem order"),
        ("brief-problem", "briefs require one known problem"),
        ("brief-duplicate", "3-5 unique candidates"),
        ("brief-assessment", "brief candidates require contextual assessments"),
        ("publication-state", "record state must be derived"),
        ("manifest-order", "manifest must be unique, sorted"),
        ("fingerprint", "fingerprint does not match"),
        ("export-id", "export ID does not match"),
    ],
)
def test_public_export_model_rejects_incoherent_derived_state(
    valid_public_export_payload: dict[str, Any], mutation: str, message: str
) -> None:
    payload = deepcopy(valid_public_export_payload)
    if mutation == "missing-private-class":
        payload["omitted_private_field_counts"].pop("credentials")
    elif mutation == "negative-private-count":
        payload["omitted_private_field_counts"]["credentials"] = -1
    elif mutation == "record-order":
        payload["exported_records"].reverse()
    elif mutation == "problem-order":
        payload["problems"].reverse()
    elif mutation == "assessment-order":
        payload["assessments"].reverse()
    elif mutation == "assessment-reference":
        payload["assessments"][-1]["repository"] = "zzzz/missing"
    elif mutation == "brief-order":
        payload["briefs"].reverse()
    elif mutation == "brief-problem":
        payload["briefs"][-1]["problem_id"] = "zzzz-unknown-problem"
    elif mutation == "brief-duplicate":
        candidates = payload["briefs"][0]["candidate_repositories"]
        candidates[-1] = candidates[0]
    elif mutation == "brief-assessment":
        payload["briefs"][0]["candidate_repositories"][0] = payload["exported_records"][0][
            "repository"
        ]
    elif mutation == "publication-state":
        state = payload["exported_records"][0]["publication_state"]
        payload["exported_records"][0]["publication_state"] = (
            "assessed" if state == "screened" else "screened"
        )
    elif mutation == "manifest-order":
        payload["generated_file_manifest"].reverse()
    elif mutation == "fingerprint":
        payload["canonical_fingerprint"] = f"public_{'0' * 64}"
    else:
        payload["export_id"] = f"pcx_{'0' * 24}"

    with pytest.raises(ValidationError, match=message):
        PublicCatalogExport.model_validate(payload)


def test_brief_pages_enforce_reader_information_and_publication_budgets() -> None:
    profile = load_profile(PUBLIC_PROFILE)
    export, files = render_public_catalog(compile_profile(PUBLIC_PROFILE), profile)
    assessed = {item.repository for item in export.assessments}

    for brief in export.briefs:
        payload = files[f"briefs/{brief.problem_id}.md"]
        assert 3 <= len(brief.candidate_repositories) <= 5
        assert payload.count(b'<article class="catalog-card assessment-card">') == len(
            brief.candidate_repositories
        )
        assert payload.count(b">Evidence</a>") == len(brief.candidate_repositories)
        assert b"What appears covered" in payload
        assert b"What still appears unresolved" in payload
        default_view = payload.split(b"<details>", 1)[0]
        for hidden in (b"Latest commit", b"fingerprint", b"projection", b"receipt ID"):
            assert hidden not in default_view

    evidence_pages = {
        path.removeprefix("evidence/").removesuffix(".md").replace("--", "/")
        for path in files
        if path.startswith("evidence/")
    }
    assert evidence_pages == assessed
    screened_only = {
        item.repository for item in export.exported_records if item.publication_state == "screened"
    }
    assert evidence_pages.isdisjoint(screened_only)


def test_entry_change_has_a_bounded_generated_diff(tmp_path: Path) -> None:
    baseline_profile = load_profile(PUBLIC_PROFILE)
    baseline_snapshot = compile_profile(PUBLIC_PROFILE)
    _, baseline = render_public_catalog(baseline_snapshot, baseline_profile)

    def change_click(entries: dict[str, Any]) -> None:
        click_entry = next(
            item for item in entries["repository_evidence"] if item["repository"] == "pallets/click"
        )
        click_entry["description"] = "A deliberately changed Click description."

    changed_path = _write_profile_tree(tmp_path, mutate_entries=change_click)
    changed_profile = load_profile(changed_path)
    changed_snapshot = compile_profile(changed_path)
    _, changed = render_public_catalog(changed_snapshot, changed_profile)

    changed_paths = {path for path in baseline if baseline[path] != changed[path]}
    assert changed_paths == {
        "catalog.json",
        "briefs/deterministic-python-research-core.md",
        "evidence/pallets--click.md",
        MANIFEST_NAME,
        "sources.md",
    }


def test_non_public_collections_are_omitted_instead_of_leaked(tmp_path: Path) -> None:
    def hide_collection(profile: dict[str, Any]) -> None:
        collection = next(
            item for item in profile["collections"] if item["slug"] == "oss-curation-foundations"
        )
        collection["public_site_visibility"] = False

    profile_path = _write_profile_tree(tmp_path, mutate_profile=hide_collection)
    export, _ = render_public_catalog(compile_profile(profile_path), load_profile(profile_path))

    assert "oss-curation-foundations" not in {item.slug for item in export.collections}
    assert all(
        "oss-curation-foundations" not in record.collections for record in export.exported_records
    )
    assert export.omitted_private_field_counts["non_public_collections"] > 0


def test_markdown_escapes_untrusted_entry_text(tmp_path: Path) -> None:
    def inject_markup(entries: dict[str, Any]) -> None:
        click = next(
            item for item in entries["repository_evidence"] if item["repository"] == "pallets/click"
        )
        click["description"] = '<script>alert("catalog")</script>'

    def inject_context(context: dict[str, Any]) -> None:
        click = next(
            item for item in context["assessments"] if item["repository"] == "pallets/click"
        )
        click["covers"] = ["[steal](javascript:alert(1))\n# injected heading\n1. fake list"]

    profile_path = _write_profile_tree(
        tmp_path,
        mutate_entries=inject_markup,
        mutate_context=inject_context,
    )
    profile = load_profile(profile_path)
    snapshot = compile_profile(profile_path)
    _, files = render_public_catalog(snapshot, profile)
    entry_path = "evidence/pallets--click.md"

    assert b"<script>" not in files[entry_path]
    assert b"&lt;script\\&gt;alert\\(&quot;catalog&quot;\\)&lt;/script\\&gt;" in files[entry_path]
    assert b"](javascript:" not in files[entry_path]
    assert b"\n# injected heading" not in files[entry_path]
    assert b"\\[steal\\]\\(javascript:alert\\(1\\)\\)" in files[entry_path]
    assert b"1\\. fake list" in files[entry_path]


def test_private_mismatched_invalid_and_leaking_inputs_fail_closed(tmp_path: Path) -> None:
    snapshot = compile_profile(PUBLIC_PROFILE)
    profile = load_profile(PUBLIC_PROFILE)

    private_path = _write_profile_tree(
        tmp_path / "private",
        mutate_profile=lambda value: value.update({"visibility": "private"}),
    )
    with pytest.raises(StateError, match="explicitly public") as private:
        render_public_catalog(compile_profile(private_path), load_profile(private_path))
    assert private.value.code == "public_export_private_profile"

    changed_path = _write_profile_tree(
        tmp_path / "changed",
        mutate_profile=lambda value: value.update({"title": "Another valid public profile"}),
    )
    with pytest.raises(StateError) as mismatch:
        render_public_catalog(snapshot, load_profile(changed_path))
    assert mismatch.value.code == "public_export_profile_mismatch"

    invalid_snapshot = snapshot.model_copy(
        update={"repository_evidence": tuple(reversed(snapshot.repository_evidence))}
    )
    with pytest.raises(StateError) as inconsistent:
        render_public_catalog(invalid_snapshot, profile)
    assert inconsistent.value.code == "curation_snapshot_inconsistent"

    leaking_path = _write_profile_tree(
        tmp_path / "leaking",
        mutate_profile=lambda value: value.update(
            {"description": "Leaked from /Users/example/private/source"}
        ),
    )
    with pytest.raises(StateError) as leaking:
        render_public_catalog(compile_profile(leaking_path), load_profile(leaking_path))
    assert leaking.value.code == "public_export_local_path_leak"

    secret_path = _write_profile_tree(
        tmp_path / "secret",
        mutate_profile=lambda value: value.update(
            {"description": "Credential-like input sk-0123456789abcdefghijklmnop"}
        ),
    )
    with pytest.raises(StateError) as secret:
        render_public_catalog(compile_profile(secret_path), load_profile(secret_path))
    assert secret.value.code == "public_export_secret_leak"


@pytest.mark.parametrize(
    "location",
    ["source-provenance", "screening", "assessment", "brief"],
)
def test_all_public_evidence_layers_reject_local_paths(tmp_path: Path, location: str) -> None:
    def mutate_entries(entries: dict[str, Any]) -> None:
        if location == "source-provenance":
            entries["repository_evidence"][0]["source_provenance"][0]["locator"] = (
                "/private/evidence.json"
            )
        elif location == "screening":
            entries["screenings"][0]["evidence_receipt_ids"] = ["/private/screening.json"]

    def mutate_context(context: dict[str, Any]) -> None:
        if location == "assessment":
            context["assessments"][0]["evidence_refs"] = ["/private/assessment.json"]
        elif location == "brief":
            context["briefs"][0]["evidence_refs"] = ["/private/brief.json"]

    profile_path = _write_profile_tree(
        tmp_path,
        mutate_entries=mutate_entries,
        mutate_context=mutate_context,
    )
    with pytest.raises(StateError) as raised:
        render_public_catalog(compile_profile(profile_path), load_profile(profile_path))
    assert raised.value.code == "public_export_local_path_leak"


def test_transactional_writer_repairs_managed_output_and_rejects_unsafe_paths(
    tmp_path: Path,
) -> None:
    profile = load_profile(PUBLIC_PROFILE)
    snapshot = compile_profile(PUBLIC_PROFILE)
    destination = tmp_path / "catalog"

    export, changed = write_public_catalog(snapshot, profile, destination)
    assert changed is True
    if os.name == "posix":
        assert destination.stat().st_mode & 0o777 == 0o755
    assert write_public_catalog(snapshot, profile, destination) == (export, False)
    validate_public_catalog_directory(destination, export)

    (destination / "index.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(StateError) as tampered:
        validate_public_catalog_directory(destination, export)
    assert tampered.value.code == "public_export_digest_mismatch"
    assert write_public_catalog(snapshot, profile, destination) == (export, True)
    validate_public_catalog_directory(destination, export)

    unmanaged = tmp_path / "unmanaged"
    unmanaged.mkdir()
    (unmanaged / "owned-by-someone-else.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(StateError) as refused:
        write_public_catalog(snapshot, profile, unmanaged)
    assert refused.value.code == "public_export_destination_unmanaged"

    file_target = tmp_path / "a-file"
    file_target.write_text("keep", encoding="utf-8")
    with pytest.raises(StateError) as unsafe_file:
        write_public_catalog(snapshot, profile, file_target)
    assert unsafe_file.value.code == "public_export_destination_unsafe"


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_public_export_rejects_symlinks(tmp_path: Path) -> None:
    profile = load_profile(PUBLIC_PROFILE)
    snapshot = compile_profile(PUBLIC_PROFILE)
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "linked"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(StateError) as target_link:
        write_public_catalog(snapshot, profile, linked)
    assert target_link.value.code == "public_export_destination_unsafe"

    destination = tmp_path / "catalog"
    export, _ = write_public_catalog(snapshot, profile, destination)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    injected = destination / "injected"
    try:
        injected.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(StateError) as tree_link:
        validate_public_catalog_directory(destination, export)
    assert tree_link.value.code == "public_export_symlink"


def test_manifest_and_portable_path_guards_are_typed() -> None:
    profile = load_profile(PUBLIC_PROFILE)
    snapshot = compile_profile(PUBLIC_PROFILE)
    export, files = render_public_catalog(snapshot, profile)

    missing = dict(files)
    missing.pop("index.md")
    with pytest.raises(StateError) as mismatch:
        validate_public_catalog_files(missing, export)
    assert mismatch.value.code == "public_export_manifest_mismatch"

    modified = dict(files)
    modified["index.md"] += b"changed"
    with pytest.raises(StateError) as digest_mismatch:
        validate_public_catalog_files(modified, export)
    assert digest_mismatch.value.code == "public_export_digest_mismatch"

    for path in ("/absolute.md", "../escape.md", "nested\\windows.md", ""):
        with pytest.raises(ValidationError):
            GeneratedFileDigest(path=path, sha256="0" * 64, bytes=0)


def test_service_state_and_cli_preserve_the_explicit_public_boundary(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "service-state")
    snapshot = curated(store, profile_path=PUBLIC_PROFILE)
    assert store.read_curation_profile(snapshot.profile_fingerprint) == load_profile(PUBLIC_PROFILE)

    with pytest.raises(StateError) as flag:
        exported(
            store,
            curation_snapshot_id=snapshot.curation_snapshot_id,
            public=False,
            output=tmp_path / "refused",
        )
    assert flag.value.code == "public_export_flag_required"
    receipt = exported(
        store,
        curation_snapshot_id=snapshot.curation_snapshot_id,
        public=True,
        output=tmp_path / "service-catalog",
    )
    assert receipt.source_curation_snapshot_id == snapshot.curation_snapshot_id

    profile_state = (
        store.profile_root / "curation-profiles" / f"{snapshot.profile_fingerprint}.json"
    )
    corrupted = json.loads(profile_state.read_text(encoding="utf-8"))
    corrupted["description"] = "Changed without a new identity"
    profile_state.write_text(json.dumps(corrupted), encoding="utf-8")
    with pytest.raises(StateError) as corrupt_state:
        store.read_curation_profile(snapshot.profile_fingerprint)
    assert corrupt_state.value.code == "curation_profile_fingerprint_mismatch"

    runner = CliRunner()
    cli_state = tmp_path / "cli-state"
    curate_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(cli_state),
            "--format",
            "json",
            "curated",
            str(PUBLIC_PROFILE),
        ],
    )
    assert curate_result.exit_code == 0, curate_result.output
    curation_id = json.loads(curate_result.stdout)["curation_snapshot_id"]
    refused_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(cli_state),
            "--format",
            "json",
            "exported",
            curation_id,
            "--output",
            str(tmp_path / "cli-refused"),
        ],
    )
    assert refused_result.exit_code == 2
    assert json.loads(refused_result.stderr)["error"]["code"] == "public_export_flag_required"
    export_result = runner.invoke(
        cli,
        [
            "--state-dir",
            str(cli_state),
            "--format",
            "json",
            "exported",
            curation_id,
            "--public",
            "--output",
            str(tmp_path / "cli-catalog"),
        ],
    )
    assert export_result.exit_code == 0, export_result.output
    assert json.loads(export_result.stdout)["source_curation_snapshot_id"] == curation_id
    assert (tmp_path / "cli-catalog" / MANIFEST_NAME).is_file()
