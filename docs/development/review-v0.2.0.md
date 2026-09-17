# v0.2.0 correctness, security, and product review

This review covers the public change from `v0.1.0` through the `v0.2.0` release candidate. It
separates fixture/local evidence, live read-only evidence, hosted evidence, and release-time gates;
a passing item in one class is not reported as proof of another.

## Scope and outcome

The implementation keeps a deterministic residual: explicit project/SBOM context, reviewed
curation records, additive projection planning, narrow apply/verify receipts, and allowlisted public
export. GitHub remains the Stars/Lists authority, SBOM formats remain the inventory interchange,
and Zensical remains a replaceable development-only view adapter.

No production model, agent framework, crawler, database, hosted backend, analytics surface,
personal token, target-write path, or destructive GitHub operation was added. No live personal Star
or List mutation was performed during the review.

## Local and fixture evidence

- The full gate passes on Python 3.14 with 212 tests and the branch-aware 90% coverage threshold.
- Ruff formatting/lint, strict mypy, deterministic JSON Schema generation, repository/privacy
  contracts, actionlint, zizmor, typos, lychee, locked runtime audit, and sdist/wheel build pass.
- Existing `v0.1.0` records remain covered alongside every new schema; unknown schemas fail closed.
- Project-context fixtures cover GitHub/local/SPDX/CycloneDX input, bounded reads, symlink and size
  failure, asynchronous SBOM states, no target writes, and public path redaction.
- Stars/Lists fixtures cover pagination, zero/empty Lists, viewer/public state, missing scope,
  malformed preview data, immutable identity, exact plans, drift, expiry, caps, partial and
  indeterminate apply, retry/resume, membership union, independent readback, CI refusal, and the
  absence of every destructive request.
- Public-export fixtures prove byte-stable replay, immediate no-op, bounded material diff,
  transactional failure, explicit-public input, hidden-collection omission, attribution inventory,
  path/secret/symlink rejection, and hostile HTML/Markdown escaping.
- `./scripts/upkeep_catalog.sh` passes twice without changing `docs/curation`; the same command is
  used by local checks, CI, pull requests, and scheduled public upkeep.

## Catalog and visual evidence

- Strict Zensical 0.0.62 build: 46 HTML pages, no broken local link/fragment, five search probes,
  and zero third-party runtime resources.
- Repository name (`pallets/click`), need text, alias (`DevOps`), disposition (`Trialing`), and
  collection (`Generative AI & Agents`) were exercised through the client search UI.
- Desktop 1280×720 and mobile 390×844 renders were inspected in dark and light/system themes.
  Navigation, cards, status/freshness chips, focusable controls, tables, and intentional empty
  collection states had no observed horizontal overflow or clipped content.
- The final 5,000-entry synthetic run compiled in 1.030 seconds, rendered in 15.563 seconds, built
  strictly in 76.749 seconds, produced a 130,762,772-byte site and 18,430,488-byte search index,
  found all seven probes, and made its second export a semantic no-op.

An early automatic-navigation build embedded the complete entry navigation into every page and
produced 348,071,836 bytes at only 1,000 entries. Explicit index-only navigation reduced the
measured case to 26,833,972 bytes and made the 5,000-entry output approximately linear. Markdown
injection hardening and generated hard-break whitespace were also found and corrected before the
catalog commit.

## Live read-only GitHub evidence

- The authenticated login and immutable node identity matched the explicitly requested account.
- Current public Stars, zero Lists, GraphQL List capability, repository identities, and desired
  state were read through bounded `gh` argument vectors; no token was requested or printed.
- The dogfood projection sealed two proposed public Lists, four missing Stars, and six memberships
  while preserving already-starred repositories and all observed memberships.
- The capability receipt reported that the current session lacked mutation readiness. Apply stayed
  closed, and no authentication refresh or personal mutation was attempted.

The plan is deliberately not a release asset or standing approval. Account/scope/state changes make
it stale; a future first mutation requires a new plan and the exact approval described in the
[operator runbook](../operations/github-curation.md).

## Hosted evidence before the release-preparation commit

Commit `2ab4312e91c9bdb36d9bff929bd9274fb399c392` passed:

- CI run `35202145807`, including Linux Python 3.12–3.14, macOS 3.12, Windows 3.12, quality,
  coverage, package build, and clean install;
- Security run `35202145790`, including workflow checks, dependency review, links, and CodeQL; and
- Catalog and Pages run `35202145841`, where deterministic verification passed and the PR-side
  deployment job correctly skipped.

The final release-candidate commit must repeat those hosted checks. A PR result does not prove a
`main` Pages deployment, and a queued or skipped job is never reported as a pass for another gate.

## Release-time gates

Before the annotated tag is created:

- protected `main` must receive its required independent approval without weakening the rule;
- local branch, `main`, `origin/main`, and the release commit must agree and be clean;
- exact-commit CI, security, Scorecard where triggered, catalog verification, and clean install
  must finish successfully;
- GitHub Pages must deploy from `main`, then the live URL, representative pages, catalog JSON,
  manifest, search asset, and absence of third-party runtime dependencies must be fetched again;
  the deployment job performs this byte-for-byte and search-probe verification itself;
- catalog regeneration must remain a no-op; and
- the annotated `v0.2.0` tag must point at that exact commit.

After the tag workflow completes, the wheel, sdist, runtime CycloneDX SBOM, checksums, release/tag
identity, immutable asset digests, and GitHub attestations must be independently inspected. PyPI
must still contain no `shoulda-used-that` publication. Failure of any item blocks the release claim
without erasing the evidence that did pass.
