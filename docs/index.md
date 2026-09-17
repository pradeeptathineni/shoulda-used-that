---
title: ShouldaUsedThat
description: Find existing open source before building from scratch, then keep the evidence behind the choice.
hide:
  - toc
---

# Check before you build

Start with the need, not a blank file. ShouldaUsedThat helps you find existing open-source options,
see why they may fit, and keep the evidence that could change the decision later.

<div class="home-actions" markdown>

[Browse by need](curation/index.md){ .md-button .md-button--primary }
[Try the CLI](getting-started.md){ .md-button }
[See the project use itself](curation/dogfood.md){ .md-button }

</div>

## A useful entry answers four questions

1. **What need does this serve?** The catalog is organized around jobs, not a generic popularity
   contest.
2. **Why is it here?** Each entry states the contextual rationale and decision status.
3. **How fresh is the evidence?** Observed facts are dated instead of presented as permanent.
4. **What would change the decision?** Every reviewed choice carries a reconsideration trigger.

Open the [catalog overview](curation/index.md) to choose a collection, or search for a repository,
technology, or need. Start with [what this project actually uses](curation/in-use.md) if you want a
concrete example of decisions backed by repository evidence.

## The short version of the workflow

```text
find options → keep the exact result → record the choice → revisit when evidence changes
  checked           saved               remembered              rechecked
```

The local workflow is deterministic and keeps its state outside the repository. A planning-only
`used` record can describe an adoption without editing the target. The [getting-started guide](getting-started.md)
walks through each step with a public fixture and no GitHub login.

## Claims stay bounded

A star is a bookmark. “Reviewed” means the stated metadata and fit checks passed or a visible,
narrow exception was recorded; it does not mean code audit, security approval, adoption, or a
universal rank. Canonical JSON and immutable receipts sit beneath the readable pages.

ShouldaUsedThat builds this site and its public GitHub Lists from the same profile. The
[self-use story](curation/dogfood.md) explains the result in plain language. Exact approval and
readback controls live in the [operator runbook](operations/github-curation.md), where readers who
need that depth can find them without carrying the machinery through the first visit.
