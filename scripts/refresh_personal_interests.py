#!/usr/bin/env python3
"""Refresh the reviewed personal-interest catalog from live public GitHub metadata.

The selection file is human-authored intent. This command supplies only volatile,
read-only repository facts, applies explicit quality gates, and reseals the public
profile. It never stars a repository or changes a GitHub List.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from shoulda_used_that.curation import CurationProfile, profile_fingerprint

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTION = ROOT / "curation" / "selections" / "personal-interests.json"
DEFAULT_OUTPUT = ROOT / "curation" / "entries" / "personal-interests.json"
DEFAULT_PROFILE = ROOT / "curation" / "profiles" / "shoulda-used-that.json"
GRAPHQL_CHUNK_SIZE = 40


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Read a captured GraphQL repository map instead of calling gh.",
    )
    args = parser.parse_args()

    selection = _object(json.loads(args.selection.read_text(encoding="utf-8")), "selection")
    repositories, memberships = _selection_repositories(selection)
    metadata = (
        _object(json.loads(args.metadata.read_text(encoding="utf-8")), "metadata")
        if args.metadata
        else _read_github_metadata(repositories)
    )
    payload = build_entries(selection, memberships, metadata)
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)
    _reseal_profile(args.profile)
    print(f"refreshed {len(payload['repository_evidence'])} screened repositories -> {args.output}")
    return 0


def build_entries(
    selection: dict[str, Any],
    memberships: dict[str, tuple[str, ...]],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    _reject_retired_context_fields(selection)
    reviewed_at = _timestamp(selection.get("reviewed_at"), "reviewed_at")
    minimum_stars = _integer(selection.get("minimum_stars"), "minimum_stars")
    maximum_staleness_days = _integer(
        selection.get("maximum_staleness_days"), "maximum_staleness_days"
    )
    evidence_receipt = _string(selection.get("evidence_receipt"), "evidence_receipt")
    decision_receipt_id = _string(selection.get("decision_receipt_id"), "decision_receipt_id")
    disposition_overrides = _object(
        selection.get("disposition_overrides", {}), "disposition_overrides"
    )
    license_overrides = _object(selection.get("license_overrides", {}), "license_overrides")
    exceptions = _object(selection.get("gate_exceptions", {}), "gate_exceptions")
    selected_repositories = set(memberships)
    for label, overrides in (
        ("disposition_overrides", disposition_overrides),
        ("license_overrides", license_overrides),
        ("gate_exceptions", exceptions),
    ):
        unknown = sorted(set(overrides) - selected_repositories, key=str.casefold)
        if unknown:
            raise SystemExit(f"{label} names unselected repositories: {', '.join(unknown)}")
    repository_evidence: list[dict[str, Any]] = []
    screenings: list[dict[str, Any]] = []
    projection_entries: list[dict[str, Any]] = []
    failures: list[str] = []
    cutoff = reviewed_at - timedelta(days=maximum_staleness_days)

    for requested_repository in sorted(memberships, key=str.casefold):
        facts = metadata.get(requested_repository.casefold())
        if not isinstance(facts, dict):
            failures.append(f"{requested_repository}: missing GitHub metadata")
            continue
        repository = facts.get("nameWithOwner")
        if (
            not isinstance(repository, str)
            or repository.casefold() != requested_repository.casefold()
        ):
            failures.append(f"{requested_repository}: canonical identity changed to {repository!r}")
            continue
        exception = exceptions.get(requested_repository, {})
        if exception and not isinstance(exception, dict):
            failures.append(f"{requested_repository}: gate exception must be an object")
            continue
        reason = exception.get("reason") if isinstance(exception, dict) else None
        if exception and not isinstance(reason, str):
            failures.append(f"{requested_repository}: gate exception needs an exact reason")
            continue
        stars = facts.get("stargazerCount")
        pushed_at = _optional_timestamp(facts.get("pushedAt"))
        license_info = facts.get("licenseInfo")
        detected_license = license_info.get("spdxId") if isinstance(license_info, dict) else None
        license_override = license_overrides.get(requested_repository)
        if license_override is not None and not isinstance(license_override, dict):
            failures.append(f"{requested_repository}: license override must be an object")
            continue
        license_id = detected_license
        license_locator: str | None = None
        if isinstance(license_override, dict):
            license_id = license_override.get("spdx_id")
            license_locator = license_override.get("locator")
            if not isinstance(license_id, str) or not isinstance(license_locator, str):
                failures.append(
                    f"{requested_repository}: license override needs spdx_id and locator"
                )
                continue
        gates = {
            "private": facts.get("isPrivate") is False,
            "archived": facts.get("isArchived") is False,
            "disabled": facts.get("isDisabled") is False,
            "fork": facts.get("isFork") is False,
            "description": isinstance(facts.get("description"), str)
            and bool(facts["description"].strip()),
            "license": isinstance(license_id, str)
            and license_id not in {"", "NOASSERTION", "OTHER"},
            "popularity": isinstance(stars, int) and stars >= minimum_stars,
            "freshness": pushed_at is not None and pushed_at >= cutoff,
        }
        waived = set(exception.get("waive", ())) if isinstance(exception, dict) else set()
        invalid_waivers = sorted(waived - {"popularity", "freshness", "license"})
        failed = sorted(name for name, passed in gates.items() if not passed and name not in waived)
        if invalid_waivers:
            failures.append(f"{requested_repository}: unsupported gate waivers {invalid_waivers}")
            continue
        if failed:
            failures.append(f"{requested_repository}: failed gates {failed}")
            continue

        disposition = disposition_overrides.get(requested_repository, "reference")
        if disposition not in {"learn", "reference", "trial"}:
            failures.append(f"{requested_repository}: unsupported disposition {disposition!r}")
            continue
        latest_release = facts.get("latestRelease")
        latest_tag = latest_release.get("tagName") if isinstance(latest_release, dict) else None
        default_branch = facts.get("defaultBranchRef")
        target = default_branch.get("target") if isinstance(default_branch, dict) else None
        commit = target.get("oid") if isinstance(target, dict) else None
        evidence = {
            "nameWithOwner": repository,
            "description": facts["description"].strip(),
            "stargazerCount": stars,
            "license": license_id,
            "pushedAt": facts.get("pushedAt"),
            "latestRelease": latest_tag,
            "defaultBranchCommit": commit,
        }
        evidence_digest = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        provenance = [
            {
                "source": "live GitHub repository metadata",
                "locator": f"https://api.github.com/repos/{repository}",
                "observed_at": _render_timestamp(reviewed_at),
                "content_digest": evidence_digest,
            },
            {
                "source": "cross-source curation decision",
                "locator": evidence_receipt,
                "observed_at": _render_timestamp(reviewed_at),
                "content_digest": None,
            },
        ]
        if license_locator is not None:
            provenance.append(
                {
                    "source": "reviewed repository license declaration",
                    "locator": license_locator,
                    "observed_at": _render_timestamp(reviewed_at),
                    "content_digest": None,
                }
            )
        repository_evidence.append(
            {
                "repository": repository,
                "url": facts["url"],
                "description": facts["description"].strip(),
                "observed_license": license_id,
                "archived": False,
                "latest_release": latest_tag,
                "latest_commit": commit,
                "popularity": {
                    "stars": stars,
                    "observed_at": _render_timestamp(reviewed_at),
                },
                "last_checked_at": _render_timestamp(reviewed_at),
                "freshness_state": "current",
                "source_provenance": provenance,
                "attribution_obligations": [],
                "field_classification": "public",
            }
        )
        screenings.append(
            {
                "repository": repository,
                "domain_tags": list(memberships[requested_repository]),
                "screening_basis": "metadata-and-eligibility",
                "decision_receipt_ids": [decision_receipt_id],
                "evidence_receipt_ids": [evidence_receipt],
                "notes": [reason] if reason else [],
                "screened_at": _render_timestamp(reviewed_at),
            }
        )
        projection_entries.append(
            {
                "repository": repository,
                "collection_memberships": list(memberships[requested_repository]),
                "primary_disposition": disposition,
            }
        )

    if failures:
        raise SystemExit("personal-interest refresh failed:\n- " + "\n- ".join(failures))
    return {
        "schema_version": "3.0",
        "repository_evidence": repository_evidence,
        "screenings": screenings,
        "projection_entries": projection_entries,
        "excluded_candidates": [],
    }


def _reject_retired_context_fields(selection: dict[str, Any]) -> None:
    retired: list[str] = []
    if "rationale_overrides" in selection:
        retired.append("rationale_overrides")
    collections = selection.get("collections")
    if isinstance(collections, dict):
        for slug, value in collections.items():
            if not isinstance(value, dict):
                continue
            for field in ("need", "reconsideration_trigger", "role"):
                if field in value:
                    retired.append(f"collections.{slug}.{field}")
    if retired:
        raise SystemExit(
            "retired contextual selection fields must move to explicit problem assessments: "
            + ", ".join(sorted(retired))
        )


def _selection_repositories(
    selection: dict[str, Any],
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    priority = _string_list(selection.get("collection_priority"), "collection_priority")
    collections = _object(selection.get("collections"), "collections")
    if set(priority) != set(collections):
        raise SystemExit("collection_priority must enumerate every selection collection exactly")
    memberships: dict[str, set[str]] = defaultdict(set)
    canonical_names: dict[str, str] = {}
    for slug in priority:
        collection = _object(collections.get(slug), slug)
        for repository in _string_list(collection.get("repositories"), f"{slug}.repositories"):
            folded = repository.casefold()
            prior = canonical_names.setdefault(folded, repository)
            if prior != repository:
                raise SystemExit(f"repository casing conflicts: {prior!r} and {repository!r}")
            memberships[prior].add(slug)
    stable = {
        repository: tuple(slug for slug in priority if slug in slugs)
        for repository, slugs in memberships.items()
    }
    return tuple(sorted(stable, key=str.casefold)), stable


def _read_github_metadata(repositories: tuple[str, ...]) -> dict[str, Any]:
    gh = shutil.which("gh")
    if gh is None:
        raise SystemExit("the official gh CLI is required for live metadata refresh")
    result: dict[str, Any] = {}
    for offset in range(0, len(repositories), GRAPHQL_CHUNK_SIZE):
        chunk = repositories[offset : offset + GRAPHQL_CHUNK_SIZE]
        fields: list[str] = []
        for index, repository in enumerate(chunk):
            owner, name = repository.split("/", 1)
            fields.append(
                f"""r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{
                  nameWithOwner url description stargazerCount pushedAt
                  isPrivate isArchived isDisabled isFork
                  licenseInfo {{ spdxId }}
                  latestRelease {{ tagName }}
                  defaultBranchRef {{ target {{ ... on Commit {{ oid }} }} }}
                }}"""
            )
        query = "query {\n" + "\n".join(fields) + "\n}"
        completed = subprocess.run(  # noqa: S603 - resolved gh path and fixed argument vector
            (gh, "api", "graphql", "-f", f"query={query}"),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise SystemExit(f"GitHub metadata query failed: {completed.stderr.strip()}")
        payload = _object(json.loads(completed.stdout), "GraphQL response")
        data = _object(payload.get("data"), "GraphQL data")
        for index, repository in enumerate(chunk):
            result[repository.casefold()] = data.get(f"r{index}")
    return result


def _reseal_profile(path: Path) -> None:
    profile = _object(json.loads(path.read_text(encoding="utf-8")), "profile")
    sources = profile.get("source_specifications")
    if not isinstance(sources, list):
        raise SystemExit("profile source_specifications must be a list")
    for source in sources:
        source_object = _object(source, "profile source")
        locator = _string(source_object.get("locator"), "source locator")
        source_path = ROOT / locator
        source_object["content_sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    normalized = CurationProfile.model_validate(profile).model_dump(mode="json")
    normalized["canonical_fingerprint"] = profile_fingerprint(normalized)
    path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{label} must be a non-empty string")
    return value.strip()


def _integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SystemExit(f"{label} must be a non-negative integer")
    return value


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise SystemExit(f"{label} must be a non-empty list")
    strings = tuple(_string(item, label) for item in value)
    if len(strings) != len(set(strings)):
        raise SystemExit(f"{label} contains duplicates")
    return strings


def _timestamp(value: Any, label: str) -> datetime:
    rendered = _string(value, label)
    parsed = datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise SystemExit(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def _optional_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC) if parsed.tzinfo else None


def _render_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
