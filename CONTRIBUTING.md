# Contributing

Use Python 3.12–3.14 and `uv`. Run `uv sync --all-groups --frozen`, then `./scripts/check.sh` before proposing a change.

Changes to a command contract, production dependency, state format, GitHub adapter, workflow, or release tool need a current prior-art receipt under `docs/decisions/`. Keep fixtures public or synthetic. Never add personal state, private repository material, credentials, or another project's files.

Open an issue for behavior changes that alter a hard gate, receipt schema, or mutation boundary. Security reports follow [`SECURITY.md`](SECURITY.md).
