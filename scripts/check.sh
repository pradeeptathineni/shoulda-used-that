#!/usr/bin/env bash
set -euo pipefail

uv lock --check
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python scripts/generate_schemas.py --check
uv run python scripts/validate_repository.py
./scripts/upkeep_catalog.sh
./scripts/review_public_writing.sh
actionlint
uv run zizmor --pedantic .github/workflows
typos
lychee_token="${GITHUB_TOKEN:-}"
if [[ -z "$lychee_token" ]] && command -v gh >/dev/null 2>&1; then
  lychee_token="$(gh auth token 2>/dev/null || true)"
fi
# Live catalog refresh owns API provenance; crawling hundreds of API locators here triggers
# GitHub's secondary rate limit without adding a separate correctness check.
if [[ -n "$lychee_token" ]]; then
  GITHUB_TOKEN="$lychee_token" lychee --no-progress --max-retries 3 \
    --host-concurrency 2 --host-request-interval 250ms \
    --exclude '^https://api\.github\.com/' \
    --exclude '^https://pradeeptathineni\.github\.io/shoulda-used-that/' \
    README.md 'docs/**/*.md'
else
  lychee --no-progress --max-retries 3 \
    --host-concurrency 2 --host-request-interval 250ms \
    --exclude '^https://api\.github\.com/' \
    --exclude '^https://pradeeptathineni\.github\.io/shoulda-used-that/' \
    README.md 'docs/**/*.md'
fi
unset lychee_token
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report
uv run python -m build
