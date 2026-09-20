---
title: "Keep prior-art coordination local-first"
description: "Coordinate prior-art research locally without making a hosted backend or personal GitHub mutation the product core."
tags:
  - "oss-curation-foundations"
  - "platform-engineering-delivery"
---
# Keep prior\-art coordination local\-first

## The build problem

Coordinate prior\-art research locally without making a hosted backend or personal GitHub mutation the product core\.

<div class="decision-summary">
  <p class="catalog-kicker">Reviewed answer</p>
  <p><strong>Recommended path:</strong> Learn from amintacccp/githubstarsmanager; Skip boffti/stardash; Build pradeeptathineni/shoulda-used-that.</p>
  <p><strong>You still own:</strong> General natural-language discovery remains outside the deterministic core. Personal GitHub organization must stay an optional sealed operator action, not a prerequisite for research.</p>
</div>

## Option-by-option decision

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--reference">Learn from</p>
  <h2>amintacccp/githubstarsmanager</h2>
  <p>Desktop application for browsing, searching, and organizing GitHub stars.</p>
  <p><strong>What it contributes:</strong> Provides useful prior art for searching and organizing an existing GitHub Stars collection.</p>
  <p><strong>Watch:</strong> Credential storage, provider, plugin, and release-provenance boundaries keep it out of this runtime.</p>
  <p><strong>Revisit when:</strong> Credential storage, outbound boundaries, and verifiable release provenance are independently resolved.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/AmintaCCCP/GithubStarsManager">Repository</a> · <a href="../evidence/amintacccp--githubstarsmanager.md#local-first-prior-art-coordination">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--reject">Skip</p>
  <h2>boffti/stardash</h2>
  <p>Dashboard for exploring and organizing GitHub stars.</p>
  <p><strong>What it contributes:</strong> Demonstrates a hosted interface for browsing and organizing starred repositories.</p>
  <p><strong>Watch:</strong> Supabase, provider, telemetry, and direct mutation surfaces are disproportionate to a local evidence core.</p>
  <p><strong>Revisit when:</strong> A local static boundary with no direct mutation or analytics becomes the default.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/boffti/stardash">Repository</a> · <a href="../evidence/boffti--stardash.md#local-first-prior-art-coordination">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--build">Build</p>
  <h2>pradeeptathineni/shoulda-used-that</h2>
  <p>Evidence-bound coordinator for discovering, evaluating, and revisiting OSS choices.</p>
  <p><strong>What it contributes:</strong> Owns the residual problem, evidence, decision, and freshness relation while established tools keep their native roles.</p>
  <p><strong>Watch:</strong> Discovery still requires an explicit research plan; it is not a general natural-language recommendation engine.</p>
  <p><strong>Revisit when:</strong> An established component supplies the complete residual under the same privacy and mutation guarantees.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pradeeptathineni/shoulda-used-that">Repository</a> · <a href="../evidence/pradeeptathineni--shoulda-used-that.md#local-first-prior-art-coordination">Evidence</a></p>
</article>
</div>

## What the existing tools already cover

- Existing products cover Stars browsing, organization, and hosted management interfaces\.
- A local receipt layer can preserve explicit research context, evidence, decisions, and freshness\.

## What you still need to decide or build

- General natural\-language discovery remains outside the deterministic core\.
- Personal GitHub organization must stay an optional sealed operator action, not a prerequisite for research\.

That remaining work is the justified custom scope in this decision. The actions above apply only
to the stated problem; they are not universal rankings or guarantees beyond the cited evidence.

Checked 2026\-09\-17 · [See all decisions](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../architecture/curation-v0.2.md">docs/architecture/curation-v0.2.md</a>
- <a href="../../decisions/curation-coordinator.json">docs/decisions/curation-coordinator.json</a>

</details>
