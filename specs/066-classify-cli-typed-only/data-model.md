# Phase 1 Data Model: All-CLI typed document transcription

No D1 schema change, no migration. This documents the in-flight shapes the `classify` command moves
between, and the contract tightening.

## Entities

### Typed transcription `fields` object (the ONLY accepted per-page fields shape)

The EXTRACT-001-conformant per-type object produced by `tools/doc_transcribe`. Self-describing:

- `doc_type` — canonical type (`danfe` | `nfse` | `boleto` | `recibo` | `comprovante_pagamento` |
  `outro`). REQUIRED — this is the typed discriminator and the gate's accept condition.
- `schema_version` — registry schema version.
- per-type blocks (e.g. nfse `valores.valor_liquido`, danfe `totais.valor_total_nota`, `prestador`/
  `emitente`, `data_emissao`, `numero`, `raw_text`, …) — validated by `validate_transcription`.

**Validation rule (FR-008)**: a per-page payload is accepted iff it is `{"error": "<non-empty
string>"}` **or** a dict carrying `doc_type` that passes the EXTRACT-001 schema (via the injected
`typed_validator`). Anything else (incl. the legacy flat ~10-field object) is **rejected**.

### `doc_transcribe` CLI result envelope (subprocess stdout)

`{"doc_type", "schema_version", "fields"[, "parse_errors"]}`. `classify` consumes:

- `result["fields"]` → the typed object recorded via `record_classification`.
- `result["parse_errors"]` (present only when non-empty) → per-page failure signal → record
  `{"error": "<joined reasons>"}` instead.
- subprocess exit code `!= 0` → config error → stop the run, propagate stderr.

### `page_classifications` staging row (unchanged shape)

One per `(attachment_id, page_label)`:

- `id` — `det_id("page_classification", attachment_id, page_label)`.
- `attachment_id`, `page_label`, `page_index`.
- `response` — the typed `fields` object stored VERBATIM (JSON), or NULL for an error row.
- `error` — the reason string for an error row, else NULL.
- `recorded_at`.

### Plan envelope / page (unchanged — from `build_plan`)

Each plan page carries `{page_index, page_label, path, read_path, recorded}`. `classify` transcribes
only pages with `recorded == False`; `read_path` is the absolute local image the subprocess reads.

## Removed/changed shapes (FR-009)

- **Legacy flat fields object** — REMOVED as an accepted shape. Constants `REQUIRED_KEYS`,
  `PAPEL_VALUES`, `STRING_OR_NULL`, `AMOUNT_KEYS` and the `is_typed` predicate in
  `page_classifications.py` are deleted (typed is the only fields shape; no discriminator needed).
- **`type_mappers._passthrough_flat`** — REMOVED. `to_reconciliation_fields` keeps the never-raise
  `_empty()` fallback for `None`/non-dict and routes any dict (with or without a recognized
  `doc_type`) through a per-type mapper (unknown → `outro`). Since the gate rejects non-typed at write
  time, a non-typed dict can only appear from malformed legacy state — handled defensively, not as a
  supported contract.
- **UI `isTyped` dual-render** — REMOVED. `AttachmentAnalysisDetailDialog` always renders via the
  typed flatten (`typed-transcription` builder); the existing try/catch degradation path is retained.

## State transitions (classify run)

For each pending, non-`recorded` page in the plan (serially):

1. `transcribe_page(read_path)` → typed `fields` **or** a per-page error (`parse_errors`/no fields).
2. If config error raised → **stop** (propagate).
3. Else `record_classification(attachment_id, page_label, fields-or-error, page_index, typed_validator)`
   → upsert a `page_classifications` row (idempotent on `(attachment_id, page_label)`).

The attachment's `attachment_state.classified_at` is NOT touched by `classify` (that is stamped by
`apply-extractions`), so the page stays pending until applied — consistent with `docs-plan`.
