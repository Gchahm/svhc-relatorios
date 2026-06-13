# Phase 1 Data Model: Vision Extraction Provenance

No persisted schema changes. All persisted entities are read-only here; the only *new* shapes are derived/response shapes computed at request time.

## Read-only persisted entities (existing)

- **documents** — `id`, `document_number`, `issuer_cnpj`, `issuer_name`, `document_type`, `total_value` (the MAX confident reconciliation total across the key's analyses), `created_at`, `updated_at`. The headline figure under audit.
- **document_entries** — N:N link `document_id ↔ entry_id` with `source_attachment_id` (provenance). Resolves a document to the attachments (and thus analyses) behind it.
- **attachment_analyses** — per-attachment roll-up: `id`, `attachment_id`, `extracted_amount`, `document_type`, `extracted_cnpj`, `issuer_name`, `document_number`, `service_description`, the `*_match` flags, `error`, `analyzed_at`. The roll-up half of the AI extraction object.
- **attachment_analysis_records** — per-page extraction: `attachment_analysis_id`, `page_index`, `page_label`, `artifact_role`, `response` (JSON: `valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, …), `parse_error`. The per-page half; `response.valor_total` is the field that usually becomes the document total.
- **entries** / **accountability_reports** / **vendors** / **subcategories** / **categories** / **units** — entry context for the dialog's `AttachmentAnalysisRow` and the linked-entries table.

## Derived shapes (computed per request, not stored)

### `TotalProvenance` (new — added to `GET /api/documents/[id]`)

Explains where `documents.total_value` came from.

| Field | Type | Meaning |
|-------|------|---------|
| `source` | `"gross" \| "rollup" \| "none"` | Which rule supplied the total: a page's `valor_total` gross, the roll-up `extracted_amount` fallback, or no AI total derivable. |
| `value` | `number \| null` | The selected total (the per-analysis value that equals the document's max). `null` when `source = "none"`. |
| `analysisId` | `string \| null` | The analysis that supplied the winning total. |
| `attachmentId` | `string \| null` | That analysis's attachment (for the dialog / provenance label). |
| `entryId` | `string \| null` | The entry that analysis belongs to (deep-link context). |
| `period` | `string \| null` | The period of that entry. |
| `sourcePageLabel` | `string \| null` | The page label (e.g. `p3`) whose `valor_total` was chosen; `null` when `source ≠ "gross"`. |

When the document has no analyzed attachment, `totalProvenance` is `null` (FR-006); the header then shows the standard "—"/`unknown` and a "no AI total derived" note.

### `AttachmentAnalysisRow` (existing type, newly carried by the document response)

The dialog's input — re-exported from `src/app/dashboard/entries/types.ts`. Attached to each distinct `imageSources[]` entry as `analysis: AttachmentAnalysisRow`. Same projection the alert route builds (roll-up fields + `entry*` context + `vendorName`/`subcategoryName`/`categoryName`).

## Selection-rule contract (the single source of truth)

A pure helper in `src/lib/documents.ts`:

```
selectReconciliationTotal(
  pages: Array<{ pageLabel: string | null; valorTotal: unknown }>,  // ordered by pageIndex asc
  rollup: number | null
): { value: number | null; source: "gross" | "rollup" | "none"; sourcePageLabel: string | null }
```

Rules (mirror `nf_total_for_reconciliation` + `_parse_brl_value` in `scripts/analysis/attachments.py`):

1. Walk `pages` in order; for the first whose `valorTotal` parses to a finite number `> 0`, return `{ value, source: "gross", sourcePageLabel }`.
2. Else, if `rollup` is a finite number, return `{ value: rollup, source: "rollup", sourcePageLabel: null }`.
3. Else `{ value: null, source: "none", sourcePageLabel: null }`.

`_parse_brl_value` parity: accept a `number` directly; for a string, strip `R$`/non-`[\d,.]`, treat `,` as decimal separator (Brazilian), reject non-finite/junk → `null`. **Drift-guard**: a comment binds this to the Python function; changing one requires changing the other.

The document's `totalProvenance` is the analysis whose `selectReconciliationTotal(...).value` is the **maximum** across all of the document's linked analyses (matching `documents.total_value = MAX(...)`), carrying that analysis's `source`/`sourcePageLabel`/ids.

## State transitions

None — entirely read/derive-on-read.
