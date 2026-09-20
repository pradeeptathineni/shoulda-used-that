# Contributing

Contributions are welcome when they make an existing choice easier to find, a decision easier to
revisit, or a safety boundary easier to verify. Start by naming the reader or operator problem the
change solves.

## Set up and validate

Use Python 3.12–3.14, `uv`, and Vale 3.21.0:

```console
uv sync --all-groups --frozen
./scripts/check.sh
```

The full check formats nothing and writes no external state. Catalog-only changes must also leave
`./scripts/upkeep_catalog.sh` as an immediate semantic no-op.

## Keep public writing reader-first

Reader-facing changes must pass `./scripts/review_public_writing.sh`. Material changes to the
README, homepage, catalog landing pages, or CLI journey also need the context-free First Reader and
local ZeroSlop passes described in the
[`public writing quality loop`](docs/architecture/public-writing.md). Review generated catalogs at
the generator, schema, representative-output, and deterministic-diff boundary; do not rewrite an
upstream project's description to fit this project's voice.

## Protect the product boundary

Changes to a command contract, production dependency, state format, GitHub adapter, workflow, or release tool need a current prior-art receipt under `docs/decisions/`. Keep fixtures public or synthetic. Never add personal state, private repository material, credentials, or another project's files.

Open an issue for behavior changes that alter a hard gate, receipt schema, or mutation boundary.
Keep publication under `shoulda catalog` and GitHub orchestration under `shoulda github`; research
commands must not import or reach mutation services. Never use a personal PAT in repository
workflows or schedule `shoulda github apply`. Security reports follow
[`SECURITY.md`](SECURITY.md).
