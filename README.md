# ShouldaUsedThat

**Before you build, get an evidence-backed brief on the open-source landscape.**

ShouldaUsedThat helps a software builder answer one concrete build question: what established
options already cover it, what deserves caution, and what remains unresolved before choosing to
adopt, adapt, combine, or build.

The intended human product is a compact prior-art brief, not a repository directory. The current
release supplies the deterministic CLI, immutable evidence workflow, screened public corpus, and
explicit problem-by-repository assessments beneath that product. It does not claim that every
screened candidate has contextual fit evidence.

## Start here

| Goal | Path |
| --- | --- |
| Inspect the current backing evidence and assessed self-use examples | [Explore the public evidence](https://pradeeptathineni.github.io/shoulda-used-that/curation/) |
| Complete one deterministic workflow without a GitHub login | [Run the fixture journey](#try-a-check-without-a-github-login) |
| Understand the product and evidence boundary | [Read the product contract](docs/architecture/product-contract.md) |

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

The result shows what stayed visible, why filters removed other candidates, and the exact receipt
you can save or revisit. Continue with the [guided CLI journey](docs/getting-started.md).

## Deterministic workflow

```text
checked  →  saved  →  remembered  →  rechecked  →  used
 find        keep       decide         revisit       plan adoption
```

- `checked` reads explicit sources and records the exact post-filter result.
- `saved` keeps findings locally without starring or changing a GitHub List.
- `remembered` records a decision, rationale, unknowns, and reconsideration trigger.
- `rechecked` repeats the bound source policy and reports meaningful differences.
- `used` writes a planning-only adoption record; it never edits the target project.

An advanced `curated → exported → projected → apply → verify` path maintains the public evidence
and additive GitHub views. Only `apply`, after exact interactive approval of an unexpired sealed
plan, can add stars, create Lists, or add memberships. It cannot unstar, remove membership,
delete or rename Lists, change privacy, run in CI, or edit a target repository.

## Evidence boundary

- Repository observations are reusable facts: identity, description, license, archive state,
  release or commit observations, popularity, provenance, and dates.
- Domains are taxonomy and filters.
- Contextual judgment belongs to a concrete `problem × repository` assessment.
- **Screened** means a candidate was worth retaining from source, metadata, and eligibility
  evidence. **Assessed** means reviewed contextual evidence exists for a concrete problem.
- Metadata screening never creates a fit claim.

JSON is authoritative for hashed state; YAML, Markdown, terminal tables, and the public site are
validated views. Runtime state lives in the operating system's user-data directory unless you set
`--state-dir`. AI may help review wording, but never supplies facts, filters, hashes, decisions,
state transitions, or mutation plans.

## More detail

- [Product contract](docs/architecture/product-contract.md)
- [Public evidence corpus](docs/curation/index.md) and [canonical JSON](docs/curation/catalog.json)
- [Implementation and safety contract](docs/architecture/implementation-brief.md)
- [Operator runbook](docs/operations/github-curation.md)
- [Decision evidence](docs/decisions/README.md)
- [Contributing and full validation](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [v0.3.0 release notes](docs/releases/v0.3.0.md)

Apache-2.0. See [LICENSE](LICENSE).
