---
title: "Publish a curated OSS evidence set"
description: "Seed and publish a curated OSS evidence set without confusing popularity or catalog presence with contextual fit."
tags:
  - "oss-curation-foundations"
  - "platform-engineering-delivery"
---
# Publish a curated OSS evidence set

## The build problem

Seed and publish a curated OSS evidence set without confusing popularity or catalog presence with contextual fit\.

<div class="decision-summary">
  <p class="catalog-kicker">Reviewed answer</p>
  <p><strong>Recommended path:</strong> Learn from best-of-lists/best-of; Watch ejacobhayes/parsecio; Skip best-of-lists/best-of-generator.</p>
  <p><strong>You still own:</strong> Catalog presence and popularity still do not establish problem-specific fit. A safe publisher still needs explicit source contracts and last-known-good failure behavior.</p>
</div>

## Option-by-option decision

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--reference">Learn from</p>
  <h2>best-of-lists/best-of</h2>
  <p>Curated best-of lists backed by structured project metadata.</p>
  <p><strong>What it contributes:</strong> Provides human-curated public seed data and transparent ecosystem discovery inputs.</p>
  <p><strong>Watch:</strong> Its scores and inclusion choices are discovery provenance, not evidence of fit for a concrete problem.</p>
  <p><strong>Revisit when:</strong> License, published data shape, or attribution terms change.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/best-of-lists/best-of">Repository</a> · <a href="../evidence/best-of-lists--best-of.md#curated-oss-evidence-publishing">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--watch">Watch</p>
  <h2>ejacobhayes/parsecio</h2>
  <p>Static dashboard experiment for organizing starred repositories.</p>
  <p><strong>What it contributes:</strong> Shows how a lightweight static catalog can publish structured project information without a custom hosted application.</p>
  <p><strong>Watch:</strong> Stable releases and an auditable deterministic export contract were not established in the reviewed evidence.</p>
  <p><strong>Revisit when:</strong> A stable release and documented deterministic export contract exist.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/ejacobhayes/parsecio">Repository</a> · <a href="../evidence/ejacobhayes--parsecio.md#curated-oss-evidence-publishing">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--reject">Skip</p>
  <h2>best-of-lists/best-of-generator</h2>
  <p>Generator and updater used by best-of list projects.</p>
  <p><strong>What it contributes:</strong> Demonstrates a generator-backed catalog workflow and the maintenance concerns such a pipeline must own.</p>
  <p><strong>Watch:</strong> GPL and content boundaries plus observed last-known-good failures make embedding it unjustified here.</p>
  <p><strong>Revisit when:</strong> License documentation and fail-closed last-known-good behavior are resolved upstream.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/best-of-lists/best-of-generator">Repository</a> · <a href="../evidence/best-of-lists--best-of-generator.md#curated-oss-evidence-publishing">Evidence</a></p>
</article>
</div>

## What the existing tools already cover

- Human\-curated seed data can provide transparent discovery provenance\.
- Static generation can publish structured project information without a bespoke hosted UI\.

## What you still need to decide or build

- Catalog presence and popularity still do not establish problem\-specific fit\.
- A safe publisher still needs explicit source contracts and last\-known\-good failure behavior\.

That remaining work is the justified custom scope in this decision. The actions above apply only
to the stated problem; they are not universal rankings or guarantees beyond the cited evidence.

Checked 2026\-09\-17 · [See all decisions](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../decisions/curation-coordinator.json">docs/decisions/curation-coordinator.json</a>

</details>
