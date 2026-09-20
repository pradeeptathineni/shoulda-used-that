---
title: ShouldaUsedThat
description: See the prior-art landscape for one concrete software build problem before writing another implementation.
hide:
  - toc
---

# Know the landscape before you build

ShouldaUsedThat turns one concrete software build problem into a short, evidence-backed brief:
the few existing approaches worth knowing, what each covers, where it stops, and what still appears
worth building.

<div class="home-actions" markdown>

[Explore prior-art briefs](curation/index.md){ .md-button .md-button--primary }
[Use the research CLI](getting-started.md){ .md-button }

</div>

## Example: build a deterministic Python research core

Four established pieces already cover much of the foundation:

- **Click** — mature parsing and help; it does not define research semantics.
- **Pydantic** — strict versioned records; workflow rules remain explicit.
- **JMESPath** — safe expressions over a documented view; native gates stay project-owned.
- **rfc8785.py** — canonical JSON bytes; receipt and state policy remain separate.

**What appears covered:** parsing, validation, safe local querying, and stable content identity.

**What remains:** the problem-specific research plan, evidence gates, state transitions, and compact
human answer.

[Open the full brief](curation/briefs/deterministic-python-research-core.md)

## How trust stays out of the way

Every visible claim links to dated evidence. The complete screened corpus, provenance, and canonical
JSON remain available underneath, but metadata never becomes contextual fit and screened-only
candidates do not receive rich pages.

The CLI executes only explicit sources, queries, filters, and ordering. It records the complete
result while keeping normal output to five candidates. Read, research, and record commands do not
mutate GitHub or a target repository.
