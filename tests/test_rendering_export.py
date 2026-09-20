from __future__ import annotations

import json
from pathlib import Path

import yaml

from shoulda_used_that.models import Disposition, FilterSpec
from shoulda_used_that.rendering import OutputFormat, render
from shoulda_used_that.services import checked, rechecked, remembered
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
    assert table.count(receipt.result_repositories[0]) == 2
    assert f"Inspect: shoulda inspect github:{receipt.result_repositories[0]}" in table


def test_decision_and_recheck_human_views_stay_compact_while_machine_views_are_complete(
    tmp_path: Path, fixture_path: Path
) -> None:
    store = StateStore(tmp_path / "state")
    check = checked(
        store,
        need="private need remains in authoritative state",
        source_requests=(fixture_request(fixture_path),),
        filter_spec=FilterSpec(limit=1),
        observed_at=NOW,
    )
    decision = remembered(
        store,
        repository=check.result_repositories[0],
        need="canonical bytes",
        disposition=Disposition.ADOPT,
        rationale=("published behavior matches",),
        evidence_ids=("manual-vector",),
        reconsider_when=("vectors fail",),
        from_check_id=check.check_id,
        created_at=NOW,
    )
    recheck = rechecked(store, target_id=check.check_id, checked_at=LATER)

    decision_table = render(decision, OutputFormat.TABLE)
    decision_markdown = render(decision, OutputFormat.MARKDOWN)
    recheck_markdown = render(recheck, OutputFormat.MARKDOWN)
    assert "Reconsider when" in decision_table
    assert "immutable local decision" in decision_table
    assert "Source check" in decision_table
    assert check.check_id in decision_table
    assert f"Source check: `{check.check_id}`" in decision_markdown
    for human_view in (decision_table, decision_markdown):
        assert check.source_observations[0].payload_fingerprint not in human_view
        assert check.result_set_fingerprint not in human_view
        assert "manual-vector" not in human_view
    assert "Last-known-good preserved" in recheck_markdown
    assert "Source errors" in recheck_markdown
    assert json.loads(render(decision, OutputFormat.JSON)) == decision.model_dump(mode="json")
    assert yaml.safe_load(render(recheck, OutputFormat.YAML)) == recheck.model_dump(mode="json")
