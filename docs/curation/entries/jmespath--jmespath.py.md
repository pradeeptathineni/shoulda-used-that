---
title: "jmespath/jmespath.py"
description: "Python implementation of the JMESPath query language for JSON documents."
tags:
  - "Used here"
  - "OSS Curation Foundations"
  - "Python Engineering"
---
# jmespath/jmespath\.py

<div class="entry-heading">
  <span class="status-chip status-chip--adopt">Used here</span>
  <span class="freshness-chip freshness-chip--current">current</span>
</div>

<p class="collection-deck">Python implementation of the JMESPath query language for JSON documents.</p>

[Open repository](https://github.com/jmespath/jmespath.py){ .md-button .md-button--primary }

## Contextual decision

**Meaning:** Confirmed by repository evidence for the named role\.<br>
**Role:** runtime advanced filter language<br>
**Need:** Safe local expressions over a documented candidate view\.<br>
**Why:** JMESPath avoids a custom DSL or arbitrary Python evaluation\.<br>
**Collections:** <a href="../collections/oss-curation-foundations.md">OSS Curation Foundations</a>, <a href="../collections/python-engineering.md">Python Engineering</a>

## Observed facts

- **License:** MIT
- **Archived:** false
- **Latest release:** 1\.1\.0
- **Latest commit:** <code>6ff419a8b171d055a9bfc6904605bceb8b7a80ef</code>
- **Popularity:** No public star count is claimed by this snapshot.
- **Last checked:** `2026-09-17T12:00:00+00:00`

## Evidence

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>

### Source provenance

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a> — observed `2026-09-17T12:00:00+00:00`

## Reconsider when

A required real\-world filter cannot be expressed safely\.

## Attribution

No additional catalog obligation recorded\.
