# Public implementation contract

ShouldaUsedThat is a local-first CLI and library for answering a narrow question: for this need, which existing open-source candidates survive explicit evidence gates, and what should happen next?

## Release boundary

Version `0.1.0` implements five read/reason/record flows:

- `checked` discovers from explicit fixture, GitHub star, GitHub search, or exact-repository sources; normalizes evidence; applies gates and filters; and writes an immutable check receipt.
- `saved` records exact candidates locally. `saved --all` is bound to one stored post-filter result fingerprint.
- `remembered` writes immutable adopt, trial, reference, learn, watch, reject, or build receipts.
- `rechecked` replays a stored evidence policy, preserves last-known-good evidence on source failure, and classifies typed differences.
- `used` writes an adoption plan without touching the target.

`apply` and `verify` expose fixture-safe plan validation only. There is no live star, List, or target-write implementation in this release.

## State and identity

Runtime state lives under an OS data directory selected by `platformdirs`, or under an explicit `--state-dir`. Profiles do not share latest-check pointers, saved items, or decisions. State is JSON validated by versioned Pydantic models and hashed with RFC 8785 canonical JSON. Receipts are immutable; a later receipt may supersede an earlier one.

Canonical repository identity is lowercase `owner/repo`. Source payload fingerprints, result-set fingerprints, and plan fingerprints use SHA-256 over the canonical JSON bytes. YAML and Markdown are views, never hash inputs.

## Filtering

Repeated values of one field are OR. Different fields are AND. Exclusions and hard gates run first. Unknown license, archival, privacy, platform, or runtime evidence fails a requested hard gate; unknown soft evidence stays visible unless explicitly filtered. JMESPath evaluates only the stable canonical candidate view after native-source pushdown, and all pushed predicates are re-evaluated locally. Stable canonical identity is the last sort key.

Every result preserves its normalized predicate tree, unknown policy, pushdown note, counts, and candidate-level reasons.

## Privacy and mutation

Public export is an allowlist of reusable fields. It excludes local paths, state-root paths, credentials, raw private payloads, and personal profile data. GitHub transport shells out only through an argument vector to the installed `gh` CLI, uses existing keyring authentication, and never requests or logs a token. Network mutations are absent from the implementation.

## Explicit exclusions

No web UI, hosted service, crawler, scanner, vector index, scheduler, runtime model, generic recommendation score, package-registry publication, automatic code change, star/unstar, or GitHub List mutation belongs in `v0.1.0`.
