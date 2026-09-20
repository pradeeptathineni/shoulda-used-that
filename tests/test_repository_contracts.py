from __future__ import annotations

import tomllib
from pathlib import Path

from scripts.generate_schemas import SCHEMAS, check_schemas, rendered_schemas, write_schemas
from scripts.validate_repository import (
    ROOT,
    catalog_upkeep_problems,
    catalog_workflow_problems,
    validate,
)


def test_generated_schemas_are_deterministic_and_current(tmp_path: Path) -> None:
    first = rendered_schemas()
    second = rendered_schemas()
    assert first == second
    assert len(first) == len(SCHEMAS) == 16
    write_schemas(tmp_path)
    assert check_schemas(tmp_path) == []
    changed = tmp_path / sorted(first)[0]
    changed.write_text("{}\n", encoding="utf-8")
    assert check_schemas(tmp_path) == [f"stale schema: {changed.name}"]


def test_repository_contract_validator_passes() -> None:
    assert validate() == []


def test_catalog_workflow_excludes_personal_mutation_authority() -> None:
    workflow = (ROOT / ".github" / "workflows" / "catalog.yml").read_text(encoding="utf-8")
    assert catalog_workflow_problems(workflow) == []
    assert catalog_workflow_problems(workflow + "\nGH_TOKEN: ${{ secrets.PERSONAL_PAT }}\n") == [
        "catalog workflow contains forbidden boundary 'secrets.'",
        "catalog workflow contains forbidden boundary 'GH_TOKEN'",
    ]


def test_one_shot_catalog_upkeep_is_read_only() -> None:
    command = (ROOT / "scripts" / "upkeep_catalog.sh").read_text(encoding="utf-8")
    assert catalog_upkeep_problems(command) == []
    assert catalog_upkeep_problems(
        command + "\ngh api --method PUT /user/starred/example/repo\n"
    ) == [
        "catalog upkeep script contains forbidden boundary 'gh '",
    ]


def test_homepage_actions_keep_mobile_touch_separation() -> None:
    homepage = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    stylesheet = (ROOT / "docs" / "curation" / "assets" / "catalog.css").read_text(encoding="utf-8")

    action_group = homepage.split('<div class="home-actions" markdown>', maxsplit=1)[1].split(
        "</div>", maxsplit=1
    )[0]
    assert action_group.count("{ .md-button") == 2

    mobile_rules = stylesheet.split("@media (max-width: 44rem)", maxsplit=1)[1].split(
        "@media (prefers-reduced-motion", maxsplit=1
    )[0]
    action_layout = mobile_rules.split(".home-actions > p", maxsplit=1)[1].split("}", maxsplit=1)[0]
    action_button = mobile_rules.split(".home-actions .md-button", maxsplit=1)[1].split(
        "}", maxsplit=1
    )[0]
    assert "gap: .75rem" in action_layout
    assert "min-height: 3rem" in action_button
    assert "white-space: normal" in action_button
    assert "width: 100%" in action_button


def test_primary_navigation_and_homepage_obey_the_reader_information_budget() -> None:
    config = tomllib.loads((ROOT / "zensical.toml").read_text(encoding="utf-8"))
    navigation = config["project"]["nav"]
    labels = tuple(next(iter(item)) for item in navigation)
    assert labels == ("Home", "Explore", "CLI", "How it works")
    assert len(navigation) <= 4
    assert all(isinstance(next(iter(item.values())), str) for item in navigation)

    homepage = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    first_screen = homepage.split("## What the evidence means", maxsplit=1)[0]
    assert len(first_screen.split()) <= 150
    assert not {"fingerprint", "projection", "receipt"}.intersection(
        first_screen.casefold().split()
    )
