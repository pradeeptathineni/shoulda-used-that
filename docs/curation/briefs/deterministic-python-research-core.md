---
title: "Build a deterministic Python research core"
description: "Build a deterministic local Python research core without inventing command parsing, validation, safe querying, or canonical JSON."
tags:
  - "oss-curation-foundations"
  - "python-engineering"
---
# Build a deterministic Python research core

## The build problem

Build a deterministic local Python research core without inventing command parsing, validation, safe querying, or canonical JSON\.

<div class="decision-summary">
  <p class="catalog-kicker">Reviewed answer</p>
  <p><strong>Recommended path:</strong> Use pallets/click, pydantic/pydantic, jmespath/jmespath.py, and trailofbits/rfc8785.py.</p>
  <p><strong>You still own:</strong> The product-specific research plan, evidence gates, state transitions, and human answer still need a local coordinator.</p>
</div>

## Option-by-option decision

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>pallets/click</h2>
  <p>Composable Python package for creating command-line interfaces.</p>
  <p><strong>What it contributes:</strong> Owns mature command parsing and help generation while typed domain validation stays outside the parser.</p>
  <p><strong>Watch:</strong> It does not define research semantics, evidence policy, or the command lifecycle.</p>
  <p><strong>Revisit when:</strong> The selected major version becomes incompatible or an already-used component fully owns parsing.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pallets/click">Repository</a> · <a href="../evidence/pallets--click.md#deterministic-python-research-core">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>pydantic/pydantic</h2>
  <p>Data validation and settings management using Python type annotations.</p>
  <p><strong>What it contributes:</strong> Validates strict versioned records and generates JSON Schema at the external data boundary.</p>
  <p><strong>Watch:</strong> Workflow rules, canonical hashing, and state transitions must remain explicit outside model validation.</p>
  <p><strong>Revisit when:</strong> A major version breaks the strict immutable record boundary.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pydantic/pydantic">Repository</a> · <a href="../evidence/pydantic--pydantic.md#deterministic-python-research-core">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>jmespath/jmespath.py</h2>
  <p>Python implementation of the JMESPath query language for JSON documents.</p>
  <p><strong>What it contributes:</strong> Evaluates safe local expressions over one documented candidate view without arbitrary Python execution.</p>
  <p><strong>Watch:</strong> It is only the advanced filter evaluator; native gates and the exposed query view remain project-owned.</p>
  <p><strong>Revisit when:</strong> A required real-world filter cannot be expressed safely.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/jmespath/jmespath.py">Repository</a> · <a href="../evidence/jmespath--jmespath.py.md#deterministic-python-research-core">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>trailofbits/rfc8785.py</h2>
  <p>Python implementation of the RFC 8785 JSON Canonicalization Scheme.</p>
  <p><strong>What it contributes:</strong> Supplies standards-based canonical JSON bytes so content identity does not rely on ordinary sorted JSON.</p>
  <p><strong>Watch:</strong> It canonicalizes bytes only; immutable receipt policy and safe state persistence remain separate responsibilities.</p>
  <p><strong>Revisit when:</strong> Published RFC vectors fail or compatibility changes.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/trailofbits/rfc8785.py">Repository</a> · <a href="../evidence/trailofbits--rfc8785.py.md#deterministic-python-research-core">Evidence</a></p>
</article>
</div>

## What the existing tools already cover

- Mature libraries already own command parsing, strict records, safe local expressions, and canonical JSON bytes\.
- Each capability can stay behind a narrow deterministic adapter\.

## What you still need to decide or build

- The product\-specific research plan, evidence gates, state transitions, and human answer still need a local coordinator\.

That remaining work is the justified custom scope in this decision. The actions above apply only
to the stated problem; they are not universal rankings or guarantees beyond the cited evidence.

Checked 2026\-09\-17 · [See all decisions](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../decisions/canonical-state.json">docs/decisions/canonical-state.json</a>
- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>
- <a href="../../decisions/dependencies.json">docs/decisions/dependencies.json</a>

</details>
