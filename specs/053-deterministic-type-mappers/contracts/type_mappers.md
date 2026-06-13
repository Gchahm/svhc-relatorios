# Contract: `scripts/analysis/type_mappers.py`

Pure, stdlib-only module. No I/O, never raises on any input.

## `to_reconciliation_fields(response: dict | None) -> dict`

Dispatch the typed (or legacy flat) per-page response to its mapper and return the flat
reconciliation-field dict (the keys in `data-model.md`).

- `None` / non-dict → returns an empty-valued reconciliation dict (all keys present, all `None`).
- `response["doc_type"]` present → canonicalize it (`_canonical_doc_type`) and call that type's
  mapper. An unknown/unresolvable type → `_map_outro`.
- `response["doc_type"]` **absent** → **legacy flat pass-through**: project the known reconciliation
  keys straight off `response` (values unchanged; unknown extra keys ignored), so a pre-typed record
  yields exactly what the pre-feature roll-up read.
- MUST NOT raise for any input (missing nested keys, wrong types, etc.) — missing fields → `None`.

## `_canonical_doc_type(value: str | None) -> str`

Resolve a `doc_type`/alias to one of the six canonical keys
(`danfe`/`nfse`/`boleto`/`recibo`/`comprovante_pagamento`/`outro`); unknown/None → `"outro"`.
Case/underscore/hyphen-insensitive. Mirrors (does not import) the EXTRACT-001 registry taxonomy.

## Per-type mappers (`_map_danfe`, `_map_nfse`, `_map_boleto`, `_map_recibo`, `_map_comprovante`, `_map_outro`)

Each takes the typed `response` dict and returns the flat reconciliation dict per the
`research.md` Decision 4 table. Key invariants:

- `_map_nfse` derives `valor_total = valor_liquido = valores.valor_liquido` (the 757dedb0 fix:
  yields 320, not the model's 800).
- `_map_danfe` derives `valor_total = totais.valor_total_nota`.
- `_map_comprovante` derives `valor_pago = valor` (no `valor_total`).
- `_map_boleto` derives `valor_total = valor_documento`.
- `_map_recibo` derives `valor_total = valor`.
- `_map_outro` derives `valor_total` from `valores_identificados[0].valor` when present, else `None`.
- Nested access is defensive: a missing/`None` sub-object yields `None`, never an exception.

## Wiring contract (`scripts/analysis/attachments.py`)

- `build_attachment_analysis`: after `provider` returns a page's `parsed`, set
  `record.response = to_reconciliation_fields(parsed)` and `record.artifact_role =
  _map_artifact_role(record.response)`. The mapper is **idempotent on a legacy flat record**, so this
  is a no-op for pre-typed data and the derivation for typed data. The normalized flat dict becomes
  the persisted `attachment_analysis_records.response`, so the roll-up, its helpers, `mismatches.py`,
  and `documents.py` all consume flat fields unchanged.
- `nf_total_for_reconciliation`: map each response defensively (idempotent) before reading
  `valor_total`, so it also works over already-persisted records read back by `documents`.
- Behavior for legacy flat records is byte-for-byte unchanged (the mapper is the identity over the
  reconciliation keys when `doc_type` is absent).
- The `reconcile_group` tolerance + `reconciliation_contract.json` are untouched.

## Idempotence requirement

`to_reconciliation_fields(flat_record) == projected(flat_record)` for any legacy flat record, and
`to_reconciliation_fields(to_reconciliation_fields(x))` is stable — a flat dict (no `doc_type`) maps
to itself, so double-application is safe.
