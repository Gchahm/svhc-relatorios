# Phase 0 Research: Vision-analyze every page of a document

All decisions below resolve the otherwise-open choices in the spec's Assumptions section. There
were no `NEEDS CLARIFICATION` markers; this records the rationale so planning/tasks are unambiguous.

## D1. Per-page records: nested in period JSON vs. flat top-level array

**Decision**: Nest a `analysis_records` array **inside each `document_analyses` object** in the
period JSON. The D1 importer flattens these into the top-level `document_analysis_records` table
at import time (stripping the nested key from the `document_analyses` row before inserting it).

**Rationale**: The spec explicitly says records are "nested in the period JSON under their
document analysis." Nesting keeps a document's records co-located with their parent in the
human-inspectable JSON and survives the existing per-document `_merge_and_write` write-back
(which replaces a whole `document_analyses` entry by `document_id`) without a second parallel
array to keep in sync. The importer already iterates `data[table]` per table; flattening is a
small, localized addition.

**Alternatives considered**:
- *Flat top-level `document_analysis_records` array in period JSON*: simpler importer (drops
  straight into the generic loop) but splits a document's data across two arrays, complicating
  `_merge_and_write`'s "replace by document_id" semantics and risking orphaned records on
  re-analysis. Rejected.
- *One JSON column on `document_analyses` holding the records array*: violates the spec's
  requirement for a normalized table queryable per record / per `analysis_type`. Rejected.

## D2. New table name and shape

**Decision**: `document_analysis_records` (Drizzle export `documentAnalysisRecords`). Columns:

| Column | Type | Notes |
|--------|------|-------|
| `id` | text PK (uuid) | deterministic id from `det_id("analysis_record", document_id, analysis_type, page_label)` |
| `document_analysis_id` | text FK → `document_analyses.id`, NOT NULL, **not unique** | many records per document analysis |
| `analysis_type` | text(50) NOT NULL | e.g. `page_extraction`; the analysis-kind label (not prompt text) |
| `page_index` | integer | 0-based position in the `file_path` page list |
| `page_label` | text(20) | the `_pN` filename suffix (e.g. `p3`) when derivable, else `page{index+1}` |
| `artifact_role` | text(30) | `invoice` / `nfse` / `boleto` / `payment_proof` / `other` |
| `response` | text | JSON-serialized parsed page response (the structured values) |
| `raw_text` | text | VLM raw text, kept when parsing failed (and optionally always) |
| `parse_error` | text | error string when the page could not be parsed / image missing |
| `analyzed_at` | integer (timestamp_ms) | per-record timestamp |

**Rationale**: FK is non-unique so multiple records per document and per page are allowed
(FR-005) — a future `forgery_detection` analysis_type attaches new rows without schema change or
collision. `analysis_type` is the discriminator. `page_index` + `page_label` together satisfy the
"page reference aligned to the `_pN` suffix / page order" requirement (FR-004). `response` is a
TEXT column holding JSON (consistent with the existing `alerts.metadata` JSON-in-TEXT pattern),
preserving per-artifact values (gross/net/paid) without collapsing them.

**Alternatives considered**:
- *Reuse `document_analyses` with a `page` column*: breaks the one-object-per-document invariant
  (FR-002) and the existing `document_id` UNIQUE constraint. Rejected.
- *Separate columns for gross/net/paid on the record*: over-fits `page_extraction`; future
  analysis kinds carry different fields. Storing the whole parsed JSON in `response` keeps the
  table generic (FR-005). The roll-up reads gross/net/paid out of `response`. Accepted instead.

## D3. Disposition of the legacy `document_analyses.raw_response` column

**Decision**: Keep the column (nullable), stop populating it with per-page detail; leave it
`NULL` (or a short document-level note) going forward. Do not drop it in this feature.

**Rationale**: FR-010 only requires that `raw_response` no longer carry per-page detail. Dropping
a column is a destructive D1 migration with no functional benefit here; retaining it as legacy is
the simpler, lower-risk choice (Principle V) and avoids touching rows already imported.

**Alternatives considered**: Dropping the column (cleaner schema, but destructive migration and
breaks any existing reader); reusing it for a document-level summary blob (muddies the new
normalized model). Both rejected for now; a later cleanup ticket may drop it.

## D4. Heterogeneity-aware roll-up & amount-match rule

**Decision**: After all pages are analyzed, derive the document-level fields from the set of
per-page records with this precedence for the amount used in `amount_match`:

1. If any record has `artifact_role == payment_proof` with a paid value → use that paid value.
2. Else if any record has a boleto value → use the boleto value.
3. Else if an invoice/nfse record exposes a **net** value (`valor_liquido`) → use net.
4. Else fall back to the invoice **gross** / `valor_total` (current behavior).

Other document-level fields (`document_type`, `extracted_cnpj`, `issuer_name`, `extracted_date`,
`document_number`, `service_description`) are taken preferentially from the invoice/nfse record
(the artifact that carries issuer/service identity), falling back to the first record that has
each field. Existing tolerances (amount 5%, fuzzy vendor, date-in-period) are unchanged.

**Rationale**: This directly implements FR-007/FR-008 and fixes the evidence-case false mismatch:
the paid amount (61.590,43) equals the entry amount, while the gross (74.791,04) does not. Gross
and net both remain recoverable from the per-page `response` (FR-009) — the roll-up only chooses
which value drives the boolean.

**Alternatives considered**: Picking `max`/`min`/first value across pages (reproduces the false
mismatch or hides the story — explicitly rejected by the spec); full reconciliation chain
(out of scope — Phase 2).

## D5. VLM prompt extension

**Decision**: Extend `EXTRACT_PROMPT` to (a) classify the page's artifact role and (b) capture
gross/net/paid explicitly, while keeping the existing fields for backward compatibility:

```
"papel_artefato": "invoice" | "nfse" | "boleto" | "payment_proof" | "other",
"valor_total":   gross/total value (existing),
"valor_liquido": net value after retentions (null if not present),
"valor_pago":    amount actually paid (null if not a payment artifact),
```

Each page is analyzed with one `apply_chat_template` + `generate` call (single image per call,
per FR/acceptance). The parsed JSON is stored verbatim in the record's `response`; the role maps
to `artifact_role`.

**Rationale**: The model already returns JSON and `_parse_vlm_response` already parses it — we
extend the schema rather than add a second call. `papel_artefato` gives the role needed for D4;
`valor_liquido`/`valor_pago` give the values D4's precedence consumes. Mapping Portuguese role
labels (`nota fiscal`/`nfs-e` → `nfse`, etc.) is handled in code defensively.

**Alternatives considered**: A separate classification call per page (doubles VLM cost, no
benefit); a single multi-image call for the whole document (acceptance explicitly requires
one call per image because `mlx_vlm.generate` takes a single image). Both rejected.

## D6. Importer `escapeSQL` fix

**Decision**: Add a branch to `escapeSQL` that detects `typeof value === "object"` (and not null)
— including arrays — and `JSON.stringify`s it before quoting/escaping, placed before the
`String(value)` fallback.

**Rationale**: FR-012. The current fallback turns any object into the literal `"[object Object]"`,
silently corrupting the column. A generic object/array branch protects the new `response` field
and any future nested field. JSON-stringify + single-quote-escape round-trips cleanly back to the
stored JSON text.

**Alternatives considered**: Stringifying only the `response` column by name (brittle, misses
future fields). Rejected in favor of the generic branch.

## D7. Crash-safe per-document write-back

**Decision**: Keep `_merge_and_write` writing after each document, but have `to_dict` emit the
nested `analysis_records` array as part of the document-analysis object, so a single write
persists the document and all its page records atomically (replace-by-`document_id` still holds).

**Rationale**: Preserves the existing mid-run inspectability / interruption-survival behavior
with no second write path.
