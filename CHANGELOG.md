# Changelog

All notable changes to this project are documented here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Replaced the repository-first catalog experience with five concrete prior-art briefs backed by
  problem-specific assessments, while retaining all safe screened evidence in canonical JSON.
- Replaced past-tense and hidden top-level CLI names with imperative research commands
  (`check`, `inspect`, `remember`, and `recheck`) plus discoverable `catalog` and `github` groups.
- Split research orchestration from maintainer publication/mutation services and stopped fresh
  research state from creating administrative or retired lifecycle directories.

### Removed

- Retired `saved`, legacy List-preview projection, and `used` adoption-plan creation along with
  their current schemas, renderers, services, and state writers. Existing JSON remains readable
  through explicit read-only legacy validators and immutable release tags.
- Removed repository/collection/status page generation and the obsolete catalog scale benchmark;
  only assessed candidates receive rich evidence pages.

## [0.3.0] - 2026-09-17

### Added

- A 206-repository personal-interest selection compiled into a 222-record catalog spanning 12
  intentionally separated OSS domains, with cross-source discovery evidence, live metadata gates,
  bounded exceptions, and meaningful multi-List membership.
- A generated self-use page and sanitized live-projection evidence linking the authoritative
  catalog to every public GitHub List.
- A deterministic read-only refresh command that enriches human-authored selections from exact
  GitHub repository metadata and reseals the profile.
- A Vale-based offline public-writing gate, context-free first-reader review policy, and explicit
  boundaries for optional AI-pattern diagnostics.
- A reader-first getting-started guide, outcome-oriented CLI help, and an explicit verified-wheel
  installation path.

### Changed

- Membership apply now advances from GitHub's strictly validated mutation result and requires a
  full remote replay before completion, avoiding redundant eventually consistent account reads
  while retaining one immutable receipt per sealed operation.
- Homepage calls to action now use a dedicated responsive group with separated, equal-width,
  touch-friendly controls on phone-sized viewports.
- The catalog overview now presents 12 collection routes instead of duplicating every entry, while
  generated rationales state the exact metadata-and-fit review boundary.
- Projection and apply orchestration now separate validation and live-capability phases, with a
  Ruff complexity ceiling preventing further branch growth.
- Public entrypoints now lead with browsing, a no-authentication check, or verified installation;
  operator mechanics remain directly linked one layer deeper.
- Catalog collections and entries now introduce the reader's need, rationale, status meaning, and
  reconsideration trigger before provenance detail.
- The release workflow derives its SBOM name and release-notes path from the verified tag instead
  of embedding one release version.

### Verified

- The live `pradeeptathineni` projection completed 438 additive operations and independently
  verified all 488 initial postconditions with zero mismatches. After refreshing the repository's
  own release evidence, a newly sealed semantic no-op independently verified all 730 current
  identity, capability, state-integrity, List, star, membership, and preserved-membership
  postconditions with zero mismatches.

## [0.2.0] - 2026-09-17

### Added

- Versioned public curation profiles, deterministic snapshots, explicit collection semantics,
  freshness, exclusions, and material-difference receipts.
- Read-only inspection of explicit GitHub projects, bounded local roots, and supplied SPDX or
  CycloneDX SBOMs, with visible applicability evidence and no target writes.
- Typed, paginated GitHub Stars/Lists reads and sealed additive projection plans bound to account
  identity, current state, exact operations, expiry, and operation caps.
- Interactive-only `github-curation` apply and independent verify receipts for public List
  creation, starring, and membership union, including partial and indeterminate recovery.
- An allowlisted Markdown/JSON catalog, digest manifest, strict Zensical build, responsive public
  site, client search, scale benchmark, and GitHub Pages workflow.
- One-shot read-only catalog upkeep plus documented launchd, systemd, and cron recipes.

### Changed

- The README now leads with the complete check-to-verification workflow and the project's own
  evidence-backed OSS catalog.
- CI now verifies deterministic catalog regeneration, strict static output, local links, search
  probes, and the absence of third-party runtime resources.

### Security

- GitHub mutation is additive-only, exact-fingerprint bound, drift checked, TTY required, and
  refused in CI. No code path can unstar, remove membership, delete or rename a List, or expose a
  private repository.
- Public export constructs only allowlisted fields and rejects path, symlink, credential-like,
  private-data, and hostile Markdown/HTML leakage.
- Scheduled upkeep has read-only repository access and no personal credential or model call.

## [0.1.0] - 2026-09-17

### Added

- Deterministic `checked`, `saved`, `remembered`, `rechecked`, and planning-only `used` flows.
- Fixture and optional read-only GitHub discovery with typed evidence and stable receipts.
- Hard gates, typed filters, JMESPath expressions, explanations, canonical ordering, and result fingerprints.
- Profile-scoped external state, immutable decisions, last-known-good revalidation, and read-only projection plans.
- Public reuse receipts, schemas, synthetic fixtures, packaging, CI, security checks, SBOM, and release provenance.

[Unreleased]: https://github.com/pradeeptathineni/shoulda-used-that/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/pradeeptathineni/shoulda-used-that/releases/tag/v0.3.0
[0.2.0]: https://github.com/pradeeptathineni/shoulda-used-that/releases/tag/v0.2.0
[0.1.0]: https://github.com/pradeeptathineni/shoulda-used-that/releases/tag/v0.1.0
