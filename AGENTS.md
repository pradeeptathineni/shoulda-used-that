# ShouldaUsedThat repository guidance

## Durable boundaries

- Keep the core deterministic and runtime-AI-free. Facts, gates, hashes, state transitions, and mutation plans must not depend on a model.
- Never write coordinator state into another repository. Runtime state belongs under `platformdirs` or an explicit `--state-dir`.
- Live GitHub behavior is read-only in `v0.1.0`. `saved --list`, `used`, `apply`, and `verify` may create or validate local plans but must not star, unstar, change Lists, or edit targets.
- Use only public or synthetic fixtures. Do not use the maintainer's other projects as guidance, fixtures, or hidden test inputs.
- JSON is authoritative for hashed state. YAML, Markdown, and terminal tables are renderings.
- Add a public prior-art receipt before or alongside a production dependency or substantial custom module.

## Commands

- Sync: `uv sync --all-groups --frozen`
- Tests: `uv run pytest`
- Coverage: `uv run coverage run -m pytest && uv run coverage report`
- Quality: `uv run ruff format --check . && uv run ruff check . && uv run mypy`
- Build: `uv run python -m build`
- Full local gate: `./scripts/check.sh`

For work on domain behavior, use the repository skill `shoulda-development` and load only the relevant public contract, decision receipt, schema, source, and tests.

## Code Review Rules

- Flag any path by which a read/reason/record command can perform a network mutation or target-repository write. The safe path is a sealed local plan.
- Flag filters that let an unknown hard-gate fact pass, apply OR across different fields, or omit the canonical-identity tie-breaker.
- Flag `saved --all` if it can escape one immutable post-filter check result or refresh the source implicitly.
- Flag revalidation that replaces last-known-good evidence after a source error or treats a timestamp-only change as material.
- Flag hashes produced from ordinary sorted JSON, mutable receipt edits, or renderings rather than RFC 8785 canonical JSON.
- Flag exports based on deny lists. Public export must use explicit allowlisted fields.
- Leave formatting and lint enforcement to CI.
