#!/usr/bin/env bash
set -euo pipefail

vale_bin="${VALE_BIN:-vale}"
if ! command -v "$vale_bin" >/dev/null 2>&1; then
  echo "Vale 3.21.0 is required; install it or set VALE_BIN to its executable." >&2
  exit 1
fi

vale_version="$("$vale_bin" --version)"
if [[ "$vale_version" != "vale version 3.21.0" ]]; then
  echo "Vale 3.21.0 is required; found: $vale_version" >&2
  exit 1
fi

public_files=(
  AGENTS.md
  CHANGELOG.md
  CONTRIBUTING.md
  README.md
  SECURITY.md
  schemas/README.md
)

while IFS= read -r path; do
  public_files+=("$path")
done < <(find docs -type f -name '*.md' ! -path 'docs/curation/*' | LC_ALL=C sort)

# These pages are generated, but every sentence in their frame is owned here. Entry and
# collection bodies also contain imported repository descriptions, so their prose is reviewed at
# the generator and representative-sample boundary instead of treated as project-authored copy.
public_files+=(
  docs/curation/index.md
  docs/curation/selection.md
  docs/curation/dogfood.md
  docs/curation/in-use.md
  docs/curation/freshness.md
  docs/curation/sources.md
  docs/curation/collections/index.md
  docs/curation/tags.md
)

"$vale_bin" --config=.vale.ini --minAlertLevel=warning "${public_files[@]}"
