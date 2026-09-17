#!/usr/bin/env python3
"""Generate or verify deterministic public JSON Schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from shoulda_used_that.curation import CurationProfile, CurationSnapshot
from shoulda_used_that.github_apply import ApplyReceipt, VerifyReceipt
from shoulda_used_that.models import (
    AdoptionPlan,
    Candidate,
    CheckReceipt,
    DecisionReceipt,
    ProjectionPlan,
    RecheckReceipt,
    SaveReceipt,
)
from shoulda_used_that.project_context import ProjectSnapshot
from shoulda_used_that.projection import GitHubProjectionPlan

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "schemas"
SCHEMAS: dict[str, type[BaseModel]] = {
    "adoption-plan": AdoptionPlan,
    "candidate": Candidate,
    "check-receipt": CheckReceipt,
    "decision-receipt": DecisionReceipt,
    "projection-plan": ProjectionPlan,
    "recheck-receipt": RecheckReceipt,
    "save-receipt": SaveReceipt,
    "curation-profile": CurationProfile,
    "curation-snapshot": CurationSnapshot,
    "project-snapshot": ProjectSnapshot,
    "github-projection-plan": GitHubProjectionPlan,
    "apply-receipt": ApplyReceipt,
    "verify-receipt": VerifyReceipt,
}


def rendered_schemas() -> dict[str, bytes]:
    """Return deterministic schema documents keyed by filename."""

    documents: dict[str, bytes] = {}
    for stem, model in SCHEMAS.items():
        schema = model.model_json_schema(mode="serialization")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = (
            "https://github.com/pradeeptathineni/shoulda-used-that/"
            f"blob/main/schemas/{stem}.schema.json"
        )
        documents[f"{stem}.schema.json"] = (
            json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode()
    return documents


def write_schemas(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    expected = rendered_schemas()
    for name, payload in expected.items():
        (output / name).write_bytes(payload)


def check_schemas(output: Path) -> list[str]:
    expected = rendered_schemas()
    problems: list[str] = []
    actual_names = {path.name for path in output.glob("*.schema.json")}
    if actual_names != set(expected):
        problems.append(
            f"schema file set differs: expected={sorted(expected)} actual={sorted(actual_names)}"
        )
    for name, payload in expected.items():
        path = output / name
        if not path.exists() or path.read_bytes() != payload:
            problems.append(f"stale schema: {name}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        problems = check_schemas(args.output)
        if problems:
            print("\n".join(problems))
            return 1
        print(f"verified {len(SCHEMAS)} generated schemas")
        return 0
    write_schemas(args.output)
    print(f"generated {len(SCHEMAS)} schemas in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
