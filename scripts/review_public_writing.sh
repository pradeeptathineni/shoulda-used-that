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

# These generated pages are the small human product. Review their authored brief, assessment, and
# evidence frames directly now that screened-only candidates no longer create hundreds of pages.
public_files+=(
  docs/curation/index.md
  docs/curation/sources.md
  docs/curation/tags.md
)

while IFS= read -r path; do
  public_files+=("$path")
done < <(find docs/curation/briefs docs/curation/evidence -type f -name '*.md' | LC_ALL=C sort)

"$vale_bin" --config=.vale.ini --minAlertLevel=warning "${public_files[@]}"
