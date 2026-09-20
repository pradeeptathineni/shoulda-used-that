---
title: "Publish a curated OSS evidence set"
description: "Seed and publish a curated OSS evidence set without confusing popularity or catalog presence with contextual fit."
tags:
  - "oss-curation-foundations"
  - "platform-engineering-delivery"
---
# Publish a curated OSS evidence set

## Problem

Seed and publish a curated OSS evidence set without confusing popularity or catalog presence with contextual fit\.

## Approaches worth knowing

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <h2>best-of-lists/best-of</h2>
  <p>Curated best-of lists backed by structured project metadata.</p>
  <p><strong>Covers:</strong> Provides human-curated public seed data and transparent ecosystem discovery inputs.</p>
  <p><strong>Watch:</strong> Its scores and inclusion choices are discovery provenance, not evidence of fit for a concrete problem.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/best-of-lists/best-of">Repository</a> · <a href="../evidence/best-of-lists--best-of.md#curated-oss-evidence-publishing">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>ejacobhayes/parsecio</h2>
  <p>Static dashboard experiment for organizing starred repositories.</p>
  <p><strong>Covers:</strong> Shows how a lightweight static catalog can publish structured project information without a custom hosted application.</p>
  <p><strong>Watch:</strong> Stable releases and an auditable deterministic export contract were not established in the reviewed evidence.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/ejacobhayes/parsecio">Repository</a> · <a href="../evidence/ejacobhayes--parsecio.md#curated-oss-evidence-publishing">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>best-of-lists/best-of-generator</h2>
  <p>Generator and updater used by best-of list projects.</p>
  <p><strong>Covers:</strong> Demonstrates a generator-backed catalog workflow and the maintenance concerns such a pipeline must own.</p>
  <p><strong>Watch:</strong> GPL and content boundaries plus observed last-known-good failures make embedding it unjustified here.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/best-of-lists/best-of-generator">Repository</a> · <a href="../evidence/best-of-lists--best-of-generator.md#curated-oss-evidence-publishing">Evidence</a></p>
</article>
</div>

## What appears covered

- Human\-curated seed data can provide transparent discovery provenance\.
- Static generation can publish structured project information without a bespoke hosted UI\.

## What still appears unresolved

- Catalog presence and popularity still do not establish problem\-specific fit\.
- A safe publisher still needs explicit source contracts and last\-known\-good failure behavior\.

Based on the reviewed evidence, that residual work may still justify a focused build. This brief
does not rank the candidates or imply certainty beyond the cited evidence.

Checked 2026\-09\-17 · [Explore all briefs](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../decisions/curation-coordinator.json">docs/decisions/curation-coordinator.json</a>

</details>
