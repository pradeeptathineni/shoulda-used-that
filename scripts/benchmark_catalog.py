#!/usr/bin/env python3
"""Benchmark deterministic catalog compilation and the replaceable static view adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
from typing import Any

from shoulda_used_that.curation import compile_profile, load_profile, profile_fingerprint
from shoulda_used_that.public_export import write_public_catalog

ROOT = Path(__file__).resolve().parents[1]
BASE_PROFILE = ROOT / "curation" / "profiles" / "shoulda-used-that.json"
BASE_ENTRIES = ROOT / "curation" / "entries" / "shoulda-used-that.json"


def benchmark(entry_count: int) -> dict[str, Any]:
    if not 1 <= entry_count <= 10_000:
        raise ValueError("entry count must be between 1 and 10,000")
    with tempfile.TemporaryDirectory(prefix=f"shoulda-catalog-{entry_count}-") as raw_root:
        root = Path(raw_root)
        profile_path = _write_synthetic_inputs(root, entry_count)
        compile_started = time.perf_counter()
        snapshot = compile_profile(profile_path)
        compile_seconds = time.perf_counter() - compile_started
        profile = load_profile(profile_path)

        docs = root / "docs"
        _write_supporting_docs(docs)
        render_started = time.perf_counter()
        export, changed = write_public_catalog(snapshot, profile, docs / "curation")
        render_seconds = time.perf_counter() - render_started
        if not changed:
            raise RuntimeError("first synthetic catalog write unexpectedly reported a no-op")
        _, changed_again = write_public_catalog(snapshot, profile, docs / "curation")
        if changed_again:
            raise RuntimeError("second synthetic catalog write was not a semantic no-op")

        config = root / "zensical.toml"
        config.write_text(_zensical_config(), encoding="utf-8")
        build_started = time.perf_counter()
        completed = subprocess.run(  # noqa: S603 - fixed interpreter and arguments
            (
                sys.executable,
                "-m",
                "zensical",
                "build",
                "--config-file",
                str(config),
                "--clean",
                "--strict",
            ),
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
        build_seconds = time.perf_counter() - build_started
        if completed.returncode:
            output = (completed.stdout + completed.stderr)[-4000:]
            raise RuntimeError(f"strict synthetic build failed:\n{output}")

        built = root / "built"
        search_path = built / "search.json"
        searchable = search_path.read_text(encoding="utf-8").casefold()
        expected_search_terms = (
            "synthetic-owner/project-00000",
            f"synthetic-owner/project-{entry_count // 2:05d}",
            f"synthetic-owner/project-{entry_count - 1:05d}",
            "bounded synthetic need",
            "devops",
            "used here",
            "platform engineering & delivery",
        )
        missing_search_terms = tuple(
            term for term in expected_search_terms if term.casefold() not in searchable
        )
        return {
            "entry_count": entry_count,
            "compile_seconds": round(compile_seconds, 3),
            "render_seconds": round(render_seconds, 3),
            "strict_static_build_seconds": round(build_seconds, 3),
            "generated_source_files": len(export.generated_file_manifest) + 1,
            "generated_source_bytes": _tree_size(docs / "curation"),
            "built_site_files": sum(1 for path in built.rglob("*") if path.is_file()),
            "built_site_bytes": _tree_size(built),
            "search_index_bytes": search_path.stat().st_size,
            "search_terms_checked": len(expected_search_terms),
            "missing_search_terms": missing_search_terms,
            "second_export": "semantic-no-op",
        }


def _write_synthetic_inputs(root: Path, entry_count: int) -> Path:
    profile = deepcopy(_read_json(BASE_PROFILE))
    source = deepcopy(_read_json(BASE_ENTRIES))
    base_entry = source["entries"][0]
    collection_slugs = [item["slug"] for item in profile["collections"]]
    entries: list[dict[str, Any]] = []
    for index in range(entry_count):
        repository = f"synthetic-owner/project-{index:05d}"
        entry = deepcopy(base_entry)
        entry.update(
            {
                "repository": repository,
                "url": f"https://github.com/{repository}",
                "description": f"Synthetic catalog project {index:05d} for scale validation.",
                "collection_memberships": [collection_slugs[index % len(collection_slugs)]],
                "primary_disposition": "adopt",
                "role": "synthetic benchmark component",
                "need": f"Bounded synthetic need {index:05d} with searchable evidence.",
                "rationale": "Generated only for deterministic scale measurement.",
                "decision_receipt_ids": [],
                "evidence_receipt_ids": [f"https://example.invalid/evidence/{index:05d}"],
                "latest_release": f"v{index}.0.0",
                "latest_commit": f"{index:040x}",
                "popularity": {
                    "stars": index,
                    "observed_at": "2026-09-17T12:00:00Z",
                },
                "reconsideration_trigger": "The measured representation misses its target.",
                "source_provenance": [
                    {
                        "source": "synthetic-benchmark",
                        "locator": f"https://example.invalid/evidence/{index:05d}",
                        "observed_at": "2026-09-17T12:00:00Z",
                        "content_digest": f"sha256:{index:064x}",
                    }
                ],
                "attribution_obligations": [],
            }
        )
        entries.append(entry)
    profile_path = root / "curation" / "profiles" / "synthetic.json"
    source_root = root / "curation" / "entries"
    source_root.mkdir(parents=True)
    profile_path.parent.mkdir(parents=True)
    source_specs: list[dict[str, Any]] = []
    source_locators: list[str] = []
    for shard_index, start in enumerate(range(0, len(entries), 1000)):
        locator = f"curation/entries/synthetic-{shard_index:02d}.json"
        source = {
            "schema_version": "2.0",
            "entries": entries[start : start + 1000],
            "excluded_candidates": [],
        }
        source_bytes = (json.dumps(source, separators=(",", ":"), sort_keys=True) + "\n").encode()
        (root / locator).write_bytes(source_bytes)
        source_locators.append(locator)
        source_specs.append(
            {
                "kind": "public-json",
                "locator": locator,
                "content_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "license": "CC0-1.0",
                "attribution": "Generated synthetic benchmark data.",
            }
        )

    profile.update(
        {
            "profile_id": "synthetic-benchmark",
            "title": f"Synthetic {entry_count}-entry catalog",
            "description": "Bounded synthetic data for repeatable scale validation.",
            "source_specifications": source_specs,
        }
    )
    for collection in profile["collections"]:
        collection["exact_bound_sources"] = source_locators
        collection["max_candidates"] = 10_000
        collection["max_repositories"] = 10_000
    profile["canonical_fingerprint"] = profile_fingerprint(profile)
    profile_path.write_text(
        json.dumps(profile, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return profile_path


def _write_supporting_docs(docs: Path) -> None:
    (docs / "architecture").mkdir(parents=True)
    (docs / "decisions").mkdir(parents=True)
    (docs / "index.md").write_text("# Synthetic catalog benchmark\n", encoding="utf-8")
    (docs / "architecture" / "dogfood-reuse-audit.md").write_text(
        "# Synthetic reuse evidence\n", encoding="utf-8"
    )
    for name in ("dependencies.json", "quality-security.json", "zensical-site.json"):
        (docs / "decisions" / name).write_text("{}\n", encoding="utf-8")


def _zensical_config() -> str:
    return """[project]
site_name = "Synthetic ShouldaUsedThat benchmark"
docs_dir = "docs"
site_dir = "built"
extra_css = ["curation/assets/catalog.css"]
nav = [
  { "Home" = "index.md" },
  { "Catalog" = [
    { "Overview" = "curation/index.md" },
    { "What is used" = "curation/in-use.md" },
    { "Considered" = "curation/considered.md" },
    { "Freshness" = "curation/freshness.md" },
    { "Sources" = "curation/sources.md" },
    { "Collections" = "curation/collections/index.md" },
    { "Entries" = "curation/entries/index.md" },
    { "Tags" = "curation/tags.md" },
  ] },
]

[project.theme]
variant = "modern"
font = false

[project.plugins.search]

[project.plugins.tags]
"""


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected an object: {path}")
    return payload


def _tree_size(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=(1000, 5000))
    args = parser.parse_args()
    result = {
        "schema_version": "1.0",
        "python": platform.python_version(),
        "platform": f"{platform.system()}-{platform.machine()}",
        "zensical": version("zensical"),
        "measurements": [benchmark(size) for size in args.sizes],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(any(item["missing_search_terms"] for item in result["measurements"]))


if __name__ == "__main__":
    raise SystemExit(main())
