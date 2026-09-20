---
title: Product contract
description: The durable boundary for an evidence-backed prior-art brief before implementation.
---

# Product contract

## Product definition

ShouldaUsedThat produces an evidence-backed build decision for a concrete software problem. The
underlying artifact is a prior-art brief, but the reader-facing answer says what to use, try, learn
from, study, watch, skip, or build before the reader commits implementation time.

The target user is a software builder about to commit design or implementation time. Their primary
job is: **understand what already covers this problem, what deserves caution, and what remains
unresolved before choosing a path.**

## Core loop

```text
state a concrete problem
  → find and screen plausible candidates
  → assess candidates in that exact context
  → synthesize a small prior-art brief
  → choose, record, and revisit when material evidence changes
```

The primary human unit is the **decision brief**, not a repository page. A useful brief normally
contains three to five options, a problem-specific action for each, what each covers, important
watch items, explicit unknowns, the landscape already covered, and the justified custom scope.

## Evidence and model boundaries

Reusable repository observations—identity, description, license, archive state, release or commit
observations, maintenance or popularity signals, provenance, and dates—belong to repository
evidence. Domains organize that evidence as taxonomy.

Contextual judgment belongs only to a concrete `problem × repository` assessment. **Screened**
means metadata or eligibility evidence justified retaining a candidate. **Assessed** means enough
contextual evidence and reviewed reasoning exists to publish covers, watch, or unknown content for
one problem. Screening cannot promote itself to assessment.

The deterministic host owns sources, gates, canonical JSON, hashes, state transitions, publication
state, and validation. A model may later help explain or synthesize bounded, cited assessment
inputs; it must not invent facts, decisions, evidence, gates, or identity.

## Information budget

- Keep primary navigation to at most four reader concepts: Home, Decisions, CLI, and How it works.
- Lead with the problem and decision effect; reveal implementation and operational evidence later.
- Translate contextual decision state into direct action words: use, try, learn from, study, watch,
  skip, or build. Never present that action outside its named problem.
- Show routine trust evidence compactly as `Checked <date> · Evidence`.
- Do not repeat default state, aliases, fingerprints, full hashes, projection terminology, or receipt
  identifiers unless the reader explicitly opens evidence or operator detail.
- Preserve complete safe evidence underneath the smaller reader-facing projection.
- Add a user-facing field only when it changes the reader's next decision.

## Non-goals

This cycle does not provide general natural-language discovery, autonomous research, scoring or
universal rankings, AI-authored facts or decisions, target-repository mutation, or a renamed CLI.
A broad screened corpus is backing evidence and dogfood data; it is not the finished product.

## Implementation sequence

1. **Foundation and model:** separate reusable evidence, screening, concrete problems, and
   problem-by-repository assessments; migrate safely; reduce the public surface.
2. **Brief product:** publish a small set of evidence-backed briefs and make the reader-facing
   projection brief-first while retaining the full safe corpus underneath.
3. **CLI and operational boundary:** align the human workflow with briefs and keep maintenance,
   projection, and mutation controls in an explicit operator surface.

Detailed safety and compatibility contracts remain available in the
[implementation contract](implementation-brief.md), [curation coordinator contract](curation-v0.2.md),
[operator runbook](../operations/github-curation.md), and [decision evidence](../decisions/README.md).
