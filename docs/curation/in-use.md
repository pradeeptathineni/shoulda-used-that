---
title: "What ShouldaUsedThat uses"
description: "Runtime, development, CI, security, documentation, and release roles."
tags:
  - "Used here"
  - "toolchain"
---
# What ShouldaUsedThat uses

This is the catalog's clearest worked example: every item below owns a named job in this repository,
and repository or configuration evidence confirms that use. It answers “what did this project use
instead of rebuilding?”—not “what should every project use?”

<div class="table-scroll" role="region" aria-label="Toolchain role inventory" tabindex="0">
<table>
  <caption>Complete evidenced toolchain roles</caption>
  <thead><tr><th scope="col">Role family</th><th scope="col">Current owners</th><th scope="col">Evidence</th></tr></thead>
  <tbody>
<tr><th scope="row">Runtime</th><td>Click, Pydantic, JMESPath, platformdirs, PyYAML, Rich, and rfc8785</td><td><a href="../decisions/dependencies.json">decision evidence</a></td></tr>
<tr><th scope="row">Development</th><td>uv, pytest, Hypothesis, coverage.py, Ruff, strict mypy, pre-commit, and Vale</td><td><a href="../architecture/dogfood-reuse-audit.md">decision evidence</a></td></tr>
<tr><th scope="row">CI</th><td>GitHub Actions, checkout, setup-uv, and tested distribution artifacts</td><td><a href="../architecture/dogfood-reuse-audit.md">decision evidence</a></td></tr>
<tr><th scope="row">Security</th><td>pip-audit, CodeQL, dependency review, actionlint, zizmor, and Scorecard</td><td><a href="../decisions/quality-security.json">decision evidence</a></td></tr>
<tr><th scope="row">Docs</th><td>Generated Markdown/JSON, First Reader, local ZeroSlop checks, Vale, typos, lychee, and Zensical</td><td><a href="../decisions/public-writing-v0.3.json">decision evidence</a></td></tr>
<tr><th scope="row">Release</th><td>Hatchling, CycloneDX, checksums, GitHub Releases, and artifact attestations</td><td><a href="../decisions/sbom-release.json">decision evidence</a></td></tr>
  </tbody>
</table>
</div>

## Assessed relationships marked used or built

<div class="catalog-grid">
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Interoperable content identity for immutable receipts.</p>
  <h3><a href="entries/trailofbits--rfc8785.py.md">trailofbits/rfc8785.py</a></h3>
  <p><strong>Covers:</strong> A standards implementation avoids incomplete sorted-JSON identity rules.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Catch repeated hype and filler across public prose without building a prose engine or making an editorial model authoritative.</p>
  <h3><a href="entries/vale-cli--vale.md">vale-cli/vale</a></h3>
  <p><strong>Covers:</strong> Vale owns repeatable offline checks across hand-authored public Markdown; First Reader, local ZeroSlop checks, and human fact-and-tone review retain the judgment roles it cannot supply.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Own the residual project plus need plus evidence plus decision plus freshness relationship.</p>
  <h3><a href="entries/pradeeptathineni--shoulda-used-that.md">pradeeptathineni/shoulda-used-that</a></h3>
  <p><strong>Covers:</strong> Existing systems remain authoritative for transport, inventory, discovery, security, and rendering; the small cross-context receipt layer remains unique.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">A mature direct command and option boundary without a custom parser.</p>
  <h3><a href="entries/pallets--click.md">pallets/click</a></h3>
  <p><strong>Covers:</strong> Click owns parsing and help while typed domain validation stays in ShouldaUsedThat.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Readable scenario and contract tests across supported Python versions.</p>
  <h3><a href="entries/pytest-dev--pytest.md">pytest-dev/pytest</a></h3>
  <p><strong>Covers:</strong> pytest is the single test runner; property and coverage tools have distinct roles.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Repository-native source analysis with SARIF evidence.</p>
  <h3><a href="entries/github--codeql-action.md">github/codeql-action</a></h3>
  <p><strong>Covers:</strong> CodeQL supplies hosted source analysis while other tools retain separate dependency and workflow roles.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">One reproducible Python environment and lock owner.</p>
  <h3><a href="entries/astral-sh--uv.md">astral-sh/uv</a></h3>
  <p><strong>Covers:</strong> uv owns the environment and lock without layering Poetry, tox, or Nox.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Safe local expressions over a documented candidate view.</p>
  <h3><a href="entries/jmespath--jmespath.py.md">jmespath/jmespath.py</a></h3>
  <p><strong>Covers:</strong> JMESPath avoids a custom DSL or arbitrary Python evaluation.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
<article class="catalog-card assessment-card">
  <p class="assessment-card__problem">Strict versioned records and generated JSON Schema.</p>
  <h3><a href="entries/pydantic--pydantic.md">pydantic/pydantic</a></h3>
  <p><strong>Covers:</strong> Pydantic validates external records while workflow rules remain explicit services.</p>
  <p><strong>Watch:</strong> No watch item recorded.</p>
  <p><strong>Unknown:</strong> No unresolved question recorded.</p>
</article>
</div>

The [full implementation reuse gate](../architecture/dogfood-reuse-audit.md) records versions, boundaries, alternatives, and removal conditions for the wider toolchain. The catalog source remains pradeeptathineni/shoulda\-used\-that's reviewed public profile.
