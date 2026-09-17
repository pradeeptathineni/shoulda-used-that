# JSON Schemas

Use these Draft 2020-12 schemas to validate ShouldaUsedThat's portable JSON without importing the
Python package. They are generated from the authoritative Pydantic models.

```console
# Regenerate after an intentional model change.
uv run python scripts/generate_schemas.py

# Verify that committed schemas still match the models.
uv run python scripts/generate_schemas.py --check
```

The JSON state models are authoritative. These files document and validate interchange; they do not
replace RFC 8785 canonicalization when a receipt or result-set fingerprint is computed.
