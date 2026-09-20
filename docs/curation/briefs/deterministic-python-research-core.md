---
title: "Build a deterministic Python research core"
description: "Build a deterministic local Python research core without inventing command parsing, validation, safe querying, or canonical JSON."
tags:
  - "oss-curation-foundations"
  - "python-engineering"
---
# Build a deterministic Python research core

## Problem

Build a deterministic local Python research core without inventing command parsing, validation, safe querying, or canonical JSON\.

## Approaches worth knowing

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <h2>pallets/click</h2>
  <p>Composable Python package for creating command-line interfaces.</p>
  <p><strong>Covers:</strong> Owns mature command parsing and help generation while typed domain validation stays outside the parser.</p>
  <p><strong>Watch:</strong> It does not define research semantics, evidence policy, or the command lifecycle.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pallets/click">Repository</a> · <a href="../evidence/pallets--click.md#deterministic-python-research-core">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>pydantic/pydantic</h2>
  <p>Data validation and settings management using Python type annotations.</p>
  <p><strong>Covers:</strong> Validates strict versioned records and generates JSON Schema at the external data boundary.</p>
  <p><strong>Watch:</strong> Workflow rules, canonical hashing, and state transitions must remain explicit outside model validation.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pydantic/pydantic">Repository</a> · <a href="../evidence/pydantic--pydantic.md#deterministic-python-research-core">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>jmespath/jmespath.py</h2>
  <p>Python implementation of the JMESPath query language for JSON documents.</p>
  <p><strong>Covers:</strong> Evaluates safe local expressions over one documented candidate view without arbitrary Python execution.</p>
  <p><strong>Watch:</strong> It is only the advanced filter evaluator; native gates and the exposed query view remain project-owned.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/jmespath/jmespath.py">Repository</a> · <a href="../evidence/jmespath--jmespath.py.md#deterministic-python-research-core">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <h2>trailofbits/rfc8785.py</h2>
  <p>Python implementation of the RFC 8785 JSON Canonicalization Scheme.</p>
  <p><strong>Covers:</strong> Supplies standards-based canonical JSON bytes so content identity does not rely on ordinary sorted JSON.</p>
  <p><strong>Watch:</strong> It canonicalizes bytes only; immutable receipt policy and safe state persistence remain separate responsibilities.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/trailofbits/rfc8785.py">Repository</a> · <a href="../evidence/trailofbits--rfc8785.py.md#deterministic-python-research-core">Evidence</a></p>
</article>
</div>

## What appears covered

- Mature libraries already own command parsing, strict records, safe local expressions, and canonical JSON bytes\.
- Each capability can stay behind a narrow deterministic adapter\.

## What still appears unresolved

- The product\-specific research plan, evidence gates, state transitions, and human answer still need a local coordinator\.

Based on the reviewed evidence, that residual work may still justify a focused build. This brief
does not rank the candidates or imply certainty beyond the cited evidence.

Checked 2026\-09\-17 · [Explore all briefs](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../decisions/canonical-state.json">docs/decisions/canonical-state.json</a>
- <a href="../../decisions/cli-filter.json">docs/decisions/cli-filter.json</a>
- <a href="../../decisions/dependencies.json">docs/decisions/dependencies.json</a>

</details>
