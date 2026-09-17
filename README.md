# ShouldaUsedThat

**Turn “Shit, I shoulda used that” into “Glad I checked first.”**

ShouldaUsedThat is a deterministic-first, AI-optional coordinator that discovers, vets,
remembers, and revalidates existing OSS before you write more code. It turns one named need into a
replayable chain: **check → decision → adoption or curation → sealed projection → independent
verification**.

The local-first CLI now compiles evidence-bound OSS catalogs, inspects explicit projects and
standards-based SBOMs, and can prepare narrowly additive GitHub Stars/List operations. Stars are
bookmarks, not adoption evidence. Recommendations apply to the stated need and context; they are
not a universal “best OSS” ranking.

## Status

This source tree is version `0.2.0`. Verified distributions are published only through
[GitHub Releases](https://github.com/pradeeptathineni/shoulda-used-that/releases); PyPI remains
intentionally unused. This version adds deterministic project inspection, versioned curation
snapshots, an allowlisted public catalog, and additive-only GitHub projection machinery. No
personal Star or List change was needed for the release: the first live change remains blocked
until the maintainer approves the exact newly sealed account, fingerprint, operations, and caps.

Browse the [live public catalog](https://pradeeptathineni.github.io/shoulda-used-that/curation/),
the committed [Markdown source](docs/curation/index.md), [canonical JSON](docs/curation/catalog.json),
[freshness ledger](docs/curation/freshness.md), and
[source/attribution inventory](docs/curation/sources.md). The site remains complete even when
personal GitHub List projection is disabled.

## Install for development

Prerequisites are Python 3.12–3.14, [`uv`](https://docs.astral.sh/uv/), Git, and the official
[`gh`](https://cli.github.com/) CLI for live read-only GitHub sources.

```console
git clone https://github.com/pradeeptathineni/shoulda-used-that.git
cd shoulda-used-that
uv sync --all-groups
uv run shoulda --help
```

No PyPI publication is planned. Release wheels and source archives belong only to verified GitHub
releases.

## Check before building

Start with an explicit source. This fixture example works without GitHub authentication:

```console
uv run shoulda \
  --state-dir .tmp/example-state \
  --format json \
  checked "canonical JSON for immutable receipts" \
  --source fixture \
  --fixture fixtures/candidates.json \
  --language Python \
  --license Apache-2.0 \
  --not-archived \
  --sort stars \
  --sort repo \
  --explain-filter
```

Live GitHub reads are always explicit:

```console
uv run shoulda checked "canonical JSON" \
  --source github-search \
  --query 'canonical json language:Python archived:false' \
  --not-archived
```

Continue the receipt chain with explicit, named inputs:

```console
# Save the exact visible set from a named check; this is local and idempotent.
uv run shoulda saved --all --from chk_REPLACE_WITH_ID

# Record a revisitable decision.
uv run shoulda remembered trailofbits/rfc8785.py \
  --as adopt \
  --for "RFC 8785 canonical bytes" \
  --because "small standards-focused adapter" \
  --reconsider-when "published vectors fail"

# Replay a stored check's bound source policy.
uv run shoulda rechecked chk_REPLACE_WITH_ID

# Produce a planning-only adoption record; this never writes the target.
uv run shoulda used trailofbits/rfc8785.py \
  --for "RFC 8785 canonical bytes" \
  --in another-project \
  --postcondition "published vectors pass" \
  --rollback "remove the dependency and adapter"

# Compile the reviewed public profile, then export only its allowlisted fields.
uv run shoulda --format json curated curation/profiles/shoulda-used-that.json
uv run shoulda --format json exported cur_REPLACE_WITH_ID \
  --public \
  --output .tmp/public-catalog

# Read current GitHub state and seal a plan. This command does not mutate GitHub.
uv run shoulda --format json projected cur_REPLACE_WITH_ID \
  --to github-lists \
  --account pradeeptathineni

# Apply remains interactive, additive-only, expiry/cap checked, and exact-fingerprint bound.
uv run shoulda apply gcp_REPLACE_WITH_ID --fingerprint plan_REPLACE_WITH_FINGERPRINT
uv run shoulda verify app_REPLACE_WITH_ID
```

JSON is the authoritative machine output. YAML and Markdown are validated renderings; terminal
tables are human summaries. Runtime state defaults to the operating system's user-data location
and can be isolated with `--state-dir` and `--profile`.

## What ShouldaUsedThat uses

| Role | Evidenced implementation |
| --- | --- |
| Runtime | Click, Pydantic, JMESPath, platformdirs, PyYAML, Rich, and RFC 8785 canonical JSON |
| Development | uv, pytest, Hypothesis, coverage.py, Ruff, strict mypy, and pre-commit |
| CI and security | GitHub Actions, CodeQL, dependency review, actionlint, zizmor, and Scorecard |
| Catalog | Generated Markdown/JSON with a pinned, replaceable Zensical development trial |
| Release | Hatchling, CycloneDX, checksums, GitHub Releases, and artifact attestations |

The full role, version, boundary, alternative, and removal evidence is in
[What ShouldaUsedThat uses](docs/curation/in-use.md) and the
[facet-by-facet reuse gate](docs/architecture/dogfood-reuse-audit.md).

## Semantics that fail closed

- Hard gates run before optional filters. Unknown hard facts are excluded; unknown soft facts stay
  visible unless explicitly filtered.
- Repeated values for one field are OR; different fields are AND. JMESPath runs only over the
  documented canonical candidate view.
- Ordering always has canonical `owner/repo` identity as its final tie-breaker.
- `saved --all` is bound to one stored post-filter fingerprint. It never means “whatever is current
  now.”
- A failed recheck preserves the last-known-good baseline and reports the source failure.
- Receipts are immutable. Changed judgment creates a new receipt that explicitly supersedes the
  earlier one.
- `v0.2.0` permits `apply` only for an approved, sealed, additive `github-curation` plan and uses
  `verify` for independent readback; destructive, silent, expired, drifted, non-interactive, or CI
  execution remains forbidden.

## Public evidence

- [Implementation contract](docs/architecture/implementation-brief.md)
- [Curated OSS coordinator expansion](docs/architecture/curation-v0.2.md)
- [Generated public catalog](docs/curation/index.md)
- [Facet-by-facet reuse gate](docs/architecture/dogfood-reuse-audit.md)
- [Prior-art and decision receipts](docs/decisions/README.md)
- [Context-engineering receipt](docs/development/context-receipt.md)
- [Executed SBOM comparison](docs/development/sbom-comparison.md)
- [Catalog scale validation](docs/development/catalog-scale-validation.md)
- [GitHub curation operator runbook](docs/operations/github-curation.md)
- [Read-only upkeep and scheduling](docs/operations/scheduling.md)
- [v0.2.0 correctness and security review](docs/development/review-v0.2.0.md)
- [v0.1.0 correctness and security review](docs/development/review-v0.1.0.md)
- [Contributing and validation](CONTRIBUTING.md)
- [Security policy and boundaries](SECURITY.md)

The receipts distinguish discovered claims from executed evidence and include explicit
reconsideration triggers. Repository history, hosted checks, the annotated release tag, and the
release assets form the VCS/release-chain evidence rather than being treated as incidental
maintenance.

## License

Apache-2.0. See [LICENSE](LICENSE).
