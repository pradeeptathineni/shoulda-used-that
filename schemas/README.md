# JSON Schemas

These Draft 2020-12 schemas are generated from the authoritative Pydantic models. Regenerate with
`uv run python scripts/generate_schemas.py`; verify drift with
`uv run python scripts/generate_schemas.py --check`.

The JSON state models are authoritative. These files document and validate interchange; they do not
replace RFC 8785 canonicalization when a receipt or result-set fingerprint is computed.
