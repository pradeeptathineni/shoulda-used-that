---
title: "ShouldaUsedThat uses itself"
description: "The catalog, additive GitHub projection, independent readback, and public export form one dogfood chain."
tags:
  - "dogfood"
  - "GitHub Lists"
  - "verification"
---
# ShouldaUsedThat uses itself

This repository is both the tool and a public execution of its central claim: **look for strong existing OSS before building another implementation, then preserve the evidence and decision boundary**.

## The executed shape

1. A human-readable [interest selection](selection.md) exposes the domains and exact repositories compiled from `curation/selections/personal-interests.json`.
2. A [cross-source decision receipt](../decisions/personal-oss-curation.json) records discovery sources, hard gates, rejected shortcuts, unknowns, and reconsideration triggers.
3. `curated` compiles those public inputs with the repository's own dependency and prior-art receipts into immutable canonical JSON.
4. `projected` reads the current GitHub account and seals only additive Star and List operations.
5. `apply` rechecks identity, capability, drift, expiry, and operation caps before each allowed write.
6. `verify` independently reads back every claimed public List, star, description, membership, and preserved membership.
7. `exported` builds this allowlisted catalog and its deterministic manifest.

The current public snapshot contains **221 reviewed repositories**, **12 projected Lists**, **218 projectable repositories**, and **248 intentional repository-to-List memberships**. Its canonical curation fingerprint is `curation_71798ffe0de72ea641ceea71746c7084c3bb0ecb1adb25e7c9e2e2d5cab73310`.

## Native GitHub projection

The GitHub views are deliberately lossy navigation surfaces. The catalog remains authoritative for rationale, provenance, freshness, rejection, and reconsideration.

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
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/oss-curation-prior-art">OSS Curation &amp; Prior Art</a></th><td>22</td><td>Catalogs, decision records, learning maps, native surfaces, and OSS evaluation tools.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/platform-engineering-delivery">Platform Engineering &amp; Delivery</a></th><td>26</td><td>CI/CD, infrastructure as code, developer platforms, release engineering, observability, and operations.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/python-engineering">Python Engineering</a></th><td>28</td><td>Runtime libraries, frameworks, packaging, typing, linting, testing, and developer tools.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/rag-search-knowledge">RAG, Search &amp; Knowledge</a></th><td>15</td><td>Retrieval, search, vector and graph stores, indexing, RAG, and knowledge systems.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/software-supply-chain">Software Supply Chain</a></th><td>24</td><td>Testing, security analysis, dependency evidence, SBOMs, signing, provenance, and releases.</td></tr>
<tr><th scope="row"><a href="https://github.com/stars/pradeeptathineni/lists/web-engineering-interfaces">Web Engineering &amp; Interfaces</a></th><td>19</td><td>Browser and server runtimes, frameworks, routing, styling, rendering, and interface systems.</td></tr>
  </tbody>
</table>
</div>

See the [sanitized live projection evidence](../operations/live-projection.md) for the last applied and independently verified public result. Private state, account node IDs, token scopes, raw API payloads, and operation receipts stay outside the repository.

## What this proves—and what it does not

- It proves the repository can compile a substantial reviewed catalog, preserve meaningful multi-list membership, execute its bounded additive projection, and verify public postconditions.
- It does not claim that stars equal adoption, that popularity equals quality, or that one list is a universal ranking.
- It does not silently unstar, remove memberships, rename or delete Lists, expose private repositories, or grant scheduled jobs personal mutation authority.
