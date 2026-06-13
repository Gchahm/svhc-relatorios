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
