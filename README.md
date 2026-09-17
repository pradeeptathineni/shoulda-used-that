# ShouldaUsedThat

**Before you build another tool, check what open source already exists and what the evidence says.**

ShouldaUsedThat helps you find credible options for a specific need, record why one fits, and
notice when the evidence changes. It turns “I should have used that” from a late discovery into an
early, repeatable check.

## Pick your quickest path

| If you want to… | Start here | What you get |
| --- | --- | --- |
| Find useful OSS now | [Browse the public catalog](https://pradeeptathineni.github.io/shoulda-used-that/curation/) | 222 reviewed records grouped by the needs they serve |
| See the workflow without a GitHub login | [Run the local fixture check](#try-a-check-without-a-github-login) | A deterministic, filterable result and its receipt |
| Use the CLI | [Install the verified release](#install-the-cli) | The signed-off `shoulda` command from GitHub Releases |

The public catalog is the best first look. Try a collection, open an entry, and read its **need**,
**why**, evidence date, and reconsideration trigger. “Reviewed” means the entry passed its stated
metadata and fit checks; it is not a code audit, security approval, or universal ranking. A GitHub
star is only a bookmark.

## Install the CLI

Prerequisites are Python 3.12–3.14 and [`uv`](https://docs.astral.sh/uv/). Install the wheel from
the immutable `v0.3.0` GitHub release:

```console
uv tool install https://github.com/pradeeptathineni/shoulda-used-that/releases/download/v0.3.0/shoulda_used_that-0.3.0-py3-none-any.whl
shoulda --help
```

PyPI is intentionally unused. Every GitHub release includes the wheel, source archive, checksums,
runtime SBOM, and artifact attestations.

## Try a check without a GitHub login

Clone the repository, install its locked environment, and query the public fixture:

```console
git clone https://github.com/pradeeptathineni/shoulda-used-that.git
cd shoulda-used-that
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

You see what stayed visible, what each filter removed, and the `chk_…` receipt ID you can use next.
Continue with the [guided CLI journey](docs/getting-started.md), or run a live,
read-only GitHub search when you are ready.

## From question to revisitable decision

```text
checked  →  saved  →  remembered  →  rechecked  →  used
 find        keep       decide         revisit       plan adoption
```

- `checked` finds candidates from explicit sources and records the exact visible result.
- `saved` keeps chosen findings locally without starring or changing a GitHub List.
- `remembered` records the decision, rationale, unknowns, and trigger to reconsider it.
- `rechecked` repeats the bound source policy and reports meaningful differences.
- `used` writes a planning-only adoption record; it never edits the target project.

For catalog maintainers, a separate `curated → exported → projected → apply → verify` path builds
the public catalog and, only after exact interactive approval, performs additive GitHub curation.
The [operator runbook](docs/operations/github-curation.md) owns that advanced path.

## What makes it safe to revisit

ShouldaUsedThat is deterministic and local-first. JSON is authoritative for hashed state; YAML,
Markdown, and terminal tables are validated views. Runtime state lives in the operating system's
user-data directory unless you choose `--state-dir`.

- Unknown hard-gate facts fail closed; optional unknowns stay visible unless filtered.
- Every result has a stable final `owner/repo` tie-breaker.
- `saved --all` stays bound to one immutable post-filter result.
- A source error cannot replace the last-known-good evidence.
- Changed judgment creates a new receipt that names the receipt it supersedes.
- Live GitHub writes are limited to an approved, unexpired, exact-fingerprint additive plan.
  ShouldaUsedThat cannot unstar, remove membership, delete or rename a List, change List privacy,
  run mutation in CI, or edit a target repository.

AI may help review public wording, but it never supplies facts, filters, hashes, decisions, state
transitions, or mutation plans.

## The project uses its own method

The repository builds its site and GitHub Lists from the same reviewed public profile. Its current
catalog contains 222 records across 12 collections. The latest recorded live projection completed
438 additive operations, then independently verified 488 initial postconditions with no
mismatches; a later semantic no-op verified all 730 then-current postconditions. Read the
[self-use story](docs/curation/dogfood.md) for the human explanation and the
[live projection evidence](docs/operations/live-projection.md) for the exact boundary.

The toolchain itself is also accounted for. See [what is used here](docs/curation/in-use.md) and
the [facet-by-facet reuse gate](docs/architecture/dogfood-reuse-audit.md) for roles, alternatives,
and removal conditions.

## Go deeper

- [Getting started and command map](docs/getting-started.md)
- [Public catalog](docs/curation/index.md) and [canonical JSON](docs/curation/catalog.json)
- [Implementation and safety contract](docs/architecture/implementation-brief.md)
- [Prior-art and decision receipts](docs/decisions/README.md)
- [Public-writing review](docs/development/public-surface-review-v0.3.0.md)
- [Contributing and full validation](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [v0.3.0 release notes](docs/releases/v0.3.0.md)

Apache-2.0. See [LICENSE](LICENSE).
