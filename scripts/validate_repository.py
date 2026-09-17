#!/usr/bin/env python3
"""Validate public metadata, prior-art receipts, action pins, and privacy boundaries."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DESCRIPTION = (
    "A deterministic-first, AI-optional coordinator that discovers, vets, remembers, "
    "and revalidates existing OSS before you write more code."
)
EXPECTED_TAGLINE = "Turn “Shit, I shoulda used that” into “Glad I checked first.”"
RECEIPT_FIELDS = {
    "schema_version",
    "receipt_id",
    "need",
    "artifact_role",
    "discovery",
    "contenders",
    "hard_gates",
    "unknowns",
    "decision_effect",
    "reconsider_when",
    "observed_at",
}
FORBIDDEN_PUBLIC_TEXT = (
    "project-coordinator" + "-planning",
    "SHOULDAUSEDTHAT_NEW" + "_CHAT_PROMPT",
    "/Users/" + "pradeeptathineni",
    "Documents/code/" + "_PROJECTS",
)
ACTION_PIN = re.compile(r"^\s*-?\s*uses:\s*[^#\s]+@([0-9a-f]{40})(?:\s*#.*)?$")
CATALOG_WORKFLOW_REQUIRED = (
    'cron: "43 8 * * 4"',
    "permissions: {}",
    "cancel-in-progress: false",
    "contents: read",
    "timeout-minutes:",
    "./scripts/upkeep_catalog.sh",
    "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'",
    "github.event_name == 'push' || github.event_name == 'workflow_dispatch'",
    "actions/upload-pages-artifact@fc324d3547104276b827a68afc52ff2a11cc49c9",
    "actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d",
    "actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346",
    "python3 -m scripts.verify_live_site",
    "PAGE_URL: ${{ steps.deployment.outputs.page_url }}",
    "id-token: write",
    "pages: write",
)
CATALOG_WORKFLOW_FORBIDDEN = (
    "pull_request_target:",
    "secrets.",
    "GH_TOKEN",
    "gh auth",
    "shoulda apply",
    "updateUserList",
    "updateUserListsForItem",
    "PUT /user/starred",
)
CATALOG_UPKEEP_REQUIRED = (
    "set -euo pipefail",
    "uv run --frozen --no-sync python scripts/generate_catalog.py --check",
    "uv run --frozen --no-sync zensical build --clean --strict",
    "uv run --frozen --no-sync python scripts/verify_site.py",
    'catalog_before="$(catalog_fingerprint)"',
    'catalog_after="$(catalog_fingerprint)"',
    "git diff --exit-code -- docs/curation",
)
CATALOG_UPKEEP_FORBIDDEN = (
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "gh ",
    "shoulda apply",
    "curl ",
    "wget ",
)


def _candidate_files() -> list[Path]:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required to enumerate the public repository boundary")
    completed = subprocess.run(  # noqa: S603 - resolved Git executable and fixed arguments
        (git, "ls-files", "--cached", "--others", "--exclude-standard"),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in completed.stdout.splitlines() if line]


def catalog_workflow_problems(text: str) -> list[str]:
    """Keep public upkeep and Pages deployment outside personal-account authority."""

    problems = [
        f"catalog workflow misses required boundary {value!r}"
        for value in CATALOG_WORKFLOW_REQUIRED
        if value not in text
    ]
    problems.extend(
        f"catalog workflow contains forbidden boundary {value!r}"
        for value in CATALOG_WORKFLOW_FORBIDDEN
        if value in text
    )
    return problems


def catalog_upkeep_problems(text: str) -> list[str]:
    """Require a deterministic local command with no network-mutation authority."""

    problems = [
        f"catalog upkeep script misses required boundary {value!r}"
        for value in CATALOG_UPKEEP_REQUIRED
        if value not in text
    ]
    problems.extend(
        f"catalog upkeep script contains forbidden boundary {value!r}"
        for value in CATALOG_UPKEEP_FORBIDDEN
        if value in text
    )
    return problems


def validate() -> list[str]:
    problems: list[str] = []
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    if project["name"] != "shoulda-used-that":
        problems.append("project distribution name is not shoulda-used-that")
    if project["version"] != "0.2.0":
        problems.append("project version is not 0.2.0")
    if project["description"] != EXPECTED_DESCRIPTION:
        problems.append("project description differs from the public contract")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if EXPECTED_TAGLINE not in readme:
        problems.append("README tagline differs from the public contract")

    catalog_workflow = ROOT / ".github" / "workflows" / "catalog.yml"
    if not catalog_workflow.is_file() or catalog_workflow.is_symlink():
        problems.append("catalog workflow is missing or unsafe")
    else:
        problems.extend(catalog_workflow_problems(catalog_workflow.read_text(encoding="utf-8")))

    catalog_upkeep = ROOT / "scripts" / "upkeep_catalog.sh"
    if not catalog_upkeep.is_file() or catalog_upkeep.is_symlink():
        problems.append("catalog upkeep script is missing or unsafe")
    else:
        problems.extend(catalog_upkeep_problems(catalog_upkeep.read_text(encoding="utf-8")))

    receipt_ids: set[str] = set()
    for path in sorted((ROOT / "docs" / "decisions").glob("*.json")):
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.relative_to(ROOT)} is invalid JSON: {exc}")
            continue
        if not isinstance(payload, dict):
            problems.append(f"{path.relative_to(ROOT)} is not an object")
            continue
        missing = RECEIPT_FIELDS - payload.keys()
        if missing:
            problems.append(f"{path.relative_to(ROOT)} misses fields {sorted(missing)}")
        receipt_id = payload.get("receipt_id")
        if not isinstance(receipt_id, str) or receipt_id in receipt_ids:
            problems.append(f"{path.relative_to(ROOT)} has an invalid or duplicate receipt_id")
        else:
            receipt_ids.add(receipt_id)
        if not payload.get("contenders") or not payload.get("reconsider_when"):
            problems.append(
                f"{path.relative_to(ROOT)} has no contenders or reconsideration trigger"
            )

    for path in _candidate_files():
        if not path.is_file() or path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for forbidden in FORBIDDEN_PUBLIC_TEXT:
            if forbidden in text:
                problems.append(f"{path.relative_to(ROOT)} contains private marker {forbidden!r}")
        if path.parent == ROOT / ".github" / "workflows" or (
            ROOT / ".github" / "workflows" in path.parents
        ):
            for number, line in enumerate(text.splitlines(), start=1):
                if (
                    "uses:" in line
                    and not line.lstrip().startswith("#")
                    and not ACTION_PIN.match(line)
                ):
                    problems.append(
                        f"{path.relative_to(ROOT)}:{number} action is not pinned to a full SHA"
                    )

    if len(receipt_ids) < 9:
        problems.append("fewer than nine facet-level prior-art receipts are present")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        print("\n".join(problems))
        return 1
    print("repository metadata, receipts, action pins, and privacy markers verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
