"""Deterministic per-type mappers: typed transcription JSON → reconciliation fields.

The vision step used to both *read* a fiscal document page and *interpret* it — deciding
"which number is the total" and "who is the issuer" — emitting a flat ~10-field object. That
interpretation was guesswork that became data errors: the documented ``757dedb0`` case where the
model reported an NFS-e total of 800 when the page legibly showed 320, and a whole class of
``amount_match`` false positives where ``_rollup_attachment_fields`` picked the *first record of a
role* (see ``docs/features/rollup-amount-false-positives.md`` §Problem A).

With the typed transcription contract (EXTRACT-001 schema registry, EXTRACT-002 transcriber) the
page is transcribed verbatim into a **typed JSON keyed by document type** (e.g. an NFS-e records
``valores.valor_servico`` and ``valores.valor_liquido`` separately; a DANFE records
``totais.valor_total_nota``). "Which number is the total / who is the issuer" then becomes a
**deterministic, pure, testable** function over that typed JSON — the per-type mappers here —
replacing the model's guesswork with versioned rules (design §10.2).

Per-type derivation of the reconciliation total (and the issuer/number):

    danfe                  valor_total = totais.valor_total_nota        emitente / numero
    nfse                   valor_total = valor_liquido = valores.valor_liquido   prestador / numero
                           (the 757dedb0 fix: yields 320, never 800)
    boleto                 valor_total = valor_documento                beneficiario / numero_documento
    recibo                 valor_total = valor                          recebedor / numero
    comprovante_pagamento  valor_pago  = valor                          recebedor / identificador
    outro                  valor_total = first valores_identificados[].valor (best-effort)

The "issuer" (``cnpj_emitente`` / ``nome_emitente``) means *who issued the fiscal document / who is
owed*: the emitente/prestador for an invoice, the recebedor/beneficiário (payee) for a payment
proof or boleto — matching the existing ``_pick_issuer_name`` payer-exclusion semantics.

Home & dependencies (design T6): the mappers live **app-side** (which field SVHC reconciles on is
app policy, not portable schema knowledge) and are **stdlib only** — this module does NOT import the
``tools/doc_transcribe`` package (the analysis package runs with cwd ``scripts/``, where ``tools/``
is off the import path). The small canonical-type alias resolution is *mirrored* locally (the six
corpus types are stable), exactly as the scraper mirrors — rather than imports — the analysis
reconciliation tolerance.

Typed-only (EXTRACT-007): the legacy flat record contract is retired — every stored ``response`` is a
typed transcription (carries a ``doc_type`` discriminator). ``to_reconciliation_fields`` runs the
per-type mapper for that ``doc_type`` (an unknown type falls back to ``outro``). It still never raises
on a malformed/non-dict input (degrading to an all-``None`` reconciliation dict), so a read of any
odd stored state stays safe.
"""

from __future__ import annotations

# The flat reconciliation-field contract the analysis roll-up consumes off each page's typed response.
# (The keys the roll-up reads — papel_artefato plus the reconciliation fields each mapper fills.)
RECONCILIATION_KEYS: tuple[str, ...] = (
    "papel_artefato",
    "tipo_documento",
    "valor_total",
    "valor_liquido",
    "valor_pago",
    "cnpj_emitente",
    "nome_emitente",
    "data_emissao",
    "numero_documento",
    "descricao_servico",
)

# Canonical document types (mirrors tools/doc_transcribe registry DOC_TYPES — kept in sync by hand,
# the set is stable: the six corpus types).
_DOC_TYPES: frozenset[str] = frozenset(
    {"danfe", "nfse", "boleto", "recibo", "comprovante_pagamento", "outro"}
)

# Alias / spelling-variant → canonical key (mirrors the registry ALIASES, normalized-key matched).
_ALIASES: dict[str, str] = {
    "danfe": "danfe",
    "nf e": "danfe",
    "nfe": "danfe",
    "nota fiscal": "danfe",
    "nota fiscal eletronica": "danfe",
    "invoice": "danfe",
    "nfse": "nfse",
    "nfs e": "nfse",
    "danfse": "nfse",
    "nota fiscal de servico": "nfse",
    "boleto": "boleto",
    "boleto bancario": "boleto",
    "recibo": "recibo",
    "comprovante pagamento": "comprovante_pagamento",
    "comprovante": "comprovante_pagamento",
    "comprovante de pagamento": "comprovante_pagamento",
    "payment proof": "comprovante_pagamento",
    "pix": "comprovante_pagamento",
    "ted": "comprovante_pagamento",
    "outro": "outro",
    "other": "outro",
}


def _normalize(raw: str) -> str:
    return " ".join(raw.strip().lower().replace("_", " ").replace("-", " ").split())


def _canonical_doc_type(value) -> str:
    """Resolve a ``doc_type`` / alias to one of the canonical keys; unknown/None → 'outro'.

    Case/underscore/hyphen-insensitive. Never raises. Mirrors (does not import) the EXTRACT-001
    registry taxonomy.
    """
    if not value or not isinstance(value, str):
        return "outro"
    if value in _DOC_TYPES:
        return value
    norm = _normalize(value)
    return _ALIASES.get(norm, "outro")


def _empty() -> dict:
    """A reconciliation dict with every key present and None (the never-raise fallback)."""
    return {k: None for k in RECONCILIATION_KEYS}


def _get(obj, *path):
    """Defensive nested access: returns the value at ``path`` or None (never raises).

    A non-dict at any level (or a missing key) yields None, so a malformed/partial typed JSON
    degrades to empty fields rather than an exception.
    """
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _str_or_none(value):
    """Coerce a scalar to a non-empty string, else None (leaves numbers/strings legible)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    return str(value)


def _first_item(seq):
    """First element of a list, else None (defensive)."""
    if isinstance(seq, list) and seq:
        return seq[0]
    return None


# ─── Per-type mappers ────────────────────────────────────────────────────────
# Each takes the typed `response` dict and returns the flat reconciliation dict. Amounts are passed
# through as-is (numeric or currency string); the roll-up parses them with the existing
# `_parse_brl_value`, so a spurious 0.0 and a currency string behave exactly as before. Never raise.


def _map_danfe(resp: dict) -> dict:
    out = _empty()
    out["papel_artefato"] = "invoice"
    out["tipo_documento"] = "danfe"
    out["valor_total"] = _get(resp, "totais", "valor_total_nota")
    out["cnpj_emitente"] = _str_or_none(_get(resp, "emitente", "cnpj"))
    out["nome_emitente"] = _str_or_none(_get(resp, "emitente", "nome"))
    out["data_emissao"] = _str_or_none(resp.get("data_emissao"))
    out["numero_documento"] = _str_or_none(resp.get("numero"))
    out["descricao_servico"] = _str_or_none(_get(_first_item(resp.get("itens")), "descricao"))
    return out


def _map_nfse(resp: dict) -> dict:
    out = _empty()
    out["papel_artefato"] = "nfse"
    out["tipo_documento"] = "nfse"
    # The 757dedb0 fix: the reconciliation total is the net (valor_liquido), the amount actually
    # settled. For the corpus where deducoes == 0 this equals valor_servico; when retentions exist
    # the liquido is the correct reconciliation target.
    liquido = _get(resp, "valores", "valor_liquido")
    out["valor_total"] = liquido
    out["valor_liquido"] = liquido
    out["cnpj_emitente"] = _str_or_none(_get(resp, "prestador", "cnpj"))
    out["nome_emitente"] = _str_or_none(_get(resp, "prestador", "nome"))
    out["data_emissao"] = _str_or_none(resp.get("data_emissao"))
    out["numero_documento"] = _str_or_none(resp.get("numero"))
    out["descricao_servico"] = _str_or_none(resp.get("discriminacao_servico"))
    return out


def _map_boleto(resp: dict) -> dict:
    out = _empty()
    out["papel_artefato"] = "boleto"
    out["tipo_documento"] = "boleto"
    out["valor_total"] = resp.get("valor_documento")
    out["cnpj_emitente"] = _str_or_none(_get(resp, "beneficiario", "cnpj_cpf"))
    out["nome_emitente"] = _str_or_none(_get(resp, "beneficiario", "nome"))
    out["data_emissao"] = _str_or_none(resp.get("data_documento"))
    out["numero_documento"] = _str_or_none(resp.get("numero_documento"))
    return out


def _map_recibo(resp: dict) -> dict:
    out = _empty()
    out["papel_artefato"] = "payment_proof"
    out["tipo_documento"] = "recibo"
    out["valor_total"] = resp.get("valor")
    out["cnpj_emitente"] = _str_or_none(_get(resp, "recebedor", "cnpj_cpf"))
    out["nome_emitente"] = _str_or_none(_get(resp, "recebedor", "nome"))
    out["data_emissao"] = _str_or_none(resp.get("data"))
    out["numero_documento"] = _str_or_none(resp.get("numero"))
    out["descricao_servico"] = _str_or_none(resp.get("referente_a"))
    return out


def _map_comprovante(resp: dict) -> dict:
    out = _empty()
    out["papel_artefato"] = "payment_proof"
    out["tipo_documento"] = "comprovante"
    out["valor_pago"] = resp.get("valor")
    out["cnpj_emitente"] = _str_or_none(_get(resp, "recebedor", "cnpj_cpf"))
    out["nome_emitente"] = _str_or_none(_get(resp, "recebedor", "nome"))
    out["data_emissao"] = _str_or_none(resp.get("data"))
    out["numero_documento"] = _str_or_none(resp.get("identificador"))
    return out


def _map_outro(resp: dict) -> dict:
    out = _empty()
    out["papel_artefato"] = "other"
    out["tipo_documento"] = "outro"
    # Best-effort single amount: the first identified value, if any. Never raises.
    out["valor_total"] = _get(_first_item(resp.get("valores_identificados")), "valor")
    out["descricao_servico"] = _str_or_none(resp.get("descricao"))
    return out


_MAPPERS = {
    "danfe": _map_danfe,
    "nfse": _map_nfse,
    "boleto": _map_boleto,
    "recibo": _map_recibo,
    "comprovante_pagamento": _map_comprovante,
    "outro": _map_outro,
}


def to_reconciliation_fields(response) -> dict:
    """Derive the flat reconciliation fields from a typed per-page response (EXTRACT-007: typed-only).

    - ``None`` / non-dict → an empty-valued reconciliation dict (all keys present, all None).
    - any dict → canonicalize its ``doc_type`` and run that type's mapper (a missing/unknown type
      falls back to ``outro`` — a defensive read path; the write-time gate already rejects non-typed
      payloads, so a dict without a recognized ``doc_type`` can only come from malformed legacy state).

    Never raises on any input.
    """
    if not isinstance(response, dict):
        return _empty()
    canonical = _canonical_doc_type(response.get("doc_type"))
    mapper = _MAPPERS.get(canonical, _map_outro)
    return mapper(response)
