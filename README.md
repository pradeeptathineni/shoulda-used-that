# ShouldaUsedThat

**Turn “Shit, I shoulda used that” into “Glad I checked first.”**

ShouldaUsedThat is a deterministic-first, AI-optional coordinator that discovers, vets,
remembers, and revalidates existing OSS before you write more code.

`v0.1.0` is local-first and deliberately read-only outside its own private state directory. It can
inspect explicit fixtures or public GitHub data, produce immutable evidence and decision receipts,
and prepare adoption or GitHub List plans. It cannot star a repository, change a List, modify a
target project, run an unattended model, or publish a package.

## Status

This repository is under active `v0.1.0` development. The public contracts and prior-art decisions
are already reviewable, but the release is not complete until the tagged GitHub release and its
hosted checks, SBOM, checksums, and provenance are verified.

## Install for development

Prerequisites are Python 3.12–3.14, [`uv`](https://docs.astral.sh/uv/), Git, and the official
[`gh`](https://cli.github.com/) CLI for live read-only GitHub sources.

```console
git clone https://github.com/pradeeptathineni/shoulda-used-that.git
cd shoulda-used-that
uv sync --all-groups
uv run shoulda --help
```

No PyPI publication is planned for `v0.1.0`. Release wheels and source archives belong only to the
verified GitHub release.

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

The remaining participle commands continue the receipt chain:

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
```

JSON is the authoritative machine output. YAML and Markdown are validated renderings; terminal
tables are human summaries. Runtime state defaults to the operating system's user-data location
and can be isolated with `--state-dir` and `--profile`.

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
- `apply` and `verify` fail closed in `v0.1.0`; no external mutation executor exists.

## Public evidence

- [Implementation contract](docs/architecture/implementation-brief.md)
- [Facet-by-facet reuse gate](docs/architecture/dogfood-reuse-audit.md)
- [Prior-art and decision receipts](docs/decisions/README.md)
- [Context-engineering receipt](docs/development/context-receipt.md)
- [Executed SBOM comparison](docs/development/sbom-comparison.md)
- [v0.1.0 correctness and security review](docs/development/review-v0.1.0.md)
- [Contributing and validation](CONTRIBUTING.md)
- [Security policy and boundaries](SECURITY.md)

The receipts distinguish discovered claims from executed evidence and include explicit
reconsideration triggers. Repository history, hosted checks, the annotated release tag, and the
release assets form the VCS/release-chain evidence rather than being treated as incidental
maintenance.

## License

Apache-2.0. See [LICENSE](LICENSE).
