---
title: ShouldaUsedThat
description: Find and vet existing open source before building from scratch.
hide:
  - toc
---

# Check before you build

Start with the need, not a blank file. ShouldaUsedThat helps you find existing open-source options,
inspect why they may fit, and keep the evidence that could change the decision later.

<div class="home-actions" markdown>

[Find existing OSS](curation/index.md){ .md-button .md-button--primary }
[See the product use itself](curation/dogfood.md){ .md-button }
[Understand the safety boundary](architecture/implementation-brief.md){ .md-button }

</div>

## What you can learn here

- **What already exists** for a concrete engineering or personal-interest area.
- **How each option is being treated:** used, trialing, reference, learning, watch, or rejected.
- **Why the choice may fit**, what evidence supports it, and what would trigger another look.
- **Which tools this repository actually uses** instead of quietly rebuilding their jobs.

## The repository uses the same process

The repository generates this site and its own GitHub Lists from the same reviewed public profile.
Every GitHub change goes through an exact additive plan and an independent readback. The
[dogfood page](curation/dogfood.md) shows the command-level chain. The
[live evidence](operations/live-projection.md) says what was actually verified without publishing
private account state.

The catalog comes from an explicitly public profile. A star is a bookmark, not adoption evidence.
“Reviewed” means the stated metadata and fit checks passed; it does not claim a code or security
audit. Canonical JSON and immutable receipts remain authoritative beneath the website.

Operators can use the [GitHub curation runbook](operations/github-curation.md) for exact approval
and readback boundaries, or the [read-only scheduling guide](operations/scheduling.md) for safe
local and repository upkeep.
