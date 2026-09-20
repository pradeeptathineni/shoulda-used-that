---
title: "Reviewed build decisions"
description: "Concrete software problems with what to use, try, learn from, study, watch, skip, and still build."
tags:
  - "prior art"
  - "software architecture"
---
# Reviewed build decisions

Choose the problem closest to yours. Each decision says what to use, try, learn from, study, watch,
skip, or build—then shows why and names the custom work that remains. Every action is specific to
the stated problem; none is a universal ranking.

<div class="catalog-grid">
<article class="catalog-card brief-card">
  <h2><a href="briefs/reproducible-python-quality-gate.md">Run a reproducible Python quality gate</a></h2>
  <p>Run a reproducible quality gate for a typed Python CLI across environments, behavior, and hosted source analysis.</p>
  <p class="catalog-card__decision"><strong>Decision:</strong> Use astral-sh/uv, pytest-dev/pytest, and github/codeql-action.</p>
  <p><strong>Still yours:</strong> The repository must still define its supported versions, typed postconditions, coverage target, and complete gate ordering.</p>
  <p class="catalog-card__evidence">3 assessed options · Checked 2026-09-17 · <a href="briefs/reproducible-python-quality-gate.md">Open decision</a></p>
</article>
<article class="catalog-card brief-card">
  <h2><a href="briefs/static-technical-docs-review.md">Publish and review static technical documentation</a></h2>
  <p>Publish searchable static technical documentation and review its prose without making an editorial model authoritative.</p>
  <p class="catalog-card__decision"><strong>Decision:</strong> Use vale-cli/vale; Try zensical/zensical; Learn from addyosmani/agent-skills; Study shubhamsaboo/awesome-llm-apps.</p>
  <p><strong>Still yours:</strong> Human review must still decide whether claims are true, concise, useful, and supported by repository evidence.</p>
  <p class="catalog-card__evidence">4 assessed options · Checked 2026-09-17 · <a href="briefs/static-technical-docs-review.md">Open decision</a></p>
</article>
<article class="catalog-card brief-card">
  <h2><a href="briefs/deterministic-python-research-core.md">Build a deterministic Python research core</a></h2>
  <p>Build a deterministic local Python research core without inventing command parsing, validation, safe querying, or canonical JSON.</p>
  <p class="catalog-card__decision"><strong>Decision:</strong> Use pallets/click, pydantic/pydantic, jmespath/jmespath.py, and trailofbits/rfc8785.py.</p>
  <p><strong>Still yours:</strong> The product-specific research plan, evidence gates, state transitions, and human answer still need a local coordinator.</p>
  <p class="catalog-card__evidence">4 assessed options · Checked 2026-09-17 · <a href="briefs/deterministic-python-research-core.md">Open decision</a></p>
</article>
<article class="catalog-card brief-card">
  <h2><a href="briefs/curated-oss-evidence-publishing.md">Publish a curated OSS evidence set</a></h2>
  <p>Seed and publish a curated OSS evidence set without confusing popularity or catalog presence with contextual fit.</p>
  <p class="catalog-card__decision"><strong>Decision:</strong> Learn from best-of-lists/best-of; Watch ejacobhayes/parsecio; Skip best-of-lists/best-of-generator.</p>
  <p><strong>Still yours:</strong> Catalog presence and popularity still do not establish problem-specific fit.</p>
  <p class="catalog-card__evidence">3 assessed options · Checked 2026-09-17 · <a href="briefs/curated-oss-evidence-publishing.md">Open decision</a></p>
</article>
<article class="catalog-card brief-card">
  <h2><a href="briefs/local-first-prior-art-coordination.md">Keep prior-art coordination local-first</a></h2>
  <p>Coordinate prior-art research locally without making a hosted backend or personal GitHub mutation the product core.</p>
  <p class="catalog-card__decision"><strong>Decision:</strong> Learn from amintacccp/githubstarsmanager; Skip boffti/stardash; Build pradeeptathineni/shoulda-used-that.</p>
  <p><strong>Still yours:</strong> General natural-language discovery remains outside the deterministic core.</p>
  <p class="catalog-card__evidence">3 assessed options · Checked 2026-09-17 · <a href="briefs/local-first-prior-art-coordination.md">Open decision</a></p>
</article>
</div>

## Evidence boundary

These 5 decisions use explicit problem-by-repository assessments. The complete safe corpus
of 222 screened repositories remains available in [machine-readable JSON](catalog.json),
but screened metadata never becomes contextual fit copy or a rich reader page.

Checked 2026-09-17T16:00 UTC · [Sources and attribution](sources.md) ·
[Reproducibility manifest](manifest.json)
