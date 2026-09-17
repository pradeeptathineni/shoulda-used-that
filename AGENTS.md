# ShouldaUsedThat repository guidance

## Durable boundaries

- Keep the core deterministic and runtime-AI-free. Facts, gates, hashes, state transitions, and mutation plans must not depend on a model.
- Never write coordinator state into another repository. Runtime state belongs under `platformdirs` or an explicit `--state-dir`.
- Live GitHub behavior remains read-only for every read/reason/record command. In `v0.2.0`, `apply` may execute only an explicitly approved, unexpired `github-curation` plan whose full fingerprint and exact account match. It may add stars, create Lists, and add memberships; it must never unstar, remove membership, delete/rename a List, change privacy, run in CI, or edit a target.
- Use only public or synthetic fixtures. Do not use the maintainer's other projects as guidance, fixtures, or hidden test inputs.
- JSON is authoritative for hashed state. YAML, Markdown, and terminal tables are renderings.
- Add a public prior-art receipt before or alongside a production dependency or substantial custom module.
- Lead public writing with the reader's need and outcome. Preserve evidence and caveats, but do not make internal receipt machinery the opening pitch.
- Treat AI-assisted wording as a reviewed editorial aid only. It must never author facts, decisions, hashes, gates, or runtime behavior, and public claims must trace to repository evidence.

## Commands

- Sync: `uv sync --all-groups --frozen`
- Tests: `uv run pytest`
- Coverage: `uv run coverage run -m pytest && uv run coverage report`
- Quality: `uv run ruff format --check . && uv run ruff check . && uv run mypy`
- Build: `uv run python -m build`
- Full local gate: `./scripts/check.sh`
- Public writing: `./scripts/review_public_writing.sh`

For work on domain behavior, use the repository skill `shoulda-development` and load only the relevant public contract, decision receipt, schema, source, and tests.

## Code Review Rules

- Flag any path by which a read/reason/record command can perform a network mutation or target-repository write. The safe path is a sealed local plan.
- Flag filters that let an unknown hard-gate fact pass, apply OR across different fields, or omit the canonical-identity tie-breaker.
- Flag `saved --all` if it can escape one immutable post-filter check result or refresh the source implicitly.
- Flag revalidation that replaces last-known-good evidence after a source error or treats a timestamp-only change as material.
- Flag hashes produced from ordinary sorted JSON, mutable receipt edits, or renderings rather than RFC 8785 canonical JSON.
- Flag exports based on deny lists. Public export must use explicit allowlisted fields.
- Flag a GitHub membership update that sends only desired List IDs. It must re-read and send the union of current and approved memberships.
- Flag personal star/List mutation without an exact sealed plan, interactive approval boundary, drift recheck, per-operation receipt, and independent readback.
- Leave formatting and lint enforcement to CI.
