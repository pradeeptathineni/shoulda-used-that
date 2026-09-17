from __future__ import annotations

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
    assert len(first) == len(SCHEMAS) == 14
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
