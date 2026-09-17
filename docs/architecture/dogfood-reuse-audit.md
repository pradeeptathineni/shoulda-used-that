# Implementation reuse gate

This dated gate records the selected owner for each implementation role. The machine-readable receipts in [`../decisions`](../decisions/) carry the evidence and reconsideration triggers.

| Role | Selected owner | Boundary |
|---|---|---|
| Environment and lock | `uv` 0.12.15 | Environment, lock, execution, and build orchestration only |
| Build backend | Hatchling 1.32.0 | PEP 517 backend only; no second environment manager |
| CLI | Click 8.5.x | Parsing and help; domain validation remains in Pydantic/services |
| Terminal rendering | Rich 15.x | Human TTY output only; never authoritative output |
| Contracts | Pydantic 2.13.x | Typed records and JSON Schema |
| Advanced filters | JMESPath 1.1.0 | Local queries over a stable public record; no custom DSL |
| State paths | platformdirs 4.11.x | OS paths; no repository-local runtime state |
| Canonical JSON | `rfc8785` 0.1.4 | Narrow bytes adapter and published vectors |
| GitHub transport | installed official `gh` | Read-only argument-vector subprocesses; no token client or SDK |
| Tests | pytest, Hypothesis, coverage.py | Examples, invariants, branch coverage |
| Static quality | Ruff and strict mypy | No overlapping formatter/linter/type checker |
| Security | pip-audit, CodeQL, dependency review, actionlint, zizmor, Scorecard | Separate dependency, source, workflow, and posture roles |
| Docs | executed examples, typos, lychee | No documentation framework |
| Release | GitHub release, checksum, inspected SBOM, GitHub attestation | No PyPI or second release service |
| VCS lifecycle | Git and GitHub native commits, protected `main`, annotated tag, release | Coherent public commits; push before hosted validation; never rewrite released history |

The implementation deliberately excludes Typer, Poetry, tox, Nox, Black, isort, Flake8, Bandit, Pyright, PyGithub, Octokit, agent frameworks, memory systems, embeddings, and extra release services because their roles are absent or already owned.

The dependency matrix was refreshed from PyPI and GitHub on 2026-09-16. Workflow action revisions,
actionlint 1.7.12, and zizmor 1.30.1 were refreshed from their primary repositories and package
metadata on 2026-09-17. Volatile versions, repository state, licenses, and action revisions are
rechecked before release.

Repository history is itself dogfood evidence. The first push establishes a reviewable vertical
slice, later pushes preserve the diagnosis/refinement boundary, and `v0.1.0` is tagged only after
the exact pushed commit passes hosted gates. No private planning artifacts, unrelated project
history, or generated runtime state may enter a commit.
