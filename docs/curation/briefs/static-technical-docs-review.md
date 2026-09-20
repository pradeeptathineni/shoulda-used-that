---
title: "Publish and review static technical documentation"
description: "Publish searchable static technical documentation and review its prose without making an editorial model authoritative."
tags:
  - "generative-ai-agents"
  - "oss-curation-foundations"
  - "platform-engineering-delivery"
---
# Publish and review static technical documentation

## The build problem

Publish searchable static technical documentation and review its prose without making an editorial model authoritative\.

<div class="decision-summary">
  <p class="catalog-kicker">Reviewed answer</p>
  <p><strong>Recommended path:</strong> Use vale-cli/vale; Try zensical/zensical; Learn from addyosmani/agent-skills; Study shubhamsaboo/awesome-llm-apps.</p>
  <p><strong>You still own:</strong> Human review must still decide whether claims are true, concise, useful, and supported by repository evidence. Simulated readers do not replace measured reader behavior.</p>
</div>

## Option-by-option decision

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--trial">Try</p>
  <h2>zensical/zensical</h2>
  <p>Static site generator for modern, searchable project documentation.</p>
  <p><strong>What it contributes:</strong> Builds responsive Markdown pages, tags, and private client-side search without a custom frontend.</p>
  <p><strong>Watch:</strong> The pinned pre-1.0 version remains removable and must keep proving deterministic, accessible, no-runtime-network output.</p>
  <p><strong>Revisit when:</strong> Strict build, search, accessibility, or no-third-party-request validation fails.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/zensical/zensical">Repository</a> · <a href="../evidence/zensical--zensical.md#static-technical-docs-review">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>vale-cli/vale</h2>
  <p>Markup-aware prose linter with project-owned styles and offline execution.</p>
  <p><strong>What it contributes:</strong> Runs repeatable offline prose checks across hand-authored public Markdown.</p>
  <p><strong>Watch:</strong> It can flag deterministic patterns but cannot establish factual truth, reader usefulness, or editorial judgment.</p>
  <p><strong>Revisit when:</strong> The pinned version cannot lint selected sources deterministically or project rules create repeated false positives.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/vale-cli/vale">Repository</a> · <a href="../evidence/vale-cli--vale.md#static-technical-docs-review">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--learn">Study</p>
  <h2>shubhamsaboo/awesome-llm-apps</h2>
  <p>100+ AI Agents, Agent Skills and RAG Apps - Free and Open Source.</p>
  <p><strong>What it contributes:</strong> Supplies the pinned First Reader method used for context-free review of first-contact public surfaces.</p>
  <p><strong>Watch:</strong> The parent repository is a learning map, not a production dependency or blanket endorsement. Unknown: Simulated reader responses are hypotheses rather than measured user behavior.</p>
  <p><strong>Revisit when:</strong> Reader reviews fail to find the primary path or require sending unpublished prose to a hosted service.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/Shubhamsaboo/awesome-llm-apps">Repository</a> · <a href="../evidence/shubhamsaboo--awesome-llm-apps.md#static-technical-docs-review">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--reference">Learn from</p>
  <h2>addyosmani/agent-skills</h2>
  <p>Open development guidance and reusable skills for agent-assisted engineering.</p>
  <p><strong>What it contributes:</strong> Provides pinned selective-context and source-driven-development guidance for the editorial workflow.</p>
  <p><strong>Watch:</strong> The skills are reviewed guidance only; they are neither runtime dependencies nor factual authorities.</p>
  <p><strong>Revisit when:</strong> A later pinned revision is fully reviewed and materially improves the workflow.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/addyosmani/agent-skills">Repository</a> · <a href="../evidence/addyosmani--agent-skills.md#static-technical-docs-review">Evidence</a></p>
</article>
</div>

## What the existing tools already cover

- Static rendering, private search, deterministic prose linting, and bounded review methods already exist\.
- Editorial aids can remain separate from factual source and approval authority\.

## What you still need to decide or build

- Human review must still decide whether claims are true, concise, useful, and supported by repository evidence\.
- Simulated readers do not replace measured reader behavior\.

That remaining work is the justified custom scope in this decision. The actions above apply only
to the stated problem; they are not universal rankings or guarantees beyond the cited evidence.

Checked 2026\-09\-17 · [See all decisions](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../decisions/context.json">docs/decisions/context.json</a>
- <a href="../../decisions/public-writing-v0.4.json">docs/decisions/public-writing-v0.4.json</a>
- <a href="../../decisions/zensical-site.json">docs/decisions/zensical-site.json</a>

</details>
