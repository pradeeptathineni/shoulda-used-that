---
name: shoulda-development
description: Develop or review ShouldaUsedThat domain behavior, receipts, adapters, filters, state, or release evidence while preserving its deterministic, local-first, no-hidden-mutation contracts.
---

# Shoulda Development

Use this skill for implementation or review work in this repository.

## Start with the smallest relevant packet

1. Read `AGENTS.md` for durable boundaries and commands.
2. Read `docs/architecture/implementation-brief.md` for product behavior only when the task changes a command or state contract.
3. Read `docs/architecture/dogfood-reuse-audit.md` and the relevant file under `docs/decisions/` before adding a dependency, custom module, workflow, or release tool.
4. Read the source, schema, and tests directly involved in the task. Do not reload the complete planning history.

The development method applies the pinned MIT-licensed `context-engineering` and `source-driven-development` skills from `addyosmani/agent-skills` commit `be4e44a9fbc5e8df0beaefadbb28bd22ee61cc39`. Use selective context, current primary documentation, exact versions, explicit conflicts, and preserved unknowns. The public application record is `docs/development/context-receipt.md`; do not copy the upstream collection into this repository.

## Preserve these invariants

- Commands `checked`, `saved`, `remembered`, `rechecked`, and `used` only read, reason, record, or plan.
- `apply` and `verify` remain fixture-only contract commands in `v0.1.0`; no live external mutation path exists.
- State is profile-scoped and external to repositories. Receipts are immutable and superseded rather than edited.
- Hard gates run before soft filters. Unknown hard-gate facts fail closed; unknown soft evidence remains visible unless explicitly filtered.
- Repeated values within a field are OR; fields are AND; exclusions win; canonical identity is the final stable tie-breaker.
- `saved --all` uses exactly one completed check's visible result and stored fingerprint.
- Source errors retain last-known-good evidence and add a typed error observation.
- JSON/RFC 8785 state is authoritative; YAML and Markdown are validated renderings.

## Finish with evidence

Run focused tests first, then the affected full gates. Record the exact command and outcome. For a substantial selection, add or update its machine-readable receipt and human explanation before committing. Before release, run correctness/security review, then the pinned `ponytail-review` and `ponytail-audit` guidance at `e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156`; its minimal-testing advice does not apply here.
