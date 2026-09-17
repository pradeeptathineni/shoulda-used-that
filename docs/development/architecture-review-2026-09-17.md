---
title: Architecture and public-writing review — 2026-09-17
description: End-to-end review of product intent, reuse, safety boundaries, maintainability, and public readability.
---

# Architecture and public-writing review — 2026-09-17

!!! note "Review snapshot"
    This page records the pre-`v0.3.0` architecture and writing baseline. The
    [v0.3.0 public-surface review](public-surface-review-v0.3.0.md) covers the later First Reader
    and ZeroSlop passes and the resulting reader-first changes.

## Outcome

The architecture fits the product's intent: ShouldaUsedThat keeps the small deterministic residual
that GitHub and established tools do not provide together. It does not contain a runtime model,
crawler, database, hosted control plane, or custom frontend. The strongest parts are the canonical
receipt chain, fail-closed filtering, explicit project context, allowlisted public export, and the
sealed additive-only GitHub mutation boundary.

The review found no path from a read, reason, or record command to a network mutation or target
repository write. It also found no reason to replace the current architecture. The changes from
this review concentrate on public clarity, truthful curation language, bounded generated output,
and maintainability around the most branched orchestration paths.

## Surfaces reviewed

- CLI-to-service-to-domain flow and the import boundary across the Python package.
- Candidate facts, hard and soft filters, canonical JSON, immutable receipts, and local state.
- Project and SBOM inspection, curation compilation, public export, and generated site structure.
- GitHub capability probing, state reads, projection, approval, additive mutation, progress
  receipts, readback, and independent verification.
- Runtime, development, CI, security, documentation, and release dependencies against their
  recorded roles and removal boundaries.
- README, homepage, catalog overview, GitHub-facing description, dogfood proof, and generated entry
  language.
- Workflow permissions, action pins, link checking, static-site verification, and local gates.

The review used source inspection, existing contracts and receipts, focused and full tests,
deterministic catalog replay, rendered desktop/mobile inspection, and read-only OSS analyzers. It
did not perform a live GitHub write or treat popularity as a security audit.

## Architecture shape

The package has a conventional and useful direction of dependency:

1. `cli.py` parses explicit operator intent and chooses a rendering.
2. `services.py` coordinates use cases without owning transport details.
3. Domain modules own typed facts and rules: candidates, curation, project context, projection,
   apply receipts, and postconditions.
4. GitHub and source adapters own external reads or the one narrowly authorized mutation surface.
5. `state.py` owns local versioned storage; `public_export.py` owns the allowlisted static view.

This is a simplest-complete architecture. Further service classes, repositories, plugin systems,
or a production agent backend would add indirection without removing a measured problem.

## Reuse findings

The implementation already follows a strong “one established owner per role” pattern. Click,
Pydantic, JMESPath, platformdirs, RFC 8785, Rich, pytest, Hypothesis, Ruff, mypy, GitHub-native
security/release features, and the official `gh` transport each own a distinct concern. The custom
code is chiefly the product's differentiator: binding a named need and project context to evidence,
a decision, a reconsideration trigger, and a safely replayable curation state.

The review added one reusable tool rather than building a prose engine: Vale 3.21.0 now runs narrow,
offline public-copy rules through the official action pinned at commit
`518a9136acc6e6668ce7c00d367051e0941e87ff`. First Reader and ZeroSlop remain review techniques,
not dependencies or authorities. The [public-writing receipt](../decisions/public-writing.json)
records why.

Read-only review tools also included Radon 6.0.1 and Vulture 2.14. Radon identified projection and
apply orchestration as high-branching paths. Those phases were extracted into named validation,
projection, and live-capability steps, and Ruff now enforces a McCabe ceiling of 24. Vulture found
no credible dead production code; its reported `cls` parameters are Pydantic validator signatures.
Neither one-time analyzer entered the dependency graph.

## Public-writing findings and changes

### The promise was accurate but buried

The previous README and homepage opened with “deterministic-first,” receipt machinery, and the
execution chain. Those details matter, but they required a new reader to understand the internals
before learning the job. Both entrypoints now lead with the outcome: find existing open source
before building from scratch, inspect the evidence, and preserve what could change the choice.

A context-free First Reader skim of the earlier copy still recovered the intended promise and said
it would continue reading. That is a positive signal for the underlying idea. A second fresh skim
of the rewrite found the outcome and next action immediately visible, then identified four narrower
problems: trust language broader than the checks, operational jargon in README status, a homepage
command chain shown too early, and an operator-only eligibility badge repeated on every collection.
The copy now bounds trust to visible evidence, defers command detail and live counts to their proof
pages, defines freshness, and removes the repeated badge.

### The catalog overview duplicated the catalog

The overview rendered all 221 record cards even though the complete entry index and individual
pages already existed. It contained 10,686 Markdown words and coupled any upstream description
change to the landing page. The overview now renders 12 collection cards and 596 words. The full
entry index, search, individual rationale, provenance, freshness, receipt links, canonical JSON,
and deterministic manifest remain intact. A single description change no longer rewrites the
overview.

### “Reviewed” needed a visible limit

The selection generator repeated a generic claim that every repository was a “strong prior-art
checkpoint after maintainer review.” That language was both repetitive and broader than the
evidence. Generated rationales now say exactly what ran: public metadata and fit review. They also
say what it does not establish: code, security, or adoption approval. A human-authored rationale
override supports cases where a broad collection needs a more exact boundary.

An offline ZeroSlop 2.12.1 diagnostic after editing scored the homepage 13.2 and README 21.0,
both in its “clear” band. It scored the generated catalog overview 28.0 because repeated collection
descriptions include list rhythms and triads. That false-positive-prone result reinforces the
chosen boundary: use the tool to prompt review, never as an authorship claim or release threshold.

## `awesome-llm-apps` verdict

`Shubhamsaboo/awesome-llm-apps` is high-signal as a discovery and learning map: at the review point
it was active, Apache-2.0, and had 138,635 stars and 20,370 forks. It is not a blanket production or
security endorsement of every example. The repository is heterogeneous, its examples own their
dependencies, it has no repo-wide release artifact, and its workflows include moving action tags.

The existing **Learn** disposition is therefore correct. Its catalog rationale now says to use it
to discover examples and techniques while reviewing each example independently. This review used
its First Reader skill at exact commit `f163bb5a92111cee4610ac98e5dce4c6a2a09c26`; that useful
technique does not make the parent repository a runtime dependency.

## Reliability changes

- The link gate now uses an existing `GITHUB_TOKEN`, or the authenticated official `gh` token when
  available, and limits each host to two concurrent requests with a 250 ms floor. Bulk
  `api.github.com` provenance locators are excluded because the live metadata refresh already owns
  their validation and a second crawl triggers GitHub's secondary rate limit. The token is scoped
  to the `lychee` process and is not written or printed.
- The prose gate targets six hand-authored public entrypoints. It intentionally excludes the large
  generated entry corpus and upstream descriptions.
- Projection and apply refactoring preserved the ordering, canonical semantic payload, sealed
  fingerprint, operation caps, drift checks, append-only receipts, and independent readback.

## Residual risks and explicit non-goals

- Local state is a single-user file store without cross-process locking. Keep that design until
  measured concurrent writers or query volume justify SQLite; concurrent mutation sessions are not
  supported.
- `services.py`, `public_export.py`, and `project_context.py` remain large. Their roles are cohesive,
  and broad file splitting would add navigation cost. Reconsider when change history shows coupled
  edits or when a function exceeds the enforced complexity ceiling.
- Zensical remains an exact pre-1.0 development trial. Markdown and canonical JSON remain complete
  without it, which keeps replacement cheap.
- GitHub Lists use a preview surface. Unknown item types, identity drift, missing scope, conflicting
  names or descriptions, private repositories, expired plans, CI, and non-interactive execution
  continue to fail closed.
- Popularity is discovery evidence only. Dependency adoption still needs its own version, license,
  compatibility, security, and project-fit review.
- Prose lint catches repeatable phrases, not reader interest or truth. A human owns final meaning
  and tone; optional AI-assisted editing remains outside runtime and canonical state.

## Reconsideration triggers

Re-open the architecture when measured concurrency requires transactional state, GitHub changes the
Lists contract, a public export needs a server-side capability, a current dependency no longer owns
its role well, or the complexity ceiling repeatedly blocks ordinary changes. Re-open the writing
loop when the rules create repeated false positives, a first-reader test identifies the same missed
friction more than once, or a mature offline tool can replace project-owned policy without weakening
fidelity.
