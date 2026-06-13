# Contract: `GET /api/documents/[id]` (extended)

Auth: unchanged — better-auth session with role in `{admin, member}`, else `403`. `404` when the document id is unknown.

## Additions (backward-compatible)

The response keeps every existing field (`id`, `documentNumber`, `issuerCnpj`, `issuerName`, `documentType`, `totalValue`, `sumEntries`, `status`, `entries`, `imageSources`, `relatedDocuments`) and adds:

### 1. `totalProvenance` (top-level, nullable)

```jsonc
"totalProvenance": {
  "source": "gross",          // "gross" | "rollup" | "none"
  "value": 800.0,             // number | null  (the per-analysis total equal to the document max)
  "analysisId": "…",          // string | null
  "attachmentId": "…",        // string | null
  "entryId": "…",             // string | null
  "period": "2025-12",        // string | null
  "sourcePageLabel": "p3"     // string | null  (only when source === "gross")
}
```

`null` when the document has no analyzed attachment at all. `source: "none"` when analyses exist but none yields a confident total (then `value`/`sourcePageLabel` are `null`, ids may still point at an analysis for the dialog).

### 2. `imageSources[].analysis` (per distinct source, nullable)

Each `imageSources[]` entry gains an `analysis` field carrying the full `AttachmentAnalysisRow` (the shape from `src/app/dashboard/entries/types.ts`) for that source's analysis — roll-up fields plus the analysis's own entry context (`entryId`, `entryDate`, `entryDescription`, `entryAmount`, `entryMovementType`, `vendorName`, `subcategoryName`, `categoryName`). This is what the document detail page hands to `AttachmentAnalysisDetailDialog`.

```jsonc
"imageSources": [
  {
    "attachmentId": "…",
    "analysisId": "…",
    "entryId": "…",
    "period": "2025-12",
    "documentPageLabel": "p3",
    "pages": [ /* unchanged: {pageLabel,pageIndex,imageUrl,artifactRole,roleLabel,isDocument} */ ],
    "analysis": { /* AttachmentAnalysisRow | null */ }
  }
]
```

## Consumers

- `DocumentDetailClient` reads `totalProvenance` for the header provenance line and opens `AttachmentAnalysisDetailDialog` with `imageSources[].analysis` (and a dedicated control resolving the provenance's `analysisId`).
- The dialog continues to self-fetch `/api/attachment-analyses/[id]` + `/[id]/pages` + `/[id]/image/[page]` (unchanged, auth-gated).

## Non-goals

- No new endpoint. No change to `/api/documents` (list), `/api/attachment-analyses/*`, or `/api/alerts/[id]` response *shapes* (the alert client change is presentational, reusing fields it already receives).
- No schema/migration change.
