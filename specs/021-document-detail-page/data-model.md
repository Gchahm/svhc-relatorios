# Phase 1 Data Model: Dedicated Document Detail Page

**No database schema change.** This feature is read-only and reuses existing tables. This document
describes the *view model* the detail API assembles and hands to the page.

## Source tables (read-only)

- `documents` — subject document identity (`id`, `documentNumber`, `issuerCnpj`, `issuerName`,
  `documentType`, `totalValue`).
- `document_entries` — N:N links (`documentId`, `entryId`, `sourceAttachmentId` provenance).
- `entries` — ledger entry (`id`, `date`, `description`, `amount`, `reportId`, `subcategoryId`,
  `vendorId`, `unitId`). **Live** amount.
- `accountability_reports` — `period` (YYYY-MM) for an entry's report (deep link target).
- `subcategories` → `categories` — entry category/subcategory names.
- `vendors`, `units` — entry vendor name and unit code (LEFT joins; may be null).
- `attachments` — `id`, `file_path` (page-image segments) for provenance images.
- `attachment_analyses` — `id` keyed uniquely by `attachmentId`; the id consumed by the existing
  page-image routes.

## View model (response of `GET /api/documents/[id]`)

```text
DocumentDetail {
  id: string
  documentNumber: string
  issuerCnpj: string
  issuerName: string | null
  documentType: string | null
  totalValue: number | null
  sumEntries: number            // live sum over linked entries
  status: "over" | "within" | "under" | "unknown"   // documentStatus(sumEntries, totalValue)

  entries: LinkedEntry[]
  imageSources: ImageSource[]
  relatedDocuments: RelatedDocument[]
}

LinkedEntry {
  entryId: string
  period: string                // YYYY-MM (for the entries deep link)
  date: string                  // YYYY-MM-DD
  description: string
  amount: number                // live
  category: string | null
  subcategory: string | null
  vendor: string | null
  unitCode: string | null
  sourceAttachmentId: string | null
}

ImageSource {
  attachmentId: string
  analysisId: string            // attachment_analyses.id → drives the existing page-image routes
  entryId: string               // a contributing entry (attribution)
  period: string                // that entry's period (attribution)
}
// One per DISTINCT provenance attachment that HAS an analysis. Attachments without an
// analysis or without file_path contribute no ImageSource (no image, no error).

RelatedDocument {
  id: string
  documentNumber: string
  issuerCnpj: string
  issuerName: string | null
  documentType: string | null
  totalValue: number | null
  sumEntries: number            // over the related doc's OWN full link set
  status: "over" | "within" | "under" | "unknown"
}
// Other documents sharing ≥1 entry with the subject; subject excluded; attachments excluded
// by construction (query is over the documents entity).
```

## Derivation rules

- **sumEntries (subject & related)**: sum of `entries.amount` over the document's own
  `document_entries` links. Live — never frozen at build time (FR-012).
- **status**: `documentStatus(sumEntries, totalValue)` from `src/lib/documents.ts` (shared tolerance,
  FR-003). `unknown` when `totalValue` is null/≤0.
- **imageSources**: distinct `document_entries.source_attachment_id` for the subject, inner-joined to
  `attachment_analyses` (so only attachments with an analysis appear), de-duplicated by `analysisId`.
- **relatedDocuments**: `DISTINCT d2` where `∃ de2(d2, e) ∧ ∃ de1(subject, e)` and `d2 ≠ subject`;
  aggregates computed per `d2` over its own links.

## Validation / states

- Subject document not found → 404 (FR-010 → "not found" UI state).
- Document with zero links → `entries: []`, `sumEntries: 0`, `imageSources: []`,
  `relatedDocuments: []`; header still renders.
- Auth: role ∈ {admin, member} or 403 (FR-011), matching the existing route.
