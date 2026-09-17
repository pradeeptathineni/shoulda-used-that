---
title: "OSS Curation Foundations"
description: "Native surfaces, catalogs, decision records, and presentation tools considered for evidence-backed OSS curation."
tags:
  - "OSS Curation Foundations"
  - "GitHub stars"
  - "open source curation"
  - "prior art"
---
# OSS Curation Foundations

<p class="collection-deck">Native surfaces, catalogs, decision records, and presentation tools considered for evidence-backed OSS curation.</p>

**Aliases:** GitHub stars, open source curation, prior art<br>
**GitHub List eligibility:** site only<br>
**Review cadence:** 60 days

## Meaning

The product\-specific collection showing the components and prior art behind ShouldaUsedThat\.

- **Include:** Include a reviewed repository when it is used by, evaluated for, or materially informs ShouldaUsedThat&#x27;s curation workflow\.
- **Exclude:** Exclude unreviewed discovery results and components without a documented decision effect\.

## Reviewed entries

<div class="catalog-grid">
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/addyosmani--agent-skills.md">addyosmani/agent-skills</a></h3>
  <p>Open development guidance and reusable skills for agent-assisted engineering.</p>
  <p class="catalog-card__role"><strong>Role</strong> pinned development guidance</p>
  <p class="catalog-card__need"><strong>Need</strong> Selective context and source-driven development guidance.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/amintacccp--githubstarsmanager.md">amintacccp/githubstarsmanager</a></h3>
  <p>Desktop application for browsing, searching, and organizing GitHub stars.</p>
  <p class="catalog-card__role"><strong>Role</strong> star-manager UX prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Learn from mature star search and organization without inheriting its runtime boundary.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/best-of-lists--best-of.md">best-of-lists/best-of</a></h3>
  <p>Curated best-of lists backed by structured project metadata.</p>
  <p class="catalog-card__role"><strong>Role</strong> attributed discovery source</p>
  <p class="catalog-card__need"><strong>Need</strong> Human-curated public seeds and refreshed metadata without treating rank as fit.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reject">Rejected / deferred</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/best-of-lists--best-of-generator.md">best-of-lists/best-of-generator</a></h3>
  <p>Generator and updater used by best-of list projects.</p>
  <p class="catalog-card__role"><strong>Role</strong> catalog generator runtime</p>
  <p class="catalog-card__need"><strong>Need</strong> Avoid a generator that can turn enrichment failure into candidate disappearance.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reject">Rejected / deferred</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/boffti--stardash.md">boffti/stardash</a></h3>
  <p>Dashboard for exploring and organizing GitHub stars.</p>
  <p class="catalog-card__role"><strong>Role</strong> hosted star dashboard runtime</p>
  <p class="catalog-card__need"><strong>Need</strong> Keep the local-first curation core free of a hosted backend and analytics surface.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--watch">Watch</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/ejacobhayes--parsecio.md">ejacobhayes/parsecio</a></h3>
  <p>Static dashboard experiment for organizing starred repositories.</p>
  <p class="catalog-card__role"><strong>Role</strong> static zero-dependency catalog prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Watch a lightweight public catalog approach without adopting an immature contract.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/jmespath--jmespath.py.md">jmespath/jmespath.py</a></h3>
  <p>Python implementation of the JMESPath query language for JSON documents.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime advanced filter language</p>
  <p class="catalog-card__need"><strong>Need</strong> Safe local expressions over a documented candidate view.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/pallets--click.md">pallets/click</a></h3>
  <p>Composable Python package for creating command-line interfaces.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime CLI parser</p>
  <p class="catalog-card__need"><strong>Need</strong> A mature direct command and option boundary without a custom parser.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--build">Built here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/pradeeptathineni--shoulda-used-that.md">pradeeptathineni/shoulda-used-that</a></h3>
  <p>Evidence-bound coordinator for discovering, evaluating, and revisiting OSS choices.</p>
  <p class="catalog-card__role"><strong>Role</strong> deterministic evidence and curation coordinator</p>
  <p class="catalog-card__need"><strong>Need</strong> Own the residual project plus need plus evidence plus decision plus freshness relationship.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/pydantic--pydantic.md">pydantic/pydantic</a></h3>
  <p>Data validation and settings management using Python type annotations.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime typed contracts</p>
  <p class="catalog-card__need"><strong>Need</strong> Strict versioned records and generated JSON Schema.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/trailofbits--rfc8785.py.md">trailofbits/rfc8785.py</a></h3>
  <p>Python implementation of the RFC 8785 JSON Canonicalization Scheme.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime canonical JSON</p>
  <p class="catalog-card__need"><strong>Need</strong> Interoperable content identity for immutable receipts.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--trial">Trialing</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/zensical--zensical.md">zensical/zensical</a></h3>
  <p>Static site generator for modern, searchable project documentation.</p>
  <p class="catalog-card__role"><strong>Role</strong> development-only static catalog view adapter</p>
  <p class="catalog-card__need"><strong>Need</strong> Responsive Markdown rendering, tags, and private client-side search without a custom frontend.</p>
</article>
</div>
