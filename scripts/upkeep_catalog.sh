#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repository_root}"

catalog_fingerprint() {
  find docs/curation -type f -print | LC_ALL=C sort | while IFS= read -r file; do
    printf '%s %s\n' "$(git hash-object "${file}")" "${file}"
  done
}

catalog_before="$(catalog_fingerprint)"
uv run --frozen --no-sync python scripts/generate_catalog.py --check
uv run --frozen --no-sync zensical build --clean --strict
uv run --frozen --no-sync python scripts/verify_site.py
catalog_after="$(catalog_fingerprint)"
if [[ "${catalog_before}" != "${catalog_after}" ]]; then
  echo "catalog upkeep changed docs/curation" >&2
  exit 1
fi
git diff --exit-code -- docs/curation
