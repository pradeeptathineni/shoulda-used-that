# Public implementation contract

ShouldaUsedThat is a local-first CLI and library for answering a narrow question: for this need, which existing open-source candidates survive explicit evidence gates, and what should happen next?

## `v0.1.0` released boundary

Version `0.1.0` implements five read/reason/record flows:

- `checked` discovers from explicit fixture, GitHub star, GitHub search, or exact-repository sources; normalizes evidence; applies gates and filters; and writes an immutable check receipt.
- `saved` records exact candidates locally. `saved --all` is bound to one stored post-filter result fingerprint.
- `remembered` writes immutable adopt, trial, reference, learn, watch, reject, or build receipts.
- `rechecked` replays a stored evidence policy, preserves last-known-good evidence on source failure, and classifies typed differences.
- `used` writes an adoption plan without touching the target.

`apply` and `verify` expose fixture-safe plan validation only. There is no live star, List, or target-write implementation in this release.

The immutable `v0.1.0` GitHub release was published on 2026-09-17 after the tagged commit passed
the hosted CI, security, package, checksum, SBOM, and attestation gates.

## `v0.2.0` boundary

Version `0.2.0` grows the thin core into a local-first curation control plane. It adds explicit
project/SBOM snapshots, deterministic curation profiles and snapshots, read-only public and viewer
Stars/Lists adapters, sealed additive GitHub projection plans, a narrowly scoped apply/verify
executor, allowlisted public catalog export, and one-shot material rechecks. The complete public
contract is [`curation-v0.2.md`](curation-v0.2.md).

GitHub remains the native public star/List surface. Canonical ShouldaUsedThat receipts remain the
evidence ledger, and generated Markdown/JSON plus the static site remain replaceable derived views.
No model, crawler, database, hosted backend, analytics service, or package-registry publication is
introduced.

## `v0.3.0` reader-surface release

Version `0.3.0` keeps the `v0.2.0` runtime, state, and mutation boundaries. It changes how people
enter the product: browsing, a no-authentication fixture check, and verified-wheel installation
are explicit first steps; command help and generated catalog pages lead with the reader's question
before showing operator evidence. First Reader and ZeroSlop are review techniques, not runtime
dependencies or authorities.

## Post-`v0.3.0` brief-first boundary

The primary reader unit is now a prior-art brief for one concrete build problem. A brief selects
three to five explicit `problem × repository` assessments, shows candidate-specific `covers` plus
`watch` or uncertainty, and states what appears covered and what remains unresolved. Screened
repository evidence remains complete in canonical JSON, but screened-only candidates do not receive
rich reader pages.

The ordinary `shoulda` journey is `check → inspect → remember → recheck`. `check` treats the
problem text as context and executes only explicit sources and queries, preserves upstream source
positions separately from local ordering, defaults to five visible results, aggregates exclusions,
and diagnoses zero-result categories without broadening the plan. JSON and YAML retain the complete
receipt. The `saved` and `used` creation flows are retired. Catalog publication lives under
`shoulda catalog`; GitHub planning, apply, and verification live under `shoulda github`. Their
implementation is imported only when one of those operational commands is invoked.

## State and identity

Runtime state lives under an OS data directory selected by `platformdirs`, or under an explicit
`--state-dir`. Profiles do not share latest-check pointers or decisions. State is JSON validated by
versioned Pydantic models and hashed with RFC 8785 canonical JSON. Receipts are immutable; a later
receipt may supersede an earlier one. Retired save, List-preview, and adoption-plan files are never
rewritten or deleted; `shoulda_used_that.legacy` validates them read-only while immutable release
tags preserve their original schemas.

Canonical repository identity is lowercase `owner/repo`. Source payload fingerprints, result-set fingerprints, and plan fingerprints use SHA-256 over the canonical JSON bytes. YAML and Markdown are views, never hash inputs.

## Filtering

Repeated values of one field are OR. Different fields are AND. Exclusions and hard gates run first. Unknown license, archival, privacy, platform, or runtime evidence fails a requested hard gate; unknown soft evidence stays visible unless explicitly filtered. JMESPath evaluates only the stable canonical candidate view after native-source pushdown, and all pushed predicates are re-evaluated locally. Stable canonical identity is the last sort key.

Every result preserves its normalized predicate tree, unknown policy, pushdown note, counts, and candidate-level reasons.

## Privacy and mutation

Public export is an allowlist of reusable fields. It excludes local paths, state-root paths,
credentials, raw private payloads, and personal profile data. GitHub transport shells out only
through an argument vector to the installed `gh` CLI, uses existing keyring authentication, and
never requests or logs a token.

The maintainer-only mutation adapter is intentionally smaller than the read transport. It can create an
exact public List, star an exact public repository, and add that repository to the union of its
current and approved memberships only after an exact sealed-plan fingerprint passes identity,
capability, expiry, cap, drift, TTY, and CI checks. Independent readback is mandatory. There is no
unstar, removal, delete, rename, privacy-change, private-repository, or scheduled mutation route.

## Explicit exclusions

No web application, hosted service, crawler, vulnerability scanner, vector index, daemon,
scheduling framework, runtime model, generic recommendation score, package-registry publication,
automatic code change, destructive GitHub mutation, unattended personal mutation, or target
remediation belongs in the current scope. The static Pages catalog and deterministic OS/Actions scheduling
recipes do not change those boundaries.
