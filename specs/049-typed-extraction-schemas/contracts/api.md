# Contract: registry + validator public API

Module: `tools/doc-transcribe` (importable as `doc_transcribe` when `tools/` is on the path, or by file path). **Zero imports from `scripts/analysis`.**

## Constants

```python
SCHEMA_VERSION: str = "1"
DOC_TYPES: tuple[str, ...] = (
    "danfe", "nfse", "boleto", "recibo", "comprovante_pagamento", "outro",
)
ALIASES: dict[str, str]   # e.g. {"comprovante": "comprovante_pagamento", "nf-e": "danfe", ...}
```

## Registry (`registry.py`)

```python
def schema_for(doc_type: str | None) -> dict:
    """Return the JSON Schema (dict) for doc_type.
    Resolves via ALIASES + case/space-insensitive match; an unknown/None type
    returns the `outro` fallback schema. NEVER raises on an unknown type."""

def load_schema(doc_type: str) -> dict:
    """Load a canonical-keyed schema by exact key. Raises KeyError only for a
    key not in DOC_TYPES (programmer error). Result is cached."""

def supported_types() -> tuple[str, ...]:
    """Return DOC_TYPES."""

def canonical_type(doc_type: str | None) -> str:
    """Return the canonical DOC_TYPES key a raw type resolves to (or 'outro')."""
```

**Contract guarantees**
- `schema_for(t)` returns a `dict` for every input, including `None`, `""`, and any unknown string (→ `outro`).
- `set(supported_types()) == {file stems in schemas/}` and every alias value is in `DOC_TYPES`.
- Every returned schema has a required `doc_type` enum whose single value equals its canonical key, and a required `schema_version` enum equal to `[SCHEMA_VERSION]`.

## Validator (`validator.py`)

```python
def validate(payload: object, schema: dict) -> list[str]:
    """Validate payload against schema using ONLY the stdlib. Returns a list of
    located, human-readable error strings; an empty list means valid.
    Supports exactly: type (with ['x','null'] unions), enum, required,
    properties + additionalProperties:false, items, anyOf, $ref into $defs.
    Does not raise on an invalid payload; may raise ValueError only on a
    malformed schema (programmer error)."""

def validate_transcription(payload: object, doc_type: str | None) -> list[str]:
    """schema = registry.schema_for(doc_type); return validate(payload, schema)."""
```

**Contract guarantees / behavior**
- Booleans are NOT numbers: `True`/`False` fail a `"number"` type check.
- `int` and `float` both satisfy `"number"`; only `int` for `"integer"` (not used by schemas, but supported).
- A non-object payload validated against an `object` schema yields one top-level type error (no crash).
- An unknown key on an `additionalProperties:false` object yields `"<path>: unexpected key '<k>'"`.
- A missing required key yields `"<path>: missing required field '<k>'"`.
- `anyOf` passes if any branch passes; on failure reports that no branch matched (and includes the branch errors compactly).
- `$ref` resolves `#/$defs/<name>`; resolution is bounded (schemas are non-recursive by R1).
- Error path uses `$` root, `.field` for object keys, `[i]` for array indices.

## Subset constraint (enforced by test, `tools/doc-transcribe/tests/test_subset_constraints.py`)

For every schema returned by `load_schema(t)` for `t in DOC_TYPES`:
- No node anywhere contains any of: `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`, `minLength`, `maxLength`, `pattern`, `minItems`, `maxItems`, `uniqueItems`, `minProperties`, `maxProperties`, `format`, `if`, `then`, `else`, `not`, `allOf`, `oneOf`.
- Every node whose `type` is (or includes) `"object"` declares `additionalProperties: false`.
- Every `$ref` is `#/$defs/<name>` and the `$defs` graph is acyclic (no recursion).
