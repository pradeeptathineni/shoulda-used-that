---
title: "Keep prior-art coordination local-first"
description: "Coordinate prior-art research locally without making a hosted backend or personal GitHub mutation the product core."
tags:
  - "oss-curation-foundations"
  - "platform-engineering-delivery"
---
# Keep prior\-art coordination local\-first

## Problem

Coordinate prior\-art research locally without making a hosted backend or personal GitHub mutation the product core\.

## Approaches worth knowing

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <h2>amintacccp/githubstarsmanager</h2>
  <p>Desktop application for browsing, searching, and organizing GitHub stars.</p>
  <p><strong>Covers:</strong> Provides useful prior art for searching and organizing an existing GitHub Stars collection.</p>
  <p><strong>Watch:</strong> Credential storage, provider, plugin, and release-provenance boundaries keep it out of this runtime.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/AmintaCCCP/GithubStarsManager">Repository</a> · <a href="../evidence/amintacccp--githubstarsmanager.md#local-first-prior-art-coordination">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>boffti/stardash</h2>
  <p>Dashboard for exploring and organizing GitHub stars.</p>
  <p><strong>Covers:</strong> Demonstrates a hosted interface for browsing and organizing starred repositories.</p>
  <p><strong>Watch:</strong> Supabase, provider, telemetry, and direct mutation surfaces are disproportionate to a local evidence core.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/boffti/stardash">Repository</a> · <a href="../evidence/boffti--stardash.md#local-first-prior-art-coordination">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>pradeeptathineni/shoulda-used-that</h2>
  <p>Evidence-bound coordinator for discovering, evaluating, and revisiting OSS choices.</p>
  <p><strong>Covers:</strong> Owns the residual problem, evidence, decision, and freshness relation while established tools keep their native roles.</p>
  <p><strong>Watch:</strong> Discovery still requires an explicit research plan; it is not a general natural-language recommendation engine.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pradeeptathineni/shoulda-used-that">Repository</a> · <a href="../evidence/pradeeptathineni--shoulda-used-that.md#local-first-prior-art-coordination">Evidence</a></p>
</article>
</div>

## What appears covered

- Existing products cover Stars browsing, organization, and hosted management interfaces\.
- A local receipt layer can preserve explicit research context, evidence, decisions, and freshness\.

## What still appears unresolved

- General natural\-language discovery remains outside the deterministic core\.
- Personal GitHub organization must stay an optional sealed operator action, not a prerequisite for research\.

Based on the reviewed evidence, that residual work may still justify a focused build. This brief
does not rank the candidates or imply certainty beyond the cited evidence.

Checked 2026\-09\-17 · [Explore all briefs](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../architecture/curation-v0.2.md">docs/architecture/curation-v0.2.md</a>
- <a href="../../decisions/curation-coordinator.json">docs/decisions/curation-coordinator.json</a>

</details>
