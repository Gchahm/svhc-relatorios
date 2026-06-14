# Data Model: Persist typed transcriptions + flat-row coexistence

No database schema change. This documents the two stored response shapes and the derived
reconciliation view.

## Stored per-page response (`page_classifications.response`, `attachment_analysis_records.response`)

Both columns are TEXT (JSON). A single column holds **either** shape; the discriminator is `doc_type`.

### Typed transcription record (NEW — has `doc_type`)

The EXTRACT-001-conformant per-type `fields` object (exactly what `doc_transcribe.transcribe()`
returns as `fields`, and what `validate_transcription` validates). Common envelope plus a per-type
body. Example (NFS-e, abbreviated):

```json
{
  "doc_type": "nfse",
  "schema_version": "1",
  "raw_text": "NOTA FISCAL DE SERVICOS ELETRONICA - NFS-e ...",
  "numero": "0000123",
  "data_emissao": "05/12/2025",
  "prestador": { "nome": "MANUTENCAO PREDIAL SV LTDA", "cnpj": "11.222.333/0001-44" },
  "tomador": { "nome": "SAO VICENTE HOME CLUB", "cnpj_cpf": "98.765.432/0001-00" },
  "discriminacao_servico": "Servico de manutencao de portao eletronico",
  "valores": { "valor_servico": 320.0, "deducoes": 0.0, "valor_liquido": 320.0 }
}
```

- `doc_type`: one of the canonical registry types (`danfe`, `nfse`, `boleto`, `recibo`,
  `comprovante_pagamento`, `outro`).
- `schema_version`: registry-canonical version (a required single-value enum in each schema).
- Per-type blocks per the EXTRACT-001 schemas.

### Legacy flat record (UNCHANGED — no `doc_type`)

The pre-typed reconciliation object:

```json
{
  "papel_artefato": "nfse",
  "tipo_documento": "nfse",
  "valor_total": 320.0,
  "valor_liquido": 320.0,
  "valor_pago": null,
  "cnpj_emitente": "11.222.333/0001-44",
  "nome_emitente": "MANUTENCAO PREDIAL SV LTDA",
  "data_emissao": "05/12/2025",
  "numero_documento": "0000123",
  "descricao_servico": "..."
}
```

### Error result (UNCHANGED — the one permitted non-fields alternative)

```json
{ "error": "page illegible" }
```

Stored with `response = NULL` and `error = "<reason>"`.

## Derived reconciliation view (in-memory, NOT stored separately)

For both shapes the roll-up needs the flat reconciliation dict (keys in
`type_mappers.RECONCILIATION_KEYS`). It is derived per record by
`type_mappers.to_reconciliation_fields(response)`:

- typed (`doc_type` present) → the per-type mapper output (e.g. nfse → `valor_total = valor_liquido`).
- flat (no `doc_type`) → identity projection of the reconciliation keys.

The raw `response` is what is persisted; the derived dict feeds `_rollup_attachment_fields` /
`_map_artifact_role` / `nf_total_for_reconciliation`.

## Typed-vs-flat predicate

`is_typed(resp)` ≡ `isinstance(resp, dict) and "doc_type" in resp`. Single source
(`scripts/analysis/page_classifications.py`), mirrored in the UI (`"doc_type" in parsed`).

## Validation rules (the contract gate)

| Input shape | Validator | Reject when |
|-------------|-----------|-------------|
| `{"error": "<str>"}` | existing | not exactly `{error}`, or empty/non-string error |
| dict with `doc_type` | EXTRACT-001 schema (via `typed_gate`) | any schema error for the resolved type (missing required block/field, unexpected key, wrong type) |
| dict without `doc_type` | existing flat contract | missing/extra reconciliation key, bad papel/amount typing |
| non-dict | existing | not a JSON object |

## State / lifecycle

Unchanged: `record-classification` (validate → upsert staging) → `apply-extractions` (roll up,
atomic write to `attachment_analyses` + `attachment_analysis_records`, prune staging) →
`analyze`/`build-documents` (read reconciliation values). The only change is what each stored
`response` contains (rich typed JSON, when typed) and that reconciliation values are derived, not
pre-collapsed.
