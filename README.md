# ShouldaUsedThat

**Know what to reuse, what to skip, and what is genuinely left to build.**

ShouldaUsedThat turns one concrete software problem into an evidence-backed decision: which
projects fit, what their limits are, and what custom work remains justified.

[See the reviewed build decisions](https://pradeeptathineni.github.io/shoulda-used-that/curation/).

## A real decision

For a reproducible quality gate around a typed Python CLI:

- **Use `uv`** for the locked environment, execution, and builds.
- **Use `pytest`** for readable behavior and contract tests.
- **Use CodeQL** for hosted source analysis and SARIF reporting.

None of them defines supported versions, typed postconditions, coverage targets, or complete gate
ordering. Compose the mature tools; keep that repository-specific policy explicit. [Read the
decision and its evidence](docs/curation/briefs/reproducible-python-quality-gate.md).

## Use the deterministic research CLI

ShouldaUsedThat does not silently translate prose into search. You supply the exact sources,
queries, filters, and ordering; the problem text remains context.

Prerequisites are Python 3.12–3.14 and [`uv`](https://docs.astral.sh/uv/):

```console
git clone https://github.com/pradeeptathineni/shoulda-used-that.git
cd shoulda-used-that
uv sync --all-groups --frozen

uv run shoulda --state-dir .tmp/try-shoulda check \
  "canonical JSON for immutable receipts" \
  --source fixture \
  --fixture fixtures/candidates.json \
  --language Python \
  --license Apache-2.0 \
  --not-archived
```

Normal output shows at most five candidates, distinguishes filtering from the result limit, and
points to inspection. `--explain` shows candidate-level exclusions; `--format json` preserves the
complete authoritative receipt.

The research tasks are:

```text
check → inspect → remember → recheck
 find    inspect    decide     revisit
```

The old `saved` and `used` lifecycle commands are retired: a check is already durable, and adoption
planning is outside the prior-art job. Existing JSON remains readable through the read-only
`shoulda_used_that.legacy` module. Catalog publication and additive GitHub curation use the
discoverable `shoulda catalog` and `shoulda github` groups and are not product prerequisites.

## How it works

- Repository observations are reusable evidence.
- A contextual assessment belongs to one `problem × candidate` relation.
- A brief selects three to five assessed candidates, gives each a problem-specific action, and
  states what is already covered and what remains unresolved.
- Screened-only candidates remain in machine-readable evidence without receiving rich pages.
- JSON and RFC 8785 canonical bytes remain authoritative for hashed state; Markdown, terminal
  tables, and the site are validated renderings.

No model supplies runtime facts, filters, hashes, decisions, state transitions, or mutation plans.
State lives in the operating system's user-data directory unless `--state-dir` is explicit.

## Trust and internals

- [Product contract](docs/architecture/product-contract.md)
- [Guided CLI journey](docs/getting-started.md)
- [Machine-readable public evidence](docs/curation/catalog.json)
- [Implementation and safety contract](docs/architecture/implementation-brief.md)
- [Maintainer GitHub curation runbook](docs/operations/github-curation.md)
- [Contributing and validation](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

Apache-2.0. See [LICENSE](LICENSE).
