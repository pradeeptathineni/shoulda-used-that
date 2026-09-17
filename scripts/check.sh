#!/usr/bin/env bash
set -euo pipefail

uv lock --check
uv sync --all-groups --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run python scripts/generate_schemas.py --check
uv run python scripts/validate_repository.py
actionlint
uv run zizmor --pedantic .github/workflows
typos
lychee --no-progress --max-retries 3 README.md 'docs/**/*.md'
uv run coverage erase
uv run coverage run -m pytest
uv run coverage report
uv run python -m build
