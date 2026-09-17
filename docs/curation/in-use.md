---
title: "What ShouldaUsedThat uses"
description: "Runtime, development, CI, security, documentation, and release roles."
tags:
  - "Used here"
  - "toolchain"
---
# What ShouldaUsedThat uses

“Used here” means repository or configuration evidence confirms a named role. It does not turn a local choice into a universal recommendation.

<div class="table-scroll" role="region" aria-label="Toolchain role inventory" tabindex="0">
<table>
  <caption>Complete evidenced toolchain roles</caption>
  <thead><tr><th scope="col">Role family</th><th scope="col">Current owners</th><th scope="col">Evidence</th></tr></thead>
  <tbody>
<tr><th scope="row">Runtime</th><td>Click, Pydantic, JMESPath, platformdirs, PyYAML, Rich, and rfc8785</td><td><a href="../decisions/dependencies.json">decision evidence</a></td></tr>
<tr><th scope="row">Development</th><td>uv, pytest, Hypothesis, coverage.py, Ruff, strict mypy, and pre-commit</td><td><a href="../architecture/dogfood-reuse-audit.md">decision evidence</a></td></tr>
<tr><th scope="row">CI</th><td>GitHub Actions, checkout, setup-uv, and tested distribution artifacts</td><td><a href="../architecture/dogfood-reuse-audit.md">decision evidence</a></td></tr>
<tr><th scope="row">Security</th><td>pip-audit, CodeQL, dependency review, actionlint, zizmor, and Scorecard</td><td><a href="../decisions/quality-security.json">decision evidence</a></td></tr>
<tr><th scope="row">Docs</th><td>Generated Markdown/JSON, typos, lychee, and the bounded Zensical trial</td><td><a href="../decisions/zensical-site.json">decision evidence</a></td></tr>
<tr><th scope="row">Release</th><td>Hatchling, CycloneDX, checksums, GitHub Releases, and artifact attestations</td><td><a href="../decisions/sbom-release.json">decision evidence</a></td></tr>
  </tbody>
</table>
</div>

## Catalog records marked used or built

<div class="catalog-grid">
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/astral-sh--uv.md">astral-sh/uv</a></h3>
  <p>Fast Python package and project manager written in Rust.</p>
  <p class="catalog-card__role"><strong>Role</strong> development environment, lock, and execution</p>
  <p class="catalog-card__need"><strong>Need</strong> One reproducible Python environment and lock owner.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/github--codeql-action.md">github/codeql-action</a></h3>
  <p>GitHub Action for initializing, building, and analyzing projects with CodeQL.</p>
  <p class="catalog-card__role"><strong>Role</strong> hosted source security analysis</p>
  <p class="catalog-card__need"><strong>Need</strong> Repository-native source analysis with SARIF evidence.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/jmespath--jmespath.py.md">jmespath/jmespath.py</a></h3>
  <p>Python implementation of the JMESPath query language for JSON documents.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime advanced filter language</p>
  <p class="catalog-card__need"><strong>Need</strong> Safe local expressions over a documented candidate view.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/pallets--click.md">pallets/click</a></h3>
  <p>Composable Python package for creating command-line interfaces.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime CLI parser</p>
  <p class="catalog-card__need"><strong>Need</strong> A mature direct command and option boundary without a custom parser.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--build">Built here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/pradeeptathineni--shoulda-used-that.md">pradeeptathineni/shoulda-used-that</a></h3>
  <p>Evidence-bound coordinator for discovering, evaluating, and revisiting OSS choices.</p>
  <p class="catalog-card__role"><strong>Role</strong> deterministic evidence and curation coordinator</p>
  <p class="catalog-card__need"><strong>Need</strong> Own the residual project plus need plus evidence plus decision plus freshness relationship.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/pydantic--pydantic.md">pydantic/pydantic</a></h3>
  <p>Data validation and settings management using Python type annotations.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime typed contracts</p>
  <p class="catalog-card__need"><strong>Need</strong> Strict versioned records and generated JSON Schema.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/pytest-dev--pytest.md">pytest-dev/pytest</a></h3>
  <p>Python testing framework for readable tests, fixtures, and plugins.</p>
  <p class="catalog-card__role"><strong>Role</strong> development test runner</p>
  <p class="catalog-card__need"><strong>Need</strong> Readable scenario and contract tests across supported Python versions.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="entries/trailofbits--rfc8785.py.md">trailofbits/rfc8785.py</a></h3>
  <p>Python implementation of the RFC 8785 JSON Canonicalization Scheme.</p>
  <p class="catalog-card__role"><strong>Role</strong> runtime canonical JSON</p>
  <p class="catalog-card__need"><strong>Need</strong> Interoperable content identity for immutable receipts.</p>
</article>
</div>

The [full implementation reuse gate](../architecture/dogfood-reuse-audit.md) records versions, boundaries, alternatives, and removal conditions for the wider toolchain. The catalog source remains pradeeptathineni/shoulda\-used\-that's reviewed public profile.
