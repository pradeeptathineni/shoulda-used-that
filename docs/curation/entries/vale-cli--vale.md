---
title: "vale-cli/vale"
description: "Markup-aware prose linter with project-owned styles and offline execution."
tags:
  - "Used here"
  - "OSS Curation \u0026 Prior Art"
---
# vale\-cli/vale

<div class="entry-heading">
  <span class="status-chip status-chip--adopt">Used here</span>
  <span class="freshness-chip freshness-chip--current">current</span>
</div>

<p class="collection-deck">Markup-aware prose linter with project-owned styles and offline execution.</p>

[Open repository](https://github.com/vale-cli/vale){ .md-button .md-button--primary }

## Contextual decision

**Meaning:** Confirmed by repository evidence for the named role\.<br>
**Role:** deterministic public\-writing lint<br>
**Need:** Catch repeated hype and filler in the most visible public entrypoints without building a prose engine or making a model authoritative\.<br>
**Why:** Vale owns repeatable offline prose checks; a context\-free first reader and human fidelity review retain the judgment roles it cannot supply\.<br>
**Collections:** <a href="../collections/oss-curation-foundations.md">OSS Curation &amp; Prior Art</a>

## Observed facts

- **License:** MIT
- **Archived:** false
- **Latest release:** v3\.21\.0
- **Latest commit:** <code>ed7117697bd9e8e0f8cd6b6217125878321ef17b</code>
- **Popularity:** 6,108 stars observed at `2026-09-17T16:00:00+00:00`
- **Last checked:** `2026-09-17T16:00:00+00:00`

## Evidence

- <a href="https://github.com/pradeeptathineni/shoulda-used-that/blob/main/.github/workflows/security.yml">.github/workflows/security.yml</a>
- <a href="../../decisions/public-writing.json">docs/decisions/public-writing.json</a>

### Source provenance

- <a href="https://github.com/vale-cli/vale/releases/tag/v3.21.0">https://github.com/vale-cli/vale/releases/tag/v3.21.0</a> — observed `2026-09-17T16:00:00+00:00`

## Reconsider when

The pinned version cannot lint the selected sources deterministically, or the project\-owned rules create repeated false positives\.

## Attribution

No additional catalog obligation recorded\.
