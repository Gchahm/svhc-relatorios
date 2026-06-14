"""Document-type → JSON-Schema registry for the typed extraction contract.

The canonical types are the six in the corpus (EXTRACT-001). Each is backed by a
``schemas/<key>.json`` file. ``schema_for`` resolves aliases + spelling variants
and falls back to ``outro`` for any unrecognized type, so it NEVER raises on an
unknown type. ``SCHEMA_VERSION`` identifies the contract version for downstream
coexistence with legacy flat rows.

Zero imports from ``scripts/analysis`` — this module is intentionally
self-contained and reusable (design §11.6).
"""

from __future__ import annotations

import json
from pathlib import Path

# Bump on any breaking change to the contract. A string keeps it human-stable
# and future-proof (e.g. "1.1"). Embedded into every schema's required
# ``schema_version`` single-value enum so a payload self-declares its version.
SCHEMA_VERSION = "1"

# Canonical registry keys (one schema file each, stem == key).
DOC_TYPES: tuple[str, ...] = (
    "danfe",
    "nfse",
    "boleto",
    "recibo",
    "comprovante_pagamento",
    "outro",
)

# Flat-taxonomy values + spelling variants → canonical key. Lets the future
# record-classification adapter (EXTRACT-004) map the existing
# papel_artefato/tipo_documento taxonomy onto these without re-deciding it.
# Keys are matched case/space-insensitively (see _normalize).
ALIASES: dict[str, str] = {
    # danfe / NF-e
    "danfe": "danfe",
    "nf-e": "danfe",
    "nfe": "danfe",
    "nota fiscal": "danfe",
    "nota fiscal eletronica": "danfe",
    "invoice": "danfe",
    # nfse / DANFSe
    "nfse": "nfse",
    "nfs-e": "nfse",
    "danfse": "nfse",
    "nota fiscal de servico": "nfse",
    # boleto
    "boleto": "boleto",
    "boleto bancario": "boleto",
    # recibo
    "recibo": "recibo",
    # comprovante de pagamento
    "comprovante_pagamento": "comprovante_pagamento",
    "comprovante": "comprovante_pagamento",
    "comprovante de pagamento": "comprovante_pagamento",
    "payment_proof": "comprovante_pagamento",
    "pix": "comprovante_pagamento",
    "ted": "comprovante_pagamento",
    # generic fallback
    "outro": "outro",
    "other": "outro",
}

_SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"
_CACHE: dict[str, dict] = {}


def _normalize(raw: str) -> str:
    return " ".join(raw.strip().lower().replace("_", " ").replace("-", " ").split())


def canonical_type(doc_type: str | None) -> str:
    """Return the canonical DOC_TYPES key ``doc_type`` resolves to, or 'outro'."""
    if not doc_type or not isinstance(doc_type, str):
        return "outro"
    # Exact canonical key (underscored) wins first.
    if doc_type in DOC_TYPES:
        return doc_type
    norm = _normalize(doc_type)
    # Direct alias hit on normalized form.
    for alias, target in ALIASES.items():
        if _normalize(alias) == norm:
            return target
    return "outro"


def load_schema(doc_type: str) -> dict:
    """Load a canonical-keyed schema by EXACT DOC_TYPES key (cached).

    Raises KeyError for a key not in DOC_TYPES (programmer error). Use
    ``schema_for`` for the alias/fallback-tolerant resolution."""
    if doc_type not in DOC_TYPES:
        raise KeyError(f"{doc_type!r} is not a canonical document type {DOC_TYPES!r}")
    cached = _CACHE.get(doc_type)
    if cached is None:
        with (_SCHEMAS_DIR / f"{doc_type}.json").open(encoding="utf-8") as fh:
            cached = json.load(fh)
        _CACHE[doc_type] = cached
    return cached


def schema_for(doc_type: str | None) -> dict:
    """Return the JSON Schema for ``doc_type``. Resolves aliases; an unknown or
    None type returns the ``outro`` fallback schema. NEVER raises on an unknown
    type."""
    return load_schema(canonical_type(doc_type))


def supported_types() -> tuple[str, ...]:
    """Return the canonical document types."""
    return DOC_TYPES


def _inline_branch(schema: dict) -> dict:
    """Return one per-type schema as a self-contained ``anyOf`` branch: every local
    ``#/$defs/<name>`` ref is **inlined** with a copy of the def body and ``$defs``/``$schema``
    are dropped.

    The API's structured-output validator accepts a top-level ``anyOf`` but rejects ``$defs``
    alongside it ("For 'anyOf', '$defs' is not supported"), and a bare ``$ref`` can't resolve
    once ``$defs`` is gone — so the only ref-free form is full inlining. The per-type schemas
    are shallow and non-recursive (recursion is forbidden by the contract), so inlining
    terminates. Pure — never mutates the cached input schema."""
    defs = schema.get("$defs", {})

    def inline(node, depth):
        if depth > 64:
            raise ValueError("ref nesting too deep (recursion is not allowed in the contract)")
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str) and node["$ref"].startswith("#/$defs/"):
                target = defs[node["$ref"][len("#/$defs/"):]]
                resolved = inline(target, depth + 1)
                siblings = {k: inline(v, depth + 1) for k, v in node.items() if k != "$ref"}
                return {**resolved, **siblings}
            return {k: inline(v, depth + 1) for k, v in node.items()}
        if isinstance(node, list):
            return [inline(x, depth + 1) for x in node]
        return node

    return inline({k: v for k, v in schema.items() if k not in ("$defs", "$schema")}, 0)


def union_schema() -> dict:
    """An ``anyOf`` union over every canonical type's schema, fully **ref-inlined**.

    This is the instruction shape used for **auto** detection: the model is shown all
    supported document types at once, so it classifies the page AND fills the matching
    type's structured fields in a single pass — instead of only ``raw_text`` (the failure
    mode when auto was shown the ``outro`` schema alone). ``anyOf`` (never ``oneOf``) keeps
    it inside the validator's supported subset; each branch is discriminated by its
    single-value ``doc_type`` enum. Each branch is fully inlined (no ``$defs``/``$ref``)
    because the API's structured-output format rejects ``$defs`` under a top-level ``anyOf``.
    A returned payload is still validated against the resolved per-type schema
    (``validate_transcription``), not this union."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Auto typed transcription — any supported Brazilian fiscal document",
        "anyOf": [_inline_branch(load_schema(t)) for t in DOC_TYPES],
    }
