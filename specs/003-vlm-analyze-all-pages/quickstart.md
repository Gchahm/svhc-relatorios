# Quickstart: verify multi-page VLM analysis + per-page records

> Verification is manual (no test framework, per Constitution III). The evidence document is the
> acceptance anchor.

## Prerequisites

- macOS/MLX host for the VLM pass (`mlx_vlm`, Qwen2.5-VL) — the analysis pass only runs there.
- Period `2025-12` scraped into `data/scrape/2025-12.json`, including the evidence entry
  `b27329f0-b020-56fc-b4b9-a38943a49c4d` and its 4-page document images.

## 1. Apply the schema migration

```bash
pnpm db:generate          # produces drizzle/0006_*.sql for document_analysis_records
pnpm db:migrate:dev       # apply locally
```

## 2. Run the analysis pass on the evidence document

```bash
# Re-analyze the evidence period (force re-run so the new per-page logic applies)
cd scripts && uv run python -m scraper analyze-docs --periodo 2025-12 --reanalyze
```

Inspect `data/scrape/2025-12.json` → the evidence document's `document_analyses` object:

- [ ] **SC-001 / US1**: `analysis_records` has **4** entries (`page_index` 0..3), one per page image.
- [ ] **US3 / SC-004**: top-level `amount_match` is `1` (true), `extracted_amount` ≈ `61590.43`
      (paid/net) — **not** `74791.04` (gross).
- [ ] **FR-009**: a record's `response` still contains gross `74791.04` AND net `61590.43`; a
      later record has paid `61590.43`. Both recoverable.
- [ ] **FR-004**: records are tagged `artifact_role` = `nfse`, `nfse`, `boleto`, `payment_proof`.
- [ ] **SC-002**: the paid value (only on page 4) drives the roll-up — proves beyond-page-1 derivation.

## 3. Single-page + failure edge cases

- [ ] **SC-003**: a single-page document produces exactly **one** `page_extraction` record.
- [ ] **SC-007 / FR-006**: temporarily point one page at a missing file → that page gets a record
      with `parse_error`, the document's other pages still analyze, document not aborted.

## 4. Import into D1 and check round-trip

```bash
node scripts/import-to-d1.mjs --input data/scrape          # local
# inspect a known record:
npx wrangler d1 execute DATABASE --local \
  --command "SELECT page_label, artifact_role, response FROM document_analysis_records \
             WHERE analysis_type='page_extraction' LIMIT 5;"
```

- [ ] **FR-011 / SC-005**: rows exist, linked to their `document_analysis_id`; `response` is valid
      JSON (NOT `"[object Object]"`); `JSON.parse(response)` equals the original page object.

## 5. Extensibility check (SC-006)

- [ ] Adding a hypothetical second `analysis_type` row for an already-analyzed document inserts
      cleanly alongside the `page_extraction` rows (non-unique FK), without altering them and with
      no schema change.

## Quality gates before commit

```bash
pnpm lint
pnpm format
git status   # confirm drizzle/0006_*.sql migration is committed
```
