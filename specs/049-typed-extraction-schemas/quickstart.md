# Quickstart: typed document-extraction schema registry

## Resolve a schema

```python
from doc_transcribe import schema_for, SCHEMA_VERSION, supported_types

schema = schema_for("danfe")          # canonical key
schema = schema_for("NF-e")           # alias → danfe
schema = schema_for("something else") # unknown → outro fallback (never raises)
supported_types()                     # ('danfe','nfse','boleto','recibo','comprovante_pagamento','outro')
```

## Validate a transcription

```python
from doc_transcribe import validate_transcription

payload = {
    "doc_type": "nfse",
    "schema_version": "1",
    "raw_text": "... full page text ...",
    "numero": "12345",
    "valores": {"valor_servico": 320.0, "valor_liquido": 320.0, ...},
    ...
}
errors = validate_transcription(payload, "nfse")
assert errors == []          # valid
```

`errors` is a list of located strings like `"$.valores.valor_liquido: expected number or null, got str"`; empty means valid.

## Run the tests

From the repo root (Python via `uv`):

```bash
uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools
```

> The directory is `tools/doc_transcribe/` (underscore) so it is a valid importable Python package; the design doc's `tools/doc-transcribe/` spelling is the same module.

This runs: registry resolution/fallback/aliases, validator positive+negative cases, each example fixture validating against its schema, and the structured-output subset checker over every registered schema.

## What this is / is NOT

- **IS**: the typed JSON-Schema contract (6 schemas), a registry with `outro` fallback + alias map, a stdlib-only validator, and `SCHEMA_VERSION`.
- **IS NOT**: a transcriber (EXTRACT-002/003), deterministic mappers (EXTRACT-005), a persistence/`record-classification` change (EXTRACT-004), or a UI change (EXTRACT-006). It changes no DB schema and adds no dependency.
