---
title: "ShouldaUsedThat uses itself"
description: "The catalog, additive GitHub projection, independent readback, and public export form one dogfood chain."
tags:
  - "dogfood"
  - "GitHub Lists"
  - "verification"
---
# ShouldaUsedThat uses itself

This repository uses its own workflow to answer a practical question: **what existing tools should
own each job, and what small residual capability is worth building here?** The result is the public
catalog you are reading and a set of GitHub Lists that make the same choices easier to revisit.

## What you can inspect

- **The corpus:** [222 screened repositories](index.md) with reusable evidence and domain
  taxonomy.
- **The contextual layer:** 17 explicit problem-by-repository assessments; screening
  metadata alone creates none.
- **The public navigation:** 12 GitHub Lists containing
  219 projectable repositories and 249 intentional memberships.
- **The readback:** [sanitized live evidence](../operations/live-projection.md) for what was
  actually applied and independently verified.

GitHub is a convenient view, not the ledger. Lists cannot carry the full rationale, provenance,
freshness, rejection, or reconsideration evidence preserved by the catalog.

## How the result is produced

1. A human-readable [interest selection](selection.md) exposes the domains and exact repositories compiled from `curation/selections/personal-interests.json`.
2. A [cross-source decision receipt](../decisions/personal-oss-curation.json) records discovery sources, hard gates, rejected shortcuts, unknowns, and reconsideration triggers.
3. `curated` compiles those public inputs with the repository's own dependency and prior-art receipts into immutable canonical JSON.
4. `projected` reads the current GitHub account and seals only additive Star and List operations.
5. `apply` rechecks identity, capability, drift, expiry, and operation caps before each allowed write.
6. `verify` independently reads back every claimed public List, star, description, membership, and preserved membership.
7. `exported` builds this allowlisted catalog and its deterministic manifest.

## Native GitHub projection

Use the Lists for browsing; use the catalog when the reason or evidence matters.

<div class="table-scroll" role="region" aria-label="Projected GitHub Lists" tabindex="0">
<table>
  <caption>Public Lists generated from the reviewed profile</caption>
  <thead><tr><th scope="col">GitHub List</th><th scope="col">Reviewed repositories</th><th scope="col">Meaning</th></tr></thead>
  <tbody>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/cloud-infrastructure-iac">Cloud Infrastructure &amp; IaC</a></th><td>16</td><td>Cloud provisioning, infrastructure as code, Kubernetes, policy, cost, and local emulation.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/computer-vision-multimodal">Computer Vision &amp; Multimodal</a></th><td>14</td><td>Image and video understanding, generation, geometry, perception, and vision-language systems.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/creative-coding-visualization">Creative Coding &amp; Visualization</a></th><td>19</td><td>Generative art, animation, interactive graphics, visual explanation, and data visualization.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/generative-ai-agents">Generative AI &amp; Agents</a></th><td>27</td><td>Foundation-model tooling, inference, RAG, agents, evaluation, context, and multimodal generation.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/homelab-self-hosting">Homelab &amp; Self-Hosting</a></th><td>25</td><td>Private cloud, networking, storage, media, monitoring, and personally operated services.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/nature-physics-simulation">Nature, Physics &amp; Simulation</a></th><td>13</td><td>Artificial life, physics, agents, procedural systems, reinforcement learning, and simulation.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/oss-curation-prior-art">OSS Curation &amp; Prior Art</a></th><td>23</td><td>Catalogs, decision records, learning maps, native surfaces, and OSS evaluation tools.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/platform-engineering-delivery">Platform Engineering &amp; Delivery</a></th><td>26</td><td>CI/CD, infrastructure as code, developer platforms, release engineering, observability, and operations.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/python-engineering">Python Engineering</a></th><td>28</td><td>Runtime libraries, frameworks, packaging, typing, linting, testing, and developer tools.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/rag-search-knowledge">RAG, Search &amp; Knowledge</a></th><td>15</td><td>Retrieval, search, vector and graph stores, indexing, RAG, and knowledge systems.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/software-supply-chain">Software Supply Chain</a></th><td>24</td><td>Testing, security analysis, dependency evidence, SBOMs, signing, provenance, and releases.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/web-engineering-interfaces">Web Engineering &amp; Interfaces</a></th><td>19</td><td>Browser and server runtimes, frameworks, routing, styling, rendering, and interface systems.</td></tr>
  </tbody>
</table>
</div>

Private state, account node IDs, token scopes, raw API payloads, and operation receipts stay outside
the repository.

## What this proves—and what it does not

- It proves the repository can compile a substantial reviewed catalog, preserve meaningful multi-list membership, execute its bounded additive projection, and verify public postconditions.
- It does not claim that stars equal adoption, that popularity equals quality, or that one list is a universal ranking.
- It does not silently unstar, remove memberships, rename or delete Lists, expose private repositories, or grant scheduled jobs personal mutation authority.
