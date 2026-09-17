---
title: "Software Supply Chain"
description: "Testing, security analysis, dependency evidence, SBOMs, signing, provenance, and releases."
tags:
  - "Software Supply Chain"
  - "SBOM"
  - "release security"
  - "supply chain security"
---
# Software Supply Chain

<p class="collection-deck">Testing, security analysis, dependency evidence, SBOMs, signing, provenance, and releases.</p>

**Aliases:** SBOM, release security, supply chain security<br>
**GitHub List eligibility:** eligible for a sealed plan<br>
**Review cadence:** 60 days

## Meaning

A cross\-cutting collection for evidenced software integrity and assurance controls\.

- **Include:** Include a reviewed repository when it supplies a named test, security, packaging, signing, or provenance control\.
- **Exclude:** Exclude generic security branding without a bounded, inspectable control\.

## Reviewed entries

<div class="catalog-grid">
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/actions--attest-build-provenance.md">actions/attest-build-provenance</a></h3>
  <p>Action for generating build provenance attestations for workflow artifacts</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/anchore--grype.md">anchore/grype</a></h3>
  <p>A vulnerability scanner for container images and filesystems</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/anchore--syft.md">anchore/syft</a></h3>
  <p>CLI tool and library for generating a Software Bill of Materials from container images and filesystems</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/aquasecurity--trivy.md">aquasecurity/trivy</a></h3>
  <p>Find vulnerabilities, misconfigurations, secrets, SBOM in containers, Kubernetes, code repositories, clouds and more</p>
  <p class="catalog-card__role"><strong>Role</strong> cloud infrastructure and infrastructure-as-code prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare mature provisioning, policy, cost, emulation, and orchestration tools before building cloud automation.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/bridgecrewio--checkov.md">bridgecrewio/checkov</a></h3>
  <p>Prevent cloud misconfigurations and find vulnerabilities during build-time in infrastructure as code, container images and open source packages with Checkov by Bridgecrew.</p>
  <p class="catalog-card__role"><strong>Role</strong> cloud infrastructure and infrastructure-as-code prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare mature provisioning, policy, cost, emulation, and orchestration tools before building cloud automation.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/cyclonedx--cyclonedx-python.md">cyclonedx/cyclonedx-python</a></h3>
  <p>CycloneDX Software Bill of Materials (SBOM) generator for Python projects and environments</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/dependabot--dependabot-core.md">dependabot/dependabot-core</a></h3>
  <p>🤖 Dependabot&#x27;s core logic for creating update PRs.</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/dependency-check--dependencycheck.md">dependency-check/dependencycheck</a></h3>
  <p>OWASP dependency-check is a software composition analysis utility that detects publicly disclosed vulnerabilities in application dependencies.</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/github--codeql-action.md">github/codeql-action</a></h3>
  <p>GitHub Action for initializing, building, and analyzing projects with CodeQL.</p>
  <p class="catalog-card__role"><strong>Role</strong> hosted source security analysis</p>
  <p class="catalog-card__need"><strong>Need</strong> Repository-native source analysis with SARIF evidence.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/gitleaks--gitleaks.md">gitleaks/gitleaks</a></h3>
  <p>Find secrets with Gitleaks 🔑</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/google--osv-scanner.md">google/osv-scanner</a></h3>
  <p>Vulnerability scanner written in Go which uses the data provided by https://osv.dev</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/ossf--scorecard.md">ossf/scorecard</a></h3>
  <p>OpenSSF Scorecard - Security health metrics for Open Source</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/pre-commit--pre-commit.md">pre-commit/pre-commit</a></h3>
  <p>A framework for managing and maintaining multi-language pre-commit hooks.</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--adopt">Used here</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/pytest-dev--pytest.md">pytest-dev/pytest</a></h3>
  <p>Python testing framework for readable tests, fixtures, and plugins.</p>
  <p class="catalog-card__role"><strong>Role</strong> development test runner</p>
  <p class="catalog-card__need"><strong>Need</strong> Readable scenario and contract tests across supported Python versions.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/renovatebot--renovate.md">renovatebot/renovate</a></h3>
  <p>Home of the Renovate CLI: Cross-platform Dependency Automation by Mend.io</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/reviewdog--reviewdog.md">reviewdog/reviewdog</a></h3>
  <p>🐶 Automated code review tool integrated with any code analysis tools regardless of programming language</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/rhysd--actionlint.md">rhysd/actionlint</a></h3>
  <p>:octocat: Static checker for GitHub Actions workflow files</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/semgrep--semgrep.md">semgrep/semgrep</a></h3>
  <p>Lightweight static analysis for many languages. Find bug variants with patterns that look like source code.</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/sigstore--cosign.md">sigstore/cosign</a></h3>
  <p>Code signing and transparency for containers and binaries</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/slsa-framework--slsa-github-generator.md">slsa-framework/slsa-github-generator</a></h3>
  <p>Language-agnostic SLSA provenance generation for Github Actions</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/step-security--harden-runner.md">step-security/harden-runner</a></h3>
  <p>Harden-Runner is a CI/CD security agent that works like an EDR for GitHub Actions runners. It monitors network egress, file integrity, and process activity on those runners, detecting threats in real-time.</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/super-linter--super-linter.md">super-linter/super-linter</a></h3>
  <p>Combination of multiple linters to run as a GitHub Action or standalone</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/trufflesecurity--trufflehog.md">trufflesecurity/trufflehog</a></h3>
  <p>Find, verify, and analyze leaked credentials</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
<article class="catalog-card">
  <div class="catalog-card__meta"><span class="status-chip status-chip--reference">Reference</span> <span class="freshness-chip freshness-chip--current">current</span></div>
  <h3><a href="../entries/zizmorcore--zizmor.md">zizmorcore/zizmor</a></h3>
  <p>Static analysis for GitHub Actions</p>
  <p class="catalog-card__role"><strong>Role</strong> software supply-chain and assurance prior art</p>
  <p class="catalog-card__need"><strong>Need</strong> Compare established testing, analysis, signing, SBOM, provenance, dependency, and workflow controls before writing a security mechanism.</p>
</article>
</div>
