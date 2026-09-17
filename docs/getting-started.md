---
title: Get from a need to a revisitable decision
description: A no-authentication walkthrough of the ShouldaUsedThat CLI and its evidence trail.
---

# Get from a need to a revisitable decision

This walkthrough answers a small question: **which existing Python project could provide canonical
JSON bytes for immutable receipts?** It uses a committed public fixture, writes state only to a
temporary directory you choose, and needs no GitHub login.

## 1. Run one evidence-bound check

From a development checkout:

```console
uv sync --all-groups --frozen
uv run shoulda --state-dir .tmp/try-shoulda checked \
  "canonical JSON for immutable receipts" \
  --source fixture \
  --fixture fixtures/candidates.json \
  --language Python \
  --license Apache-2.0 \
  --not-archived \
  --explain-filter
```

The output shows the surviving candidates, why other candidates were removed, and a receipt ID
beginning with `chk_`. Copy that ID for the next step.

## 2. Keep the exact visible result

```console
uv run shoulda --state-dir .tmp/try-shoulda saved --all --from chk_REPLACE_WITH_ID
```

`saved --all` means the exact post-filter set in that receipt. It does not refresh the source,
reach beyond the result, star anything, or change a GitHub List.

## 3. Record the decision in your own words

```console
uv run shoulda --state-dir .tmp/try-shoulda remembered trailofbits/rfc8785.py \
  --as adopt \
  --for "RFC 8785 canonical bytes" \
  --because "small standards-focused adapter" \
  --reconsider-when "published vectors fail" \
  --from chk_REPLACE_WITH_ID
```

The decision is immutable. If your judgment changes, create a new receipt with `--supersedes`
instead of rewriting history.

## 4. Ask what changed

```console
uv run shoulda --state-dir .tmp/try-shoulda rechecked chk_REPLACE_WITH_ID
```

`rechecked` repeats the source policy stored with the receipt and classifies meaningful changes. A
source failure is reported without replacing the last-known-good evidence.

## 5. Describe adoption without touching the target

```console
uv run shoulda --state-dir .tmp/try-shoulda used trailofbits/rfc8785.py \
  --for "RFC 8785 canonical bytes" \
  --in another-project \
  --postcondition "published vectors pass" \
  --rollback "remove the dependency and adapter"
```

This is a plan, not an installer. It records what success and rollback would mean and never writes
to `another-project`.

## Command map

| Command | Human question | Network or write boundary |
| --- | --- | --- |
| `inspected` | What public or supplied evidence does one project expose? | Explicit target; read-only |
| `checked` | What matches this need and these gates? | Explicit sources; read-only |
| `saved` | Which exact findings should I keep? | Local state only |
| `remembered` | What did I decide, why, and when should I reconsider? | Local state only |
| `rechecked` | Has meaningful evidence changed? | Replays the bound source policy |
| `used` | How could I adopt this, prove it worked, and undo it? | Planning only; never edits the target |

Catalog maintenance has its own advanced path: `curated` compiles a profile, `exported` writes an
allowlisted site, and `projected` seals a plan without mutation. Only `apply` can perform live
GitHub changes, and only for an approved, unexpired, exact-fingerprint additive plan in an
interactive terminal. `verify` then reads every claimed postcondition back independently. Use the
[GitHub curation runbook](operations/github-curation.md) before that path.

## Use live GitHub discovery when you choose

The official `gh` CLI must already be authenticated for live sources:

```console
uv run shoulda checked "canonical JSON" \
  --source github-search \
  --query 'canonical json language:Python archived:false' \
  --not-archived
```

The source is explicit; the command does not silently broaden to your Stars or refresh another
receipt. Run `shoulda checked --help` for the complete filter vocabulary and `shoulda --help` for
the whole journey.
