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
| Docs | generated Markdown/JSON, Zensical 0.0.62, typos, lychee | Zensical is a development-only view adapter; canonical source remains portable |
| Release | CycloneDX Python SBOM, GitHub release, checksum, GitHub attestation | Syft measured and rejected for this Python environment; no PyPI or second release service |
| VCS lifecycle | Git and GitHub native commits, protected `main`, annotated tag, release | Coherent public commits; push before hosted validation; never rewrite released history |

## `v0.2.0` expansion decisions

| Role | Selected owner | Boundary |
|---|---|---|
| Star/List identity and transport | GitHub REST plus GraphQL through `gh` 2.101.0 | Current live schema exposes repository-only `UserListItems`, native create/update membership mutations, and 2026-03-10 REST; no HTML scraping or second credential store |
| Project inventory | Supplied SPDX/CycloneDX first; bounded local facts and GitHub metadata second | No universal manifest parser, target writes, inferred needs, or silent external-tool installation |
| Curation compiler | Small deterministic ShouldaUsedThat residual | Joins exact public receipts and profile intent; popularity and source presence never become fit scores |
| Public catalog | Generated JSON/Markdown plus Zensical 0.0.62 trial | Development-only, MIT, pre-1.0, pinned and removable; no runtime API, analytics, or database |
| Public hosting | GitHub Pages Actions deployment | Static artifact only, least permissions, no personal credential |
| Scheduling | One deterministic command invoked by OS scheduler or an optional product heartbeat | No daemon and never unattended `apply` |

The current GitHub REST versions were read from `GET /versions` on 2026-09-17: `2026-03-10` and
`2022-11-28`. New adapters target `2026-03-10`; the older version remains supported until
2028-03-10 but is not the new integration baseline. Live GraphQL introspection confirmed
`createUserList`, `updateUserList`, and `updateUserListsForItem`, with repository as the only current
`UserListItems` variant. Lists remain a public preview, so capability probes and typed
`preview_changed` failures stay mandatory.

Zensical 0.0.62 was observed at immutable GitHub release `v0.0.62`, commit
`777d105f4e4cb03db6fa5e9a0887a8a013728b79`, under MIT. It is a bounded view-adapter trial only;
authoritative JSON and Markdown must remain complete if it is removed.

The native Pages path uses the official MIT-licensed `actions/configure-pages` 6.0.0,
`actions/upload-pages-artifact` 5.0.0, and `actions/deploy-pages` 5.0.1 releases pinned at commits
`45bfe0192ca1faeb007ade9deae92b16b8254a0d`, `fc324d3547104276b827a68afc52ff2a11cc49c9`,
and `368f82528645a54fb793d4d04e342629a3f51346`. Pull requests and schedules receive no deployment
permission. The scheduled path reads only committed public inputs and cannot reach personal Stars
or Lists.

The implementation deliberately excludes Typer, Poetry, tox, Nox, Black, isort, Flake8, Bandit, Pyright, PyGithub, Octokit, agent frameworks, memory systems, embeddings, and extra release services because their roles are absent or already owned.

The dependency matrix was refreshed from PyPI and GitHub on 2026-09-16. Workflow action revisions,
actionlint 1.7.12, and zizmor 1.30.1 were refreshed from their primary repositories and package
metadata on 2026-09-17. Volatile versions, repository state, licenses, and action revisions are
rechecked before release.

Repository history is itself dogfood evidence. The first push establishes a reviewable vertical
slice, later pushes preserve the diagnosis/refinement boundary, and `v0.1.0` is tagged only after
the exact pushed commit passes hosted gates. No private planning artifacts, unrelated project
history, or generated runtime state may enter a commit.
