---
title: ShouldaUsedThat
description: Build an evidence-backed prior-art brief for a concrete software problem before writing another implementation.
hide:
  - toc
---

# Know the landscape before you build

Suppose you need stable JSON identity, safe local querying, or a mature CLI boundary. The useful
answer is not a wall of repositories. It is a short, evidence-backed view of the credible options:
what each covers, what to watch, what is still unknown, and which part may genuinely remain yours.

ShouldaUsedThat is built around that prior-art brief. The current public Explore surface exposes
the screened evidence corpus and explicit assessments used to prove the underlying model; it does
not pretend every screened candidate has been assessed for your problem.

<div class="home-actions" markdown>

[Explore the evidence](curation/index.md){ .md-button .md-button--primary }
[Try the deterministic CLI](getting-started.md){ .md-button }

</div>

## What the evidence means

- **Screened**: public source, metadata, and eligibility evidence made a candidate worth retaining.
- **Assessed**: reviewed evidence supports contextual covers, watch, or unknown content for one
  concrete problem.

The same repository may deserve different assessments for different problems. Domains help filter
the backing corpus; they are not needs or recommendations.

## A local, revisitable workflow

```text
find options → keep the exact result → record the choice → revisit material change
  checked           saved               remembered              rechecked
```

The CLI is deterministic and keeps state outside the target repository. Read and record commands
do not mutate GitHub or a target project. Start with the [guided CLI journey](getting-started.md),
or see the durable [product and evidence boundary](architecture/product-contract.md).

## Evidence stays available

Reader pages hide routine machinery, but the safe public corpus, dated observations, provenance,
schemas, decision evidence, and reproducibility manifest remain inspectable. Operator controls and
live readback evidence are available through the [runbook](operations/github-curation.md) without
competing for first-visit navigation.
