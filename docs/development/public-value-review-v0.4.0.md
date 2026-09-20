---
title: v0.4.0 public-value review
description: First-screen and decision-page evidence for the decision-first public correction.
---

# v0.4.0 public-value review

This review asks a stricter first-contact question than the v0.3 review: **does the public surface
show a useful decision immediately, or merely describe a research mechanism?** It covers the
rendered homepage, decision overview, one decision with only adopt actions, one mixed decision,
search behavior, mobile layout, CLI route, and the evidence boundary.

## Baseline defect

The production page at commit `0c85038f4fc8a2104fc4ffbb26a6ee9929521dd2` accurately described
an evidence-backed brief, but the first screen still delayed the payoff:

- “prior art” and “landscape” named the mechanism rather than the decision changed for the reader;
- the worked example concerned the product's own deterministic research core;
- the homepage described what tools cover but did not show the stored adopt decision;
- overview cards showed an option count but hid use, trial, reference, watch, reject, and build;
- reconsideration triggers existed in canonical assessment data but were absent from brief cards.

The result looked like documentation about a repository-research system. The underlying data
contained a stronger product answer than the public rendering exposed.

## Correction

Version 0.4.0 uses the existing authoritative assessment fields rather than inventing a new score
or recommendation layer:

1. The first screen leads with “reuse what fits; build only what is missing.”
2. A familiar Python quality-gate example gives a complete use/custom-scope answer in one view.
3. The decision overview states the contextual action and remaining custom work on every card.
4. Every candidate card shows its action, contribution, caution, and reconsideration trigger.
5. The homepage states that the current product is not a prompt-driven internet search service.

The labels are a rendering of existing problem-specific state: `adopt` becomes “Use,” `trial`
becomes “Try,” `reference` becomes “Learn from,” `learn` becomes “Study,” `watch` remains “Watch,”
`reject` becomes “Skip,” and `build` remains “Build.” No action is inferred from popularity,
screening, or repository metadata.

## Evidence boundary

The correction does not change candidate facts, assessments, hashes, state transitions, or runtime
behavior. Canonical JSON remains authoritative. Screened-only repositories still receive no rich
page, and every visible action remains confined to one named problem with dated evidence one click
deeper.

## Correctness, security, and deletion review

The release diff was reviewed for claim drift, unsafe rendering, privacy leakage, new network or
mutation paths, and changes to the sealed GitHub boundary. The renderer consumes only allowlisted
public assessment and brief fields. Every field placed inside raw HTML is HTML-escaped; regression
coverage now injects active markup into descriptions, residual scope, and reconsideration triggers
and proves that the overview, brief, and evidence pages render it inert. No GitHub adapter, mutation
executor, target-write route, credential path, dependency, or runtime model changed.

The pinned `ponytail-review` pass found one redundant label-and-verb tuple in the new renderer; it
was collapsed to one ordered action map. The corresponding whole-repository `ponytail-audit` found
no further deletion or dependency cut that preserves the documented contracts. The existing small
protocols have live production and test implementations, and each runtime dependency retains one
distinct recorded role. The upstream one-smoke-test minimum was not applied because this project's
stronger safety and replay gates remain required.

## Verification

- `uv run pytest tests/test_public_export.py tests/test_repository_contracts.py`: 35 tests passed,
  including decision ordering, action labels, reconsideration triggers, information budgets, and
  active-markup escaping on every changed renderer level.
- `uv run coverage run -m pytest && uv run coverage report`: 259 tests passed with 90% branch-aware
  coverage.
- The complete `./scripts/check.sh` gate passed with a checksum-verified Vale 3.21.0 binary supplied
  through its documented `VALE_BIN` override. Lock and environment checks, Ruff, strict mypy,
  generated schemas, repository and privacy contracts, deterministic catalog replay, strict site
  build, Vale, actionlint, zizmor, typos, links, branch-aware coverage, and isolated package builds
  all passed. Vale reported zero alerts, zizmor reported no findings, and the link check reported
  240 reachable links, four intentional exclusions, and zero errors.
- Deterministic generation produced public export `pcx_98b0287ccd3f16d2e6fa6acf`; the strict site
  contains 49 pages, passes six search cases, and loads no third-party runtime resource.
- Desktop and 390-by-844 rendered review covered the homepage, decision overview, all-use quality
  gate, and mixed learn/watch/skip decision. It found and resolved one leaked Markdown-escape
  sequence; the final narrow layouts had no observed overflow or hidden primary action.
