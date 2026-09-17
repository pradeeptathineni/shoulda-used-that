---
title: Public writing quality loop
description: A bounded, evidence-preserving process for clear public copy.
---

# Public writing quality loop

Public writing should make the reader's job obvious before it explains the machinery. For
ShouldaUsedThat, that job is: **find existing open source before building from scratch, inspect what
fits the named need, and keep enough evidence to revisit the choice**.

## What must stay true

1. **Meaning is authoritative.** Claims come from source, tests, receipts, and executed evidence.
   A prose tool may flag or rephrase text; it cannot invent a fact or decision.
2. **Outcome comes first.** The README, homepage, and catalog overview lead with what a reader can
   do. Canonical fingerprints, postconditions, and projection mechanics remain available after
   that first explanation.
3. **Statuses keep their boundaries.** A star is a bookmark. “Reviewed” means the stated metadata
   and fit checks ran. Neither means code audit, security approval, adoption, or a universal rank.
4. **Compression must not hide evidence.** Overview pages summarize. Full entries, sources,
   receipts, canonical JSON, and reconsideration triggers remain directly reachable.
5. **Runtime stays AI-free.** AI-assisted wording is an editorial activity outside the product's
   deterministic facts, gates, hashes, plans, and state transitions.

## Review layers

### 1. Deterministic prose lint

[Vale](https://vale.sh/) runs offline against a deliberately small set of public entrypoints. The
project-owned rules flag generic hype and removable filler. They do not score authorship, rewrite
text, or inspect generated pages full of upstream descriptions.

```console
./scripts/review_public_writing.sh
```

The local and CI checks use Vale 3.21.0. The GitHub workflow pins the official Vale action by full
commit. A rule should be added only for an observed, repeatable problem; this is not a growing
house-style bureaucracy.

### 2. Context-free first read

For a material README, homepage, or catalog-overview change, give a fresh reviewer only the rendered
text and ask:

- What is this for?
- Who is it for?
- Would you continue, and why?
- Which sentence created friction or doubt?

This borrows the useful boundary from the First Reader skill reviewed at an exact commit: the first
reader does not receive author intent before reporting their impression. The answer is review
evidence, not an automatic gate.

### 3. Optional AI-pattern diagnostic

ZeroSlop may be run locally on hand-authored entrypoints to surface repeated phrasing patterns. Its
score is heuristic: it is not an authorship probability, a quality grade, or a CI threshold.
Generated catalog indexes and imported upstream descriptions are outside its useful boundary.
No unpublished copy is sent to a hosted rewriting service.

### 4. Human fidelity pass

The author or reviewer confirms that the edit preserves the underlying claim, states important
limits near the claim, and still sounds like this project. This pass owns the final wording.

## Scope

The required entrypoints are `README.md`, `docs/index.md`, the catalog overview, the dogfood and
in-use pages, and this policy. Other pages use the same principles, but high-volume generated pages
are reviewed through their generator, schema, samples, and deterministic diff rather than a prose
score over every repeated card.

The [public-writing decision receipt](../decisions/public-writing.json) records the tools considered,
their evidence, and their removal boundaries.
