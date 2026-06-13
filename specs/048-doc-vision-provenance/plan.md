# Implementation Plan: Vision Extraction Provenance on Document & Alert Detail

**Branch**: `048-doc-vision-provenance` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/048-doc-vision-provenance/spec.md`

## Summary

Make the AI (vision-model) extraction that produced a document's total figure visible and traceable from the document detail page, and reinforce the same on the alert detail page. Two deliverables: (1) open the **existing** `AttachmentAnalysisDetailDialog` from the document detail page (the per-page extracted fields + page images), and (2) display a **total-provenance** line on the document header naming the page + field (or roll-up fallback) the total came from — computed by a shared helper that mirrors the pipeline's `nf_total_for_reconciliation` selection rule so the UI explanation can't drift from the computed value. Presentation-layer only: no D1 schema change, no migration, no pipeline change, no new dependency; `/api/documents/[id]` is extended to carry the analysis rows + a `totalProvenance` object it already has the data to compute.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router); Node 22 for the test runner
**Primary Dependencies**: Existing only — Drizzle ORM (D1), better-auth, shadcn/ui (card, badge, button, dialog), lucide-react, the I18N-001 catalog (`@/lib/i18n`), `@tanstack/react-virtual` (already in lists). No new npm/pip dependency.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`), tables `documents`, `document_entries`, `entries`, `attachments`, `attachment_analyses`, `attachment_analysis_records`, plus the entry-context joins — all **read-only** here. Page images in R2 via the existing image routes. No schema change, no migration.
**Testing**: Node's built-in `node:test` / `node:assert` via native TS type-stripping (the existing `src/lib/documents.test.mjs` / `catalog.test.mjs` pattern). No new framework.
**Target Platform**: Cloudflare Workers (via `@opennextjs/cloudflare`); auth-gated dashboard.
**Project Type**: Web (Next.js App Router single project under `src/`).
**Performance Goals**: Standard dashboard interactivity; the document detail request already runs these joins — the additions are one extra column and one in-memory pass.
**Constraints**: Reuse the existing extraction dialog (no divergent view); the UI total attribution MUST equal the value the pipeline used; all new text via the pt-BR catalog.
**Scale/Scope**: A handful of files: one API route extended, one client extended, one shared lib helper + its test, the alert client + evidence helper touched lightly, and catalog keys. No new pages.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No schema change (read-only over existing tables). New shapes are typed; no `any`. No auth schema change.
- **II. Cloudflare-Native Architecture** — PASS. DB access stays through `await getDb()`; no new bindings; image bytes still flow through the existing auth-gated R2 routes.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` before commit. The spec's consistency requirement (FR-003) is covered by a unit test extending `src/lib/documents.test.mjs` (tests are optional per the constitution but cheap and warranted here).
- **IV. Security & Auth by Default** — PASS. No new public surface; the extended `/api/documents/[id]` keeps its `ALLOWED_ROLES` gate; the dialog self-fetches via the already auth-gated `/api/attachment-analyses/*` routes.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses `AttachmentAnalysisDetailDialog`, `PageImageViewer`, `documentStatus`, and the existing `imageSources[].analysisId` linkage rather than adding components or endpoints. Stories are independently shippable (P1 dialog → P1 provenance → P2 alert reinforcement).

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/048-doc-vision-provenance/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the extended /api/documents/[id] response shape)
└── tasks.md             # Phase 2 output (speckit tasks — not created here)
```

### Source Code (repository root)

```text
src/
├── lib/
│   ├── documents.ts                 # ADD: shared reconciliation-total selection helper
│   │                                #      (mirrors nf_total_for_reconciliation + _parse_brl_value)
│   └── documents.test.mjs           # ADD: unit cases for the selection helper
├── app/
│   ├── api/
│   │   └── documents/[id]/route.ts  # EXTEND: select extractedAmount + page valor_total/pageIndex;
│   │                                #         compute totalProvenance; attach AttachmentAnalysisRow
│   │                                #         per distinct analysis to imageSources
│   └── dashboard/
│       ├── documents/[id]/DocumentDetailClient.tsx  # EXTEND: provenance line + "view AI extraction"
│       │                                            #         control opening the existing dialog
│       ├── entries/AttachmentAnalysisDetailDialog.tsx  # REUSE unchanged (consumed from doc page)
│       └── alerts/
│           ├── [id]/AlertDetailClient.tsx  # LIGHT: label total-driven figures as AI-extracted
│           └── alerts.tsx (evidence helper) # LIGHT: flag AI-extracted total fields if needed
└── lib/i18n/catalog.ts              # ADD: new keys (CatalogShape + pt-BR + en) for provenance/labels
```

**Structure Decision**: Single Next.js App Router project (existing). The change is confined to the documents + alerts dashboard surfaces, their backing `/api/documents/[id]` route, the shared `src/lib/documents.ts` helper (single source of truth for the selection rule), and the i18n catalog. No new directories.

## Phase 0: Research

See [research.md](./research.md). All technical unknowns are resolved from the existing codebase (the dialog, the API linkage, and the Python selection rule are all already present); no external research needed.

## Phase 1: Design & Contracts

- [data-model.md](./data-model.md) — read-only entities + the derived `totalProvenance` shape and the selection-rule contract.
- [contracts/api-documents-id.md](./contracts/api-documents-id.md) — the extended `GET /api/documents/[id]` response (added `totalProvenance` + per-source `analysis`).
- [quickstart.md](./quickstart.md) — how to verify locally (seeded period + the over/under document).

## Complexity Tracking

> No constitution violations. Section intentionally empty.
