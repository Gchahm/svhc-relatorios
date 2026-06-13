---
name: typed-vs-flat-record-contract
description: Two distinct per-page response shapes coexist (typed transcription JSON vs legacy flat reconciliation fields); the analysis roll-up consumes ONLY the flat shape
metadata:
  type: project
---

The analysis roll-up (`scripts/analysis/attachments.py`) reads each page record's `response` as a
**flat** dict (`valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `nome_emitente`,
`data_emissao`, `numero_documento`, `descricao_servico`, `papel_artefato`, `tipo_documento`) at MANY
call sites: `_rollup_attachment_fields`, `_map_artifact_role`, `_pick_issuer_name`,
`_pick_attachment_date`, `_pick_payment_amount`, `_sum_distinct_invoices`, `_attachment_in_period`,
`nf_total_for_reconciliation`, and downstream `documents.py` + `mismatches.py`.

The EXTRACT-001/002 typed transcription (`tools/doc_transcribe`) produces a **nested** JSON keyed by
a `doc_type` discriminator (e.g. `nfse` → `valores.valor_liquido`, `danfe` → `totais.valor_total_nota`,
`prestador.cnpj`). Those nested fields do NOT match the flat keys the roll-up reads.

**Bridge (feature 053 / EXTRACT-003):** `scripts/analysis/type_mappers.py`
`to_reconciliation_fields(response)` — per-type mappers that turn typed JSON → the flat dict, and
**pass a legacy flat record through unchanged (idempotent)**. It is wired at ONE boundary in
`build_attachment_analysis` (set `record.response = to_reconciliation_fields(parsed)` before
`_map_artifact_role`) plus defensively inside `nf_total_for_reconciliation` for the
`documents.build_documents` read-back path.

**Why:** Future-you adding a field to the typed schema OR touching the roll-up must know: the
rolled-up `attachment_analysis_records.response` stores the FLAT mapped dict (the typed JSON is
evidence kept in the `page_classifications` staging row, not in the records table). Mappers are
app-side + stdlib-only (no `tools/doc_transcribe` import from the analysis package; cwd is `scripts/`
so `tools/` is off the path — the canonical-type alias map is mirrored locally).

**How to apply:** When a reconciliation false positive traces to "wrong field picked," the fix is the
deterministic mapper (cheap, systematic, re-derive without re-vision), not the vision step. Per-type
total rules: nfse→`valor_liquido` (this fixed the 757dedb0 800-vs-320 bug), danfe→`valor_total_nota`,
boleto→`valor_documento`, recibo→`valor`, comprovante→`valor` (as `valor_pago`), outro→first
`valores_identificados[].valor`. Related: [[tools-module-test-discovery]].
