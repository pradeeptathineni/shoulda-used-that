---
title: "Run a reproducible Python quality gate"
description: "Run a reproducible quality gate for a typed Python CLI across environments, behavior, and hosted source analysis."
tags:
  - "platform-engineering-delivery"
  - "python-engineering"
  - "software-supply-chain"
---
# Run a reproducible Python quality gate

## The build problem

Run a reproducible quality gate for a typed Python CLI across environments, behavior, and hosted source analysis\.

<div class="decision-summary">
  <p class="catalog-kicker">Reviewed answer</p>
  <p><strong>Recommended path:</strong> Use astral-sh/uv, pytest-dev/pytest, and github/codeql-action.</p>
  <p><strong>You still own:</strong> The repository must still define its supported versions, typed postconditions, coverage target, and complete gate ordering.</p>
</div>

## Option-by-option decision

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>astral-sh/uv</h2>
  <p>Fast Python package and project manager written in Rust.</p>
  <p><strong>What it contributes:</strong> Owns the reproducible Python environment, lock, execution, and build orchestration.</p>
  <p><strong>Watch:</strong> It is the environment owner, not a replacement for tests, typing, linting, or hosted security analysis.</p>
  <p><strong>Revisit when:</strong> The lock or cross-platform execution contract stops being reproducible.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/astral-sh/uv">Repository</a> · <a href="../evidence/astral-sh--uv.md#reproducible-python-quality-gate">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>pytest-dev/pytest</h2>
  <p>Python testing framework for readable tests, fixtures, and plugins.</p>
  <p><strong>What it contributes:</strong> Runs readable scenario and contract tests across supported Python versions.</p>
  <p><strong>Watch:</strong> Property generation and branch visibility remain distinct Hypothesis and coverage.py roles.</p>
  <p><strong>Revisit when:</strong> Supported Python compatibility or plugin behavior becomes unsuitable.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/pytest-dev/pytest">Repository</a> · <a href="../evidence/pytest-dev--pytest.md#reproducible-python-quality-gate">Evidence</a></p>
</article>
<article class="catalog-card assessment-card">
  <p class="decision-chip decision-chip--adopt">Use</p>
  <h2>github/codeql-action</h2>
  <p>GitHub Action for initializing, building, and analyzing projects with CodeQL.</p>
  <p><strong>What it contributes:</strong> Supplies hosted repository-native source analysis and SARIF reporting in GitHub Actions.</p>
  <p><strong>Watch:</strong> It is GitHub-hosted and does not replace dependency, workflow, typing, or behavior checks.</p>
  <p><strong>Revisit when:</strong> GitHub changes the supported action or the selected SHA is no longer valid.</p>
  <p class="catalog-card__evidence">Checked 2026-09-17 · <a href="https://github.com/github/codeql-action">Repository</a> · <a href="../evidence/github--codeql-action.md#reproducible-python-quality-gate">Evidence</a></p>
</article>
</div>

## What the existing tools already cover

- Environment locking, behavior tests, and hosted source analysis already have mature owners\.
- Their boundaries can compose without inventing one universal quality tool\.

## What you still need to decide or build

- The repository must still define its supported versions, typed postconditions, coverage target, and complete gate ordering\.

That remaining work is the justified custom scope in this decision. The actions above apply only
to the stated problem; they are not universal rankings or guarantees beyond the cited evidence.

Checked 2026\-09\-17 · [See all decisions](../index.md)

<details>
<summary>Brief research evidence</summary>

- <a href="../../architecture/dogfood-reuse-audit.md">docs/architecture/dogfood-reuse-audit.md</a>
- <a href="../../decisions/quality-security.json">docs/decisions/quality-security.json</a>

</details>
