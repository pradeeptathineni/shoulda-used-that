# ShouldaUsedThat

**Before you build, get an evidence-backed brief on the open-source landscape.**

Know what already covers your software idea, where those approaches stop, and what may still be
worth building.

[Explore the prior-art briefs](https://pradeeptathineni.github.io/shoulda-used-that/curation/).

## A tiny real brief

For a deterministic local Python research core, the reviewed landscape already supplies:

- **Click** for mature command parsing and help;
- **Pydantic** for strict versioned records and JSON Schema;
- **JMESPath** for safe expressions over a documented view;
- **rfc8785.py** for standards-based canonical JSON bytes.

Those pieces cover the foundation. They do not own the problem-specific research plan, evidence
gates, state transitions, or the compact human answer. That residual is the part still worth
building here. [Read the evidence-backed brief](docs/curation/briefs/deterministic-python-research-core.md).

## Use the deterministic research CLI

ShouldaUsedThat does not silently translate prose into search. You supply the exact sources,
queries, filters, and ordering; the problem text remains context.

Prerequisites are Python 3.12–3.14 and [`uv`](https://docs.astral.sh/uv/):

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
  --not-archived
```

Normal output shows at most five candidates, distinguishes filtering from the result limit, and
points to inspection. `--explain` shows candidate-level exclusions; `--format json` preserves the
complete authoritative receipt.

The public research tasks are:

```text
checked → inspected → remembered → rechecked
 find       inspect      decide       revisit
```

Compatibility commands for saved findings and adoption plans remain callable but are no longer
part of the core journey. GitHub catalog projection and additive mutation remain maintainer tools,
not product prerequisites.

## How it works

- Repository observations are reusable evidence.
- A contextual assessment belongs to one `problem × candidate` relation.
- A brief selects three to five assessed candidates, then states what appears covered and what
  remains unresolved.
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
