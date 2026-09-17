---
title: "pallets/click"
description: "Composable Python package for creating command-line interfaces."
tags:
  - "Used here"
  - "OSS Curation Foundations"
  - "Platform Engineering \u0026 Delivery"
  - "Python Engineering"
---
# pallets/click

<div class="entry-heading">
  <span class="status-chip status-chip--adopt">Used here</span>
  <span class="freshness-chip freshness-chip--current">current</span>
</div>

<p class="collection-deck">Composable Python package for creating command-line interfaces.</p>

[Open repository](https://github.com/pallets/click){ .md-button .md-button--primary }

## Contextual decision

**Meaning:** Confirmed by repository evidence for the named role\.<br>
**Role:** runtime CLI parser<br>
**Need:** A mature direct command and option boundary without a custom parser\.<br>
**Why:** Click owns parsing and help while typed domain validation stays in ShouldaUsedThat\.<br>
**Collections:** <a href="../collections/oss-curation-foundations.md">OSS Curation Foundations</a>, <a href="../collections/platform-engineering-delivery.md">Platform Engineering &amp; Delivery</a>, <a href="../collections/python-engineering.md">Python Engineering</a>

## Observed facts

- **License:** BSD-3-Clause
- **Archived:** false
- **Latest release:** 8\.5\.0
- **Latest commit:** <code>not recorded</code>
- **Popularity:** No public star count is claimed by this snapshot.
- **Last checked:** `2026-09-17T12:00:00+00:00`

## Evidence

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>
- <a href="../../decisions/dependencies.json">docs/decisions/dependencies.json</a>

### Source provenance

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a> — observed `2026-09-17T12:00:00+00:00`

## Reconsider when

The selected major version becomes incompatible or an already\-used component fully owns parsing\.

## Attribution

No additional catalog obligation recorded\.
