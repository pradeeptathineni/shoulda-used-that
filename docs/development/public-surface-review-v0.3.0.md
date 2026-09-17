---
title: v0.3.0 public-surface review
description: Executed First Reader and ZeroSlop evidence for the reader-first release.
---

# v0.3.0 public-surface review

This review asked whether a newcomer can understand the project, choose a useful first action, and
complete that action before meeting the operator machinery. It covered the GitHub and package
description, README, documentation homepage, getting-started guide, CLI help and table output,
catalog frames and representative generated pages, changelog, release notes, security and
contribution guidance, architecture and operations documents, schema guidance, navigation, and
the 404 recovery page.

Structured JSON, action YAML, and imported repository descriptions were checked for correctness in
their native validation paths. They were not treated as prose to rewrite.

## First Reader changed the order, not the claims

The review used the First Reader skill from
[`Shubhamsaboo/awesome-llm-apps`](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/f163bb5a92111cee4610ac98e5dce4c6a2a09c26/agent_skills/first-reader)
at commit `f163bb5a92111cee4610ac98e5dce4c6a2a09c26`. Fresh roles saw the README
without author intent, prior scores, or a proposed rewrite.

The baseline opening survived: readers accurately recalled “check before you build” and trusted
the explicit deterministic-AI boundary. The failure was structural. One skeptical reader left to
browse the catalog before finding a runnable path. A sympathetic reader left when the README began
to feel written for auditors. The verified-release installation path was not findable.

That evidence led to four changes:

1. The README now offers three immediate choices: browse, run a no-authentication check, or install
   the verified wheel.
2. The fixture check and its outcome appear before receipt internals.
3. The five everyday commands form one question-to-decision journey; catalog projection remains a
   separate operator journey.
4. Catalog entries lead with need, rationale, status meaning, and reconsideration before observed
   facts and provenance.

A second fresh read found all three README routes and the full documentation journey without a
broken trail. Both readers completed the fixture sequence, understood where its check ID came
from, and correctly identified `apply` as the only command shown that can change GitHub. One
skeptical reader challenged the phrase “two-minute fixture check” because a fresh clone and
dependency sync can take longer; the final README calls it a local fixture check without promising
a duration.

## ZeroSlop covered the authored surface

The local review used [ZeroSlop 2.12.1](https://github.com/manavmishra/ZeroSlop/tree/v2.12.1),
tag commit `98e34b5cddbafdb25bff385d046fe0cef4d05fad`. Its formal-prose scorer ran over
every hand-authored public Markdown file, the project-owned generated frames, root CLI help,
`checked --help`, and a rendered fixture result. Codex performed the contextual editing; ZeroSlop's
local tools supplied the repeatable checks. Document-level voice, copy-desk, read-aloud,
fact-preservation, and fresh-eyes passes followed. No hosted rewrite endpoint received repository
prose.

The finished hand-authored Markdown scored from 9.5 to 14.0 on the local writing diagnostic. Root
and `checked` help each scored 11.4; the rendered fixture result scored 9.5. These numbers locate
lexical and structural patterns. They are not authorship probabilities, quality grades, or release
thresholds.

Generated grids produced much higher whole-file numbers—28.0 for the catalog overview, 32.1 for
the in-use page, 88.0 for the entry index, and 97.1 for considered choices—because hundreds of
cards repeat labels and retain upstream descriptions. Rewriting those descriptions to lower a
score would corrupt source evidence. The review instead changed the owned templates, inspected
representative entry and collection pages, regenerated all outputs, and checked the deterministic
diff and strict site build.

## Surface-by-surface outcome

| Surface | Reader-facing change or verified condition |
| --- | --- |
| Repository and package metadata | States the find, record, and revisit outcome without opening on GitHub mechanics |
| README | Browse, try, and install are visible before status or architecture detail |
| Homepage | Explains the four questions a useful entry answers and links directly to a need-based browse path |
| Getting started | Runs on a public fixture without authentication and explains what each receipt enables next |
| CLI help | Commands answer human questions; every option names its input or boundary |
| Terminal tables | Uses readable labels and explicit “GitHub changed: no” or “Target changed: no” boundaries instead of field-name dumps |
| Catalog | Overview teaches the status vocabulary; collections state when to use them; entries put decision context first |
| Trust and maintenance docs | Security, release, schema, contribution, architecture, and operations pages retain exact boundaries and gain direct reader routes |
| Generated corpus | Upstream prose remains unchanged; project-owned framing is reviewed through the generator and representative output |
| Site recovery | The 404 page routes readers to the current catalog or homepage |

## Fidelity and limits

No decision status, repository fact, count, timestamp, license, fingerprint, safety qualifier, or
mutation boundary was supplied by either review technique. The rewrite preserved the distinction
between a bookmark, a metadata-and-fit review, an adoption, and a security audit. It also kept
canonical JSON authoritative and the product runtime AI-free.

First Reader responses are simulated first-impression evidence, not measured user behavior.
ZeroSlop cannot judge whether a claim is true or whether a repeated card layout is appropriate.
The final approval therefore depends on repository validation, rendered-site inspection, hosted
pull-request checks, and human comparison of changed claims with their sources.
