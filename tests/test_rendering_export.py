from __future__ import annotations

import json
from pathlib import Path

import yaml

from shoulda_used_that.export import public_summary
from shoulda_used_that.models import Disposition, FilterSpec
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.services import checked, rechecked, remembered, saved, used
from shoulda_used_that.state import StateStore
from tests.support import LATER, NOW, fixture_request


def test_all_renderings_are_derived_from_validated_model(
    tmp_path: Path, fixture_path: Path
) -> None:
    receipt = checked(
        StateStore(tmp_path / "state"),
        need="render evidence",
        source_requests=(fixture_request(fixture_path),),
        filter_spec=FilterSpec(limit=1),
        observed_at=NOW,
    )

    json_payload = json.loads(render(receipt, OutputFormat.JSON))
    yaml_payload = yaml.safe_load(render(receipt, OutputFormat.YAML))
    markdown = render(receipt, OutputFormat.MARKDOWN)
    table = render(receipt, OutputFormat.TABLE, explain=True)

    assert json_payload == yaml_payload == receipt.model_dump(mode="json")
    assert receipt.check_id in markdown
    assert receipt.result_repositories[0] in table
    assert "all predicates passed" in table
    assert "\x1b[" not in table


def test_public_exports_are_allowlists_without_private_values(
    tmp_path: Path, fixture_path: Path
) -> None:
    store = StateStore(tmp_path / "private-state", profile="private-profile")
    check = checked(
        store,
        need="private need must not be exported",
        source_requests=(fixture_request(fixture_path),),
        filter_spec=FilterSpec(limit=1),
        observed_at=NOW,
    )
    save, projection = saved(
        store,
        repositories=(),
        save_all=True,
        from_check_id=check.check_id,
        disposition=Disposition.TRIAL,
        list_name="private list",
        created_at=NOW,
    )
    decision = remembered(
        store,
        repository=check.result_repositories[0],
        need="private decision need",
        disposition=Disposition.ADOPT,
        rationale=("private rationale",),
        evidence_ids=("evidence",),
        reconsider_when=("trigger",),
        from_check_id=check.check_id,
        created_at=NOW,
    )
    recheck = rechecked(store, target_id=check.check_id, checked_at=LATER)
    adoption = used(
        store,
        repository=check.result_repositories[0],
        need="private adoption need",
        target="/private/target/path",
        proposed_files=("secret.txt",),
        native_tools=("tool",),
        tests=("test",),
        expected_postconditions=("done",),
        rollback=("undo",),
        remaining_evidence=("unknown",),
        created_at=NOW,
    )
    assert projection is not None

    summaries = [
        public_summary(check),
        public_summary(save),
        public_summary(decision),
        public_summary(recheck),
        public_summary(projection),
        public_summary(adoption),
    ]
    serialized = json.dumps(summaries, sort_keys=True)
    for forbidden in (
        str(tmp_path),
        "private-profile",
        "private need",
        "private rationale",
        "private list",
        "/private/target/path",
        "secret.txt",
    ):
        assert forbidden not in serialized
    assert [item["record_type"] for item in summaries] == [
        "check",
        "save",
        "decision",
        "recheck",
        "projection-plan",
        "adoption-plan",
    ]


def test_non_check_markdown_and_table_rendering(tmp_path: Path) -> None:
    plan = used(
        StateStore(tmp_path / "state"),
        repository="fixture-labs/a",
        need="test",
        target="synthetic-target",
        proposed_files=(),
        native_tools=(),
        tests=(),
        expected_postconditions=("done",),
        rollback=("undo",),
        remaining_evidence=(),
        created_at=NOW,
    )
    assert render(plan, OutputFormat.MARKDOWN).startswith("# AdoptionPlan\n")
    assert "plan_id" in render(plan, OutputFormat.TABLE)
