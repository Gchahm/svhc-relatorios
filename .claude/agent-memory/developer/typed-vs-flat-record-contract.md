---
name: typed-vs-flat-record-contract
description: How typed transcription JSON vs legacy flat reconciliation records coexist in the analysis pipeline (store raw, derive at read time); EXTRACT-003/004
metadata:
  type: project
---

Two per-page `response` shapes coexist in `page_classifications.response` /
`attachment_analysis_records.response` (both TEXT, no migration):

- **typed transcription** — the EXTRACT-001-conformant per-type `fields` object (carries `doc_type`
  + `schema_version`, nested blocks e.g. nfse `valores.valor_liquido`, danfe `totais.valor_total_nota`,
  `prestador.cnpj`). Produced by `tools/doc_transcribe` (EXTRACT-002 `transcribe()`).
- **legacy flat record** — the pre-typed ~10-field reconciliation object (no `doc_type`).

**The single discriminator** is `is_typed(resp)` = `dict and "doc_type" in resp`, owned in
`scripts/analysis/page_classifications.py` and mirrored in the UI (`AttachmentAnalysisDetailDialog`,
`isTyped`). Do NOT re-implement this predicate elsewhere.

**Bridge (EXTRACT-003):** `scripts/analysis/type_mappers.py:to_reconciliation_fields(response)` —
per-type mappers turn typed JSON → the flat reconciliation dict, and pass a legacy flat record
through unchanged (idempotent). Per-type total rules: nfse→`valor_liquido` (the 757dedb0 800-vs-320
fix), danfe→`valor_total_nota`, boleto→`valor_documento`, recibo→`valor`, comprovante→`valor` (as
`valor_pago`), outro→first `valores_identificados[].valor`. Mappers are app-side + stdlib-only (no
`tools/` import; the canonical-type alias map is mirrored locally).

**Wiring (EXTRACT-004 / feature 055 / PR #101):**
- `build_attachment_analysis` (`scripts/analysis/attachments.py`) stores the **RAW** response
  (`record.response = parsed`) so the typed JSON survives into the records table, and computes a
  **NON-persisted** `record.recon = to_reconciliation_fields(parsed)` view ONCE. Every roll-up read
  site reads `record.recon` (`_rollup_attachment_fields`'s `first_field`/`pick`, `_pick_issuer_name`,
  `_pick_attachment_date`, `_pick_payment_amount`, `_sum_distinct_invoices`, `_attachment_in_period`,
  `_issuer_names_of`, and `_map_artifact_role`). `record.recon` is NOT in `to_dict()` so it is never
  written. The fan-out copies both `response` and `recon` to siblings.
- `nf_total_for_reconciliation` and `documents.build_documents` still read `record.response` (the
  RAW shape) — they map internally via `to_reconciliation_fields`, so passing raw is correct.
- **Validation gate:** `record-classification` validates a typed payload against the EXTRACT-001
  schema via **`scripts/analysis/typed_gate.py`** — the ONLY place the analysis pipeline imports
  `tools/doc_transcribe`, lazily at runtime (it puts `<repo>/tools` on `sys.path` like `common/d1.py`
  resolves `_REPO_ROOT = parents[2]`). The analysis LIBRARY (roll-up/mappers/staging core) stays
  import-clean of `tools/` (design §11.6). `validate_page_fields(payload, *, typed_validator=…)` is
  dual-path; the CLI injects `typed_gate.validate_typed`, pure tests inject a fake.

**How to apply:** when a reconciliation false positive traces to "wrong field picked," fix the
deterministic mapper (cheap, systematic, re-derive without re-vision), not the vision step. When
adding a roll-up read, read `record.recon` (the derived view), never `record.response` (which may be
typed JSON the roll-up can't read flat). Related: [[tools-module-test-discovery]],
[[extract002-vision-transcriber]].
