# GitHub curation operator runbook

This runbook is for the only live mutation kind supported in `v0.2.0`: an explicitly approved,
sealed `github-curation` plan. It never authorizes a Star or List change by itself.

## Safety model

The executor can perform only three additive operations, in this order:

1. create an exact public List when it does not exist;
2. star an exact public repository when it is not already starred; and
3. add that starred repository to the union of its current and approved List memberships.

There is no command path for unstar, membership removal, List deletion, rename, privacy change,
private-repository projection, replacement synchronization, or CI execution. GitHub's membership
mutation accepts a set, so the adapter reads current memberships immediately before a write and
sends their union with the approved IDs.

## 1. Prepare without mutation

Use the same private state profile for compilation, projection, apply, and verify:

```console
uv run shoulda --profile personal --format json \
  curated curation/profiles/shoulda-used-that.json

uv run shoulda --profile personal --format markdown \
  projected cur_REPLACE_WITH_CURRENT_ID \
  --to github-lists \
  --account pradeeptathineni
```

`projected` performs reads only. If the capability receipt reports a missing scope or unavailable
preview, stop. Follow an operator command only after inspecting it; ShouldaUsedThat never refreshes
authentication, requests a token, or runs `gh auth token` on the user's behalf. After any account,
scope, source, or target-state change, discard the old plan and project again.

## 2. Seal the human approval

Before the first live change, show the complete newly rendered plan and obtain approval that names
all of the following together:

- exact GitHub login and immutable account node ID;
- plan ID and full `plan_…` fingerprint;
- creation time, expiry, and source GitHub-state fingerprint;
- total operation count and the create-List, star, and membership caps;
- every List title and exact public description;
- every repository to be starred;
- every repository-to-List membership to be added; and
- the statement that unrelated existing stars, Lists, and memberships are preserved.

Approval of a prior or summarized plan is not approval of a replacement. Any drift requires a
fresh plan and a fresh exact approval. For the first canary, generate a plan containing one List
and one already-starred public repository; expanding beyond that canary requires another reviewed
plan.

## 3. Apply interactively

Only after exact approval, from a real terminal outside CI:

```console
uv run shoulda --profile personal --format json \
  apply gcp_REPLACE_WITH_APPROVED_ID \
  --fingerprint plan_REPLACE_WITH_FULL_APPROVED_FINGERPRINT
```

The command rechecks the fingerprint, expiry, caps, TTY/CI boundary, authenticated identity,
GitHub capability, complete relevant state, and material drift before its first write. It records
each attempt. List-create and star classes receive complete remote readbacks; membership writes
advance only when GitHub returns the exact requested List union and repository identity. A final
complete remote Star-and-List replay is mandatory before the apply can be marked complete. A
nonzero exit or partial receipt is not permission to start over.

## 4. Verify independently

Use the exact apply receipt ID:

```console
uv run shoulda --profile personal --format json \
  verify app_REPLACE_WITH_ID
```

`verify` performs fresh reads of identity, target-state integrity, public List names/descriptions,
stars, memberships, preserved memberships, and capability. Success requires a `verified` receipt,
not merely a zero exit from the mutation transport.

## Partial or indeterminate execution

- Keep the append-only apply and operation receipts.
- Do not delete or rename anything as an automatic rollback.
- For an indeterminate create, inspect readback before retrying; the executor refuses an uncertain
  duplicate create.
- Resume only with the same plan and full fingerprint. Satisfied operations become no-ops, while
  target changes outside the allowed progress relation block continuation.
- If an operator wants cleanup, treat it as a separate destructive request outside this release.

## Audit handoff

Retain the plan, pre-state fingerprint, operation receipts, apply receipt, and final verify receipt
together in the private state directory. Public catalog content may cite reviewed decisions, but it
must not publish viewer payloads, credential/scope details, private repositories, or personal notes.
