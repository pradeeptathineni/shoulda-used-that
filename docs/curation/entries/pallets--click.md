---
title: "pallets/click"
description: "Composable Python package for creating command-line interfaces."
tags:
  - "OSS Curation \u0026 Prior Art"
  - "Platform Engineering \u0026 Delivery"
  - "Python Engineering"
---
# pallets/click



<p class="collection-deck">Composable Python package for creating command-line interfaces.</p>

[Open repository](https://github.com/pallets/click){ .md-button .md-button--primary }

Checked 2026\-09\-17 · [Evidence](#evidence)

**Domains:** <a href="../collections/oss-curation-foundations.md">OSS Curation &amp; Prior Art</a>, <a href="../collections/platform-engineering-delivery.md">Platform Engineering &amp; Delivery</a>, <a href="../collections/python-engineering.md">Python Engineering</a>

## Contextual assessments

### A mature direct command and option boundary without a custom parser\.

**Decision in this context:** Used here<br>
**Assessment basis:** documented\-use<br>
**Assessed:** `2026-09-17T12:00:00+00:00`

#### Covers

- Click owns parsing and help while typed domain validation stays in ShouldaUsedThat\.

#### Watch

- No watch item recorded.

#### Unknowns

- No unresolved question recorded.

#### Assessment evidence

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>
- <a href="../../decisions/dependencies.json">docs/decisions/dependencies.json</a>

#### Reconsider when

- The selected major version becomes incompatible or an already\-used component fully owns parsing\.

## Evidence

### Observed repository facts

- **License:** BSD-3-Clause
- **Archived:** false
- **Latest release:** 8\.5\.0
- **Latest commit:** <code>not recorded</code>
- **Popularity:** No public star count is claimed by this snapshot.
- **Last checked:** `2026-09-17T12:00:00+00:00`

### Screening evidence

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>
- <a href="../../decisions/dependencies.json">docs/decisions/dependencies.json</a>

### Source provenance

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a> — observed `2026-09-17T12:00:00+00:00`

## Attribution

No additional catalog obligation recorded\.
