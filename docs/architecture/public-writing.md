---
title: Public writing quality loop
description: How every reader-facing surface is reviewed without giving prose tools authority over facts.
---

# Public writing quality loop

Public writing should make the reader's job obvious before it explains the machinery. Here, that
job is: **find existing open source before building from scratch, see what fits a named need, and
keep enough evidence to revisit the choice**.

## The boundary never moves

1. **Repository evidence owns meaning.** Source, tests, receipts, and executed results supply the
   claims. An editorial tool may point out or rephrase text; it cannot invent a fact or decision.
2. **Outcome comes first.** First-contact pages explain what the reader can do. Fingerprints,
   postconditions, and projection mechanics stay reachable one layer deeper.
3. **Statuses keep their limits.** A star is a bookmark. “Reviewed” is a stated metadata-and-fit
   check, not a code audit, security approval, adoption claim, or universal rank.
4. **Compression cannot hide evidence.** Overview pages summarize. Entries, sources, canonical
   JSON, and reconsideration triggers remain directly reachable.
5. **Runtime stays AI-free.** Editorial assistance never enters facts, gates, hashes, plans, state
   transitions, or the command runtime.

## Every public surface has a review route

| Surface | Reader's job | Review route |
| --- | --- | --- |
| GitHub description, README, homepage | Decide whether this is relevant and choose a first action | First Reader plus ZeroSlop and Vale |
| Getting started and CLI help | Complete one task without learning the internal architecture | ZeroSlop, command tests, and a clean-environment smoke test |
| Catalog overview, collections, cards, entries | Find by need, understand why an option is present, and judge freshness | First Reader on landing pages; ZeroSlop on owned templates; deterministic generation and sample review |
| Changelog and release notes | Understand what changed, why it matters, and what remains bounded | ZeroSlop, version checks, and release verification |
| Architecture, operations, security, schemas, contribution docs | Find exact contracts without mistaking detail for the opening pitch | ZeroSlop, Vale, link checks, and the relevant technical tests |
| 404 page and site chrome | Recover quickly | Human read-through and site build |

Imported repository descriptions are quoted source data, not prose this project is free to
rewrite. High-volume generated pages are therefore reviewed through the owned generator text,
schema, representative outputs, deterministic diff, and site build—not by “improving” upstream
wording.

## The four passes

### 1. First Reader checks interest and wayfinding

For a material README, homepage, catalog-landing, or command-journey change, a fresh reviewer sees
only the rendered surface. The reviewer reports:

- what the project is for;
- who it appears to serve;
- where they would go next;
- the first sentence or section that makes them hesitate or leave; and
- what they remember after the text is hidden.

This follows the First Reader skill pinned in the public-writing receipt. Reader reactions are
diagnostic evidence, not user research or an automatic gate. The author answers friction with the
smallest truthful structural or wording change.

### 2. ZeroSlop checks the editorial texture

ZeroSlop's local scorer runs in formal mode over hand-authored Markdown and captured CLI help. Its
performed-register, copy-desk, read-aloud, and fresh-eyes passes then check problems the meter
cannot see: overly even explanation, repetitive section shapes, delayed payoff, and prose written
for the review process instead of the reader.

The score is a lexical-and-structural writing diagnostic. It is not an authorship probability,
quality grade, or CI threshold. A low score does not waive the human passes. No public draft is
sent to ZeroSlop's hosted rewrite service.

### 3. Deterministic checks protect the text around the prose

`./scripts/review_public_writing.sh` runs Vale 3.21.0 on
every hand-authored public Markdown file and on the generated catalog landing pages whose wording
the project owns. The full gate also checks spelling, links, generated drift, CLI behavior, and the
strict static site.

Vale flags a small set of observed, repeatable problems. It does not score authorship, rewrite
copy, or inspect hundreds of imported descriptions as if they were this project's voice.

### 4. A human confirms fidelity

The final reviewer compares changed claims with their source, keeps every qualifier at the same
strength, removes process narration that does not help the reader, and reads the rendered surface
from top to bottom. This pass owns the final wording.

## Evidence and maintenance

The [v0.3.0 public-surface review](../development/public-surface-review-v0.3.0.md) records the
executed First Reader and ZeroSlop passes, changes they caused, and remaining caveats. The immutable
[v0.3 public-writing decision receipt](../decisions/public-writing-v0.3.json) supersedes the
original receipt and records why these tools are editorial aids rather than dependencies or
authorities.

Rerun the review when a first-contact page changes purpose, a new public surface appears, or a
generated template changes how readers interpret a status. Do not rerun it merely to optimize a
number.
