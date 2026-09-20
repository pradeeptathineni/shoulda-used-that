---
title: Run an explicit prior-art check
description: Find, inspect, decide, and recheck with a deterministic research plan.
---

# Run an explicit prior-art check

The CLI is the power-user research path. It executes the sources and queries you name; the problem
text provides context and never silently expands or rewrites retrieval.

## 1. Find candidates

This no-authentication example uses the committed public fixture and writes only to the state
directory you choose:

```console
uv sync --all-groups --frozen
uv run shoulda --state-dir .tmp/try-shoulda checked \
  "canonical JSON for immutable receipts" \
  --source fixture \
  --fixture fixtures/candidates.json \
  --language Python \
  --license Apache-2.0 \
  --not-archived
```

The default answer contains at most five visible candidates, aggregate filter and limit counts,
the upstream source position when one exists, and an exact inspection command. It also writes the
complete immutable check receipt. Use `--explain` for candidate-level exclusions or
`--format json` for all evidence, predicates, ordering, and fingerprints.

Zero results are diagnosed without broadening the plan: no source candidates, all candidates
filtered, or required hard-gate evidence unavailable.

## 2. Inspect one explicit candidate

Live GitHub inspection uses the official `gh` authentication already present on the machine:

```console
uv run shoulda inspected github:trailofbits/rfc8785.py
```

Inspection is read-only. Normal output prioritizes the target's available evidence and typed gaps;
the complete source and SBOM record remains available through `--format json`.

## 3. Record a decision

Use the `chk_` identifier from the check:

```console
uv run shoulda --state-dir .tmp/try-shoulda remembered trailofbits/rfc8785.py \
  --as adopt \
  --for "RFC 8785 canonical bytes" \
  --because "small standards-focused adapter" \
  --reconsider-when "published vectors fail" \
  --from chk_REPLACE_WITH_ID
```

The decision is immutable. If judgment changes, create a new receipt with `--supersedes` rather
than rewriting history.

## 4. Recheck the evidence policy

```console
uv run shoulda --state-dir .tmp/try-shoulda rechecked chk_REPLACE_WITH_ID
```

`rechecked` repeats the stored source policy and classifies material changes. A source error is
recorded without replacing last-known-good evidence.

## Use live discovery when you choose

```console
uv run shoulda checked "canonical JSON identity" \
  --source github-search \
  --query 'canonical json language:Python archived:false' \
  --not-archived
```

The query is exact and its upstream order is preserved separately from local filtering and sorting.
Run `shoulda checked --help` for the filter vocabulary.

## Compatibility and maintainer commands

`saved` and `used` remain callable for existing local workflows but are not part of the core
research journey. Catalog compilation, public export, GitHub projection, `apply`, and `verify` are
maintainer commands documented in the [GitHub curation runbook](operations/github-curation.md).
They are hidden from ordinary root help and retain their existing safety boundaries.
