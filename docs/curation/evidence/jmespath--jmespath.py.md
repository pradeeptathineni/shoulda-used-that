---
title: "Evidence for jmespath/jmespath.py"
description: "Problem-relative assessment and observed repository facts for jmespath/jmespath.py."
tags:
  - "oss-curation-foundations"
  - "python-engineering"
search:
  exclude: true
---
# Evidence for jmespath/jmespath\.py

Python implementation of the JMESPath query language for JSON documents\.

[Open repository](https://github.com/jmespath/jmespath.py){ .md-button .md-button--primary }

<a id="deterministic-python-research-core"></a>
## Build a deterministic Python research core

**Problem:** Build a deterministic local Python research core without inventing command parsing, validation, safe querying, or canonical JSON\.

### Covers

- Evaluates safe local expressions over one documented candidate view without arbitrary Python execution\.

### Watch

- It is only the advanced filter evaluator; native gates and the exposed query view remain project\-owned\.

### Unknowns

- No additional unknown recorded.

### Assessment evidence

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>

Assessed 2026\-09\-17 ·
[Return to brief](../briefs/deterministic-python-research-core.md)


<details>
<summary>Observed repository and provenance details</summary>

- **License:** MIT
- **Archived:** false
- **Latest release:** 1\.1\.0
- **Latest commit:** `6ff419a8b171d055a9bfc6904605bceb8b7a80ef`
- **Last checked:** `2026-09-17T12:00:00+00:00`

### Screening evidence

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>

### Source provenance

- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a> — observed `2026-09-17T12:00:00+00:00`

</details>
