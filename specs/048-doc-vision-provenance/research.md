# Phase 0 Research: Vision Extraction Provenance

All unknowns resolve to existing code. No external/library research was required.

## Decision 1: Reuse the existing extraction dialog instead of building a new view

- **Decision**: Open `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx` from the document detail page, passing an `AttachmentAnalysisRow` (the same shape the alert detail page already passes).
- **Rationale**: The dialog already renders exactly what the feature asks for — the roll-up summary, per-page extracted fields (`valor_total`/`valor_liquido`/`valor_pago`/issuer/date/number/role), parse errors, and the page image — and it self-fetches its per-page records and images by `analysis.id` from the already auth-gated `/api/attachment-analyses/[id]` and `/[id]/pages` routes. FR-001 explicitly requires reuse, not a divergent view. Constitution V (reuse before new primitives).
- **Alternatives considered**: A bespoke inline extraction panel on the document page — rejected (duplicates a tested component, risks drift in field labels/currency formatting).

## Decision 2: The document API supplies the `AttachmentAnalysisRow` (the dialog's input)

- **Decision**: Extend `GET /api/documents/[id]` to attach a full `AttachmentAnalysisRow` to each distinct image source, joining the analysis to its own entry (`attachments.entry_id`) for the entry-context fields the dialog shows.
- **Rationale**: The dialog needs roll-up fields + entry context (date, description, amount, movement type, vendor, subcategory, category) that the current document response does not carry. The alert route (`/api/alerts/[id]`) already builds this exact projection; mirroring its `analysisRows` select keeps the two consistent. The route already exposes `imageSources[].analysisId`, so no new linkage is invented (spec Assumption 1).
- **Alternatives considered**: Have the client fetch `/api/attachment-analyses/[id]` and synthesize the row — rejected: that endpoint returns per-page records, not the roll-up + entry context the dialog's `analysis` prop needs; the server already has the joins cheaply.

## Decision 3: Single source of truth for the total-selection rule

- **Decision**: Add a pure helper to `src/lib/documents.ts` — given an ordered list of per-page parsed responses plus the roll-up `extractedAmount`, return `{ value, source: "gross" | "rollup" | "none", sourcePageLabel }`. It mirrors the Python `nf_total_for_reconciliation` (prefer the first page whose `valor_total` parses to `> 0`, else the roll-up amount, else none) and the `_parse_brl_value` tolerance (accept number or BRL string). The API computes each linked analysis's total with this helper; the document's `totalProvenance` is the analysis/page producing the **max** (matching how `documents.total_value` is built — `MAX` across the key's analyses).
- **Rationale**: FR-003 requires the UI attribution to equal the pipeline's computed value with no drift. `documents.ts` is already the shared home for the reconciliation tolerance (mirrors `nf_groups.py`) with a drift-guard comment + cross-language contract test, so the gross-selection rule belongs beside it. A drift-guard comment will point at `scripts/analysis/attachments.py:nf_total_for_reconciliation`.
- **Ordering note**: the Python loads per-page records without an explicit `ORDER BY` and takes the first `valor_total > 0`. The helper (and the API feeding it) orders pages by `pageIndex` ascending for determinism; this is identical to Python whenever an analysis has a single invoice page carrying a gross (the normal case) and is a safe, documented tie-break otherwise.
- **Alternatives considered**: Recompute the rule client-side from raw responses — rejected (ships more data, duplicates the rule in a second place, invites drift). Reading a stored provenance column — rejected (no such column; this is pure derived data and adding one is out of scope / a schema change).

## Decision 4: Alert side is reinforcement, not new capability

- **Decision**: The alert detail page already reaches the same dialog per affected entry via its "View Attachment" button (`AlertDetailClient` + `analysisByEntry`). For FR-005, add only a localized **"AI-extracted"** annotation on total-driven alert evidence (e.g. `document_overpayment`, `attachment_amount_mismatch`) so the disputed figure is recognizably AI-sourced.
- **Rationale**: Reachability exists; the gap is the explicit labeling. Keeping the change minimal honors Constitution V and keeps Story 3 (P2) small.
- **Alternatives considered**: Duplicating the full provenance line on the alert page — deferred; the document page is the canonical place for total provenance, and the alert links to the referenced document already.

## Decision 5: Testing approach

- **Decision**: Extend `src/lib/documents.test.mjs` with `node:test` cases for the selection helper (gross-wins, first-confident-gross, rollup-fallback, none, BRL-string parsing, max-across-analyses attribution). Catalog completeness is already enforced by `catalog.test.mjs`.
- **Rationale**: Cheap, matches the existing test pattern, and directly verifies FR-003 (no drift). Constitution III keeps tests optional but they are warranted by an explicit consistency requirement.
