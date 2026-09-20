---
title: ShouldaUsedThat
description: See what to reuse, what to skip, and what is genuinely left to build.
hide:
  - toc
---

<div class="catalog-hero" markdown>

<p class="catalog-kicker">Open-source build decisions</p>

# Reuse what fits. Build only what is missing.

Before you spend days implementing a software idea, see the established projects that already own
parts of it, the limits that matter, and the exact custom work still worth doing.

<div class="home-actions" markdown>

[See 5 reviewed decisions](curation/index.md){ .md-button .md-button--primary }
[Run your own evidence check](getting-started.md){ .md-button }

</div>

</div>

<div class="catalog-grid">
<article class="catalog-card home-value-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>Reuse proven parts</h2>
  <p>See which project owns each capability and why it fits this specific problem.</p>
</article>
<article class="catalog-card home-value-card">
  <p class="decision-chip decision-chip--reject">Skip or watch</p>
  <h2>Avoid the wrong fit</h2>
  <p>See the boundary, risk, or missing evidence before adding another dependency.</p>
</article>
<article class="catalog-card home-value-card">
  <p class="decision-chip decision-chip--build">Build</p>
  <h2>Keep the justified gap</h2>
  <p>Separate solved infrastructure from the product-specific work that remains yours.</p>
</article>
</div>

## A real answer, not a repository list

**Problem:** run a reproducible quality gate for a typed Python CLI.

<div class="decision-summary">
  <p><strong>Use:</strong> <code>uv</code> for the locked environment and builds, <code>pytest</code> for behavior, and CodeQL for hosted source analysis.</p>
  <p><strong>Do not expect:</strong> any one of them to define the whole quality policy.</p>
  <p><strong>You still own:</strong> supported versions, typed postconditions, coverage targets, and gate ordering.</p>
  <p><strong>Bottom line:</strong> compose three mature tools; build only the repository-specific policy around them.</p>
</div>

[Open the decision and its evidence](curation/briefs/reproducible-python-quality-gate.md)

## What you can do today

- Browse five reviewed build decisions with explicit **use**, **try**, **study**, **watch**, **skip**,
  and **build** actions.
- Run a deterministic CLI check against exact repositories, GitHub searches, Stars, or public
  fixtures, then record and recheck your decision.
- Inspect dated evidence and reconsideration triggers instead of trusting an unexplained score.

!!! note "Current boundary"

    This is not a prompt box that searches the whole internet. The public decisions are a small,
    reviewed demonstration. The CLI executes the sources, queries, filters, and ordering you name;
    it never silently invents a research plan.
