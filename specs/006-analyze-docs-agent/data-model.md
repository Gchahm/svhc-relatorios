# Phase 1 Data Model: Claude Vision Agent for Document Analysis

This feature introduces **two working-file formats** and preserves the existing persisted shapes.
No D1 schema change. Entities below are file/in-memory structures in the analysis pipeline.

## Preserved (unchanged) — persisted shapes

These are produced exactly as today by the deterministic pipeline; documented here only to pin the
compatibility contract.

### `document_analyses` row (period JSON → D1 table)

Fields (from `DocAnalysisResult.to_dict`): `id`, `document_id`, `analyzed_at`, `document_type`,
`extracted_amount`, `amount_match` (1/0/null), `extracted_cnpj`, `issuer_name`, `vendor_match`,
`extracted_date`, `date_match`, `document_number`, `service_description`, `raw_response` (legacy,
stays `null`), `error`, `analysis_records[]` (nested; flattened on import).

### `document_analysis_records` row (nested `analysis_records` → D1 table)

Fields (from `PageAnalysisRecord.to_dict`): `id`, `document_analysis_id`, `analysis_type`
(`"page_extraction"`), `page_index`, `page_label`, `artifact_role`, `response` (the page-extraction
fields object), `raw_text` (kept only on parse failure), `parse_error`, `analyzed_at`.

**Invariant**: byte-shape identical to the current flow → `scripts/import-to-d1.mjs` imports without
modification (SC-003).

## New — Work manifest (`<period>.extract-todo.json`)

Written by `docs-plan`; read by the `classify-period` skill and by `apply-extractions`. Carries
everything needed so `apply` never re-runs selection.

```jsonc
{
    "period": "2025-12",
    "data_dir": "../data/scrape",
    "generated_for": { "min_amount": null, "limit": null, "reanalyze": false, "document_ids": null, "entry_ids": null },
    "groups": [
        {
            "group_key": "<content-hash or doc:<id>>",
            "representative_document_id": "<uuid>",
            "group_size": 2,
            "sibling_sum": 1234.5, // sum of member entry amounts over the FULL group
            "pages": [
                {
                    "page_index": 0,
                    "page_label": "p1",
                    "path": "../data/scrape/2025-12/<id>_p1.jpg", // extraction key (relative-to-scripts)
                    "read_path": "/abs/path/.../<id>_p1.jpg", // absolute, for the skill's Read tool
                },
            ],
            "members": [
                {
                    "document_id": "<uuid>",
                    "entry_id": "<uuid>",
                    "entry_amount": 617.25,
                    "vendor_name": "ACME LTDA", // resolved at plan time (may be null)
                    "is_representative": true,
                },
            ],
        },
    ],
}
```

**Rules / validation**:

- One `group` per shared-NF group; exactly one member has `is_representative: true`, and its
  `document_id` equals `representative_document_id`.
- `pages` are the representative's page images only (siblings are byte-identical → reuse).
- `sibling_sum` and `group_size` are over the full group (every member entry), matching today's
  reconciliation, even for members excluded from extraction by filters.
- Singletons (no shared NF, or unhashable pages) are groups of `group_size: 1`.

## New — Per-page classification files (`<image-stem>.classify.json`)

> **Evolution note:** originally a single `<period>.extractions.json` map written by the agent. Now
> one file **per page image**, written next to the image by the `classify-doc-page` skill, and read
> by `apply-extractions`. Per-page values/errors are unchanged; only the layout and producer changed.

Written by the `classify-doc-page` skill (one per page); read by `apply-extractions`. Each file is
either the extracted fields or a per-page error.

```jsonc
// …/<id>_p1.classify.json
{
    "papel_artefato": "invoice",
    "tipo_documento": "NF-e",
    "valor_total": 617.25,
    "valor_liquido": null,
    "valor_pago": null,
    "cnpj_emitente": "12.345.678/0001-90",
    "nome_emitente": "ACME LTDA",
    "data_emissao": "03/12/2025",
    "numero_documento": "12345",
    "descricao_servico": "Serviço de limpeza",
}
// …/<id>_p2.classify.json  ->  { "error": "page illegible" }
```

**Rules / validation**:

- Each file is EITHER the page-extraction fields (see `contracts/page-extraction-fields.md`) OR
  `{ "error": "<reason>" }` — never both.
- Amounts may be numeric or BRL-formatted strings; absent fields are `null` (never invented).
- The sibling path is derived from the image path (`extractions.classify_path_for`). A manifest page
  whose `.classify.json` is missing is treated as a per-page error
  (`"no classification for page (run classify-doc-page)"`) — it does not abort the document.

## New — Mismatch summary (vision-step hand-back)

The terse, machine-readable list the `analyze-docs` agent returns (via the `mismatches` command):
one item per mismatch — `kind` (amount / vendor / date / page-error / duplicate_billing), its
document/entry, and ledger-vs-extracted values. This is the context-clean hand-back to a caller
(no images or artifacts). See feature `007-classification-improve-loop`.

## Entity relationships

```
Period JSON ──(docs-plan: select_work + group_documents)──▶ Work manifest (scoped to period or doc subset)
                                                                  │
                Work manifest.groups[].pages[].read_path ─────────┤
                                                                  ▼
                                   classify-period → classify-doc-page SKILLS (vision, per page)
                                                                  │ each writes
                                                                  ▼
                                                  <image>.classify.json (one per page)
                                                                  │
Work manifest + per-page classify files ──(apply-extractions)──▶ document_analyses (+ records)
   │  per representative: FileExtractionProvider → PageAnalysisRecord → _map_artifact_role → _rollup
   │  per group: _apply_group_amount_match / reconcile_group ; fan out via _fanout_result
   │  per member: entry vendor/date/amount validation ; _merge_and_write into Period JSON
   ▼
analyze (checks, incl. duplicate_billing) ──▶ mismatches summary ──▶ analyze-docs agent return value
```

## In-memory provider seam

`ExtractionProvider`: callable `path -> (parsed: dict | None, error: str | None)`.

- `FileExtractionProvider()` (stateless) resolves the page image's sibling `.classify.json`
  (`classify_path_for`) and returns `(fields, None)` for a fields object, `(None, reason)` for an
  `{error}` object, and `(None, "no classification for page …")` when the file is absent/unreadable.
  This is the single seam that replaced the VLM; `build_document_analysis` calls it per page instead
  of the removed `_analyze_page`.
