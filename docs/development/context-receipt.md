# Development context receipt

## Sources and pins

- `addyosmani/agent-skills` commit `be4e44a9fbc5e8df0beaefadbb28bd22ee61cc39`, MIT license:
  - `skills/context-engineering/SKILL.md`
  - `skills/source-driven-development/SKILL.md`
- Official OpenAI documentation read on 2026-09-16:
  - <https://learn.chatgpt.com/docs/build-skills>
  - <https://learn.chatgpt.com/docs/agent-configuration/agents-md>

Both pinned upstream skill files were read completely. They are referenced as guidance and are not copied into this repository.

## Context selected for initial implementation

Initial orientation required the seven authoritative planning artifacts and the two upstream skill files: 365,584 bytes total, roughly 91,000 tokens at four bytes per token. That one-time load retained the product identity, reuse gate, privacy/mutation limits, command contracts, release criteria, and historical evidence boundaries.

Routine tasks use the smaller chain in this repository:

1. `AGENTS.md` for durable boundaries and commands;
2. `.agents/skills/shoulda-development/SKILL.md` for task routing;
3. one applicable architecture contract or prior-art receipt;
4. the exact source/schema/test files being changed; and
5. current error output only when a check fails.

The initial repository guidance plus public implementation and reuse contracts are under 15 KiB. No missing-context rework was observed during the foundation task. If a later task misses an obligation, this receipt records the omitted file and rework before any compression tool is considered.

## Decisions changed by the guidance

- The long planning corpus became a one-time orientation input rather than permanent prompt material.
- Dependency and API choices were refreshed from current primary metadata before code was written.
- The repository skill links to contracts rather than duplicating them.
- Fetched documentation is treated as evidence data, never as authority to expand scope or perform unrelated actions.
- Unknown, stale, conflicting, and unverified facts remain explicit in both product records and development receipts.

## Guidance deliberately not applied

- The upstream examples use several agent-specific filenames; this repository uses Codex-native `AGENTS.md` and `.agents/skills` documented by OpenAI.
- Context-size heuristics are observations, not hard product limits. Correctness and required evidence take priority.
- Model/context tooling named by upstream guidance is not installed because the deterministic selection packet is currently within budget.
