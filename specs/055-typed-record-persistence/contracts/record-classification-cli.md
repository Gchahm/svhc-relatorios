# Contract: `record-classification` CLI (dual-path validation)

`python -m analysis record-classification --attachment-id <id> --page <label> [--page-index N]
[--json <payload>|-] [--remote]`

Unchanged invocation. The change is the **validation** applied to the payload and **what is stored**.

## Input

`--json` (or stdin) is one JSON value, one of:

1. **Typed payload** — a JSON object carrying a `doc_type` key (the EXTRACT-002 transcriber's `fields`
   object). Example: see data-model.md.
2. **Legacy flat payload** — a JSON object with no `doc_type`, matching the existing reconciliation
   field contract (`page_classifications.REQUIRED_KEYS` + `papel_artefato`).
3. **Error result** — exactly `{"error": "<non-empty string>"}`.

## Validation (the single contract gate)

- An error result is accepted unchanged.
- A typed payload is validated against the EXTRACT-001 schema for `canonical_type(doc_type)` (via
  `doc_transcribe.validate_transcription`, reached through `scripts/analysis/typed_gate.py`). An
  unknown `doc_type` resolves to the `outro` fallback schema (never blocks on type alone).
- A flat payload is validated against the existing flat-field contract.
- A non-object payload is rejected.

On ANY validation failure: exit code **1**, a located error message on stderr
(`error: classification rejected: <detail>`), and **nothing written** to D1.

## Storage (on success)

- Typed payload → one `page_classifications` row with `response` = the typed JSON **verbatim**
  (carrying `doc_type` + `schema_version`), `error` = NULL.
- Flat payload → one row with `response` = the flat JSON, `error` = NULL (unchanged).
- Error result → one row with `response` = NULL, `error` = `<reason>` (unchanged).

Row id is deterministic on `(attachment_id, page_label)` (idempotent upsert — latest wins), unchanged.

## Output (on success)

stdout: `Recorded classification for <attachment_id> <page_label>.` (unchanged).

## Downstream effect

`apply-extractions` rolls the staging rows into `attachment_analyses` +
`attachment_analysis_records`. The persisted `attachment_analysis_records.response` carries the SAME
shape that was staged (typed JSON for a typed row), and the rolled-up reconciliation columns
(`extracted_amount`, `extracted_cnpj`, `issuer_name`, `extracted_date`, `document_number`,
`document_type`) are derived from the response via the EXTRACT-003 per-type mapper. Legacy flat rows
roll up identically to before.

## Backward compatibility

- A flat payload behaves exactly as it did before this feature (same validation, same storage, same
  roll-up).
- The error-result alternative is unchanged.
- No CLI flag added or removed.
