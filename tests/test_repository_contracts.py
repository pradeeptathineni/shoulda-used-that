from __future__ import annotations

from pathlib import Path

from scripts.generate_schemas import SCHEMAS, check_schemas, rendered_schemas, write_schemas
from scripts.validate_repository import validate


def test_generated_schemas_are_deterministic_and_current(tmp_path: Path) -> None:
    first = rendered_schemas()
    second = rendered_schemas()
    assert first == second
    assert len(first) == len(SCHEMAS) == 11
    write_schemas(tmp_path)
    assert check_schemas(tmp_path) == []
    changed = tmp_path / sorted(first)[0]
    changed.write_text("{}\n", encoding="utf-8")
    assert check_schemas(tmp_path) == [f"stale schema: {changed.name}"]


def test_repository_contract_validator_passes() -> None:
    assert validate() == []
