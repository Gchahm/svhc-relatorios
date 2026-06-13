# Implementation Plan: Localize detail pages, dialogs, and notices to pt-BR (I18N-004)

**Branch**: `042-i18n-detail-surfaces` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/042-i18n-detail-surfaces/spec.md`

## Summary

Migrate every user-facing chrome string in the dashboard's drill-down surfaces (alert detail,
document detail, attachment-analysis dialog, page-image viewer, and the entries deep-link not-found
notice) from inline English literals into the existing I18N-001 catalog, rendering pt-BR by default.
Replace per-file currency/date helpers with the I18N-001 locale-aware client formatters, render the
alert *type* through the localized label map (`useAlertTypeLabel`), and keep all fiscal data
(vendor/issuer names, NF numbers, CNPJs, extracted values) verbatim. Presentation-only: no data,
schema, API, or behavior change.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router); Node 22 for the test runner
**Primary Dependencies**: Existing only — the I18N-001 layer (`@/lib/i18n`, `@/lib/i18n/client`,
`@/lib/i18n/formatters.client`), shadcn/ui, lucide-react. **No new npm dependency.**
**Storage**: N/A — reads no new data, writes nothing; no D1 schema/migration.
**Testing**: Node's built-in `node:test`/`node:assert` via the existing catalog-completeness test
(`src/lib/i18n/catalog.test.mjs`), extended to cover the new keys. Manual verification in the running
app (ui-login + verify skills) against local D1 prod-like data.
**Target Platform**: Cloudflare Workers (browser-rendered client components).
**Project Type**: Web (Next.js App Router) — single app, client-component presentation layer.
**Performance Goals**: No change — translation is a synchronous in-memory catalog lookup.
**Constraints**: Must not drag server-only code into client bundles — client components import from
`@/lib/i18n/client` and `@/lib/i18n/formatters.client` (NOT the server barrel `@/lib/i18n`), per the
documented bundle-safety boundary.
**Scale/Scope**: 4 components to edit (the 5th, the EntriesClient notice, is already localized — verify
only), plus catalog additions in `src/lib/i18n/catalog.ts` and its test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. New catalog keys are added to the typed `CatalogShape`,
  so both pt-BR and en entries are compile-checked; no `any`; no DB schema change.
- **II. Cloudflare-Native Architecture**: PASS. No DB access. Client components use the client-safe
  i18n entrypoints; no `getCloudflareContext` pulled into client bundles.
- **III. Quality Gates Before Commit**: PASS. `pnpm lint` + `pnpm format` run before commit; the
  catalog-completeness test is extended and MUST pass.
- **IV. Security & Auth by Default**: PASS. No routes added/changed; surfaces stay auth-gated.
- **V. Simplicity & Incremental Delivery**: PASS. Reuses the established catalog/formatter/label-map
  mechanism; no new abstraction or dependency. Delivered as prioritized user stories (P1 alert &
  document detail → P2 dialog/viewer → P3 notice verification).

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/042-i18n-detail-surfaces/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (catalog key inventory)
├── quickstart.md        # Phase 1 output (verification steps)
├── checklists/
│   └── requirements.md  # spec quality checklist (done in specify)
├── contracts/           # Phase 1 output (N/A note — no API/contract change)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── lib/i18n/
│   ├── catalog.ts            # ADD new keys (CatalogShape + pt-BR + en)
│   └── catalog.test.mjs      # EXTEND completeness coverage for new keys
└── app/dashboard/
    ├── alerts/[id]/AlertDetailClient.tsx          # EDIT — localize, drop local formatters, use useAlertTypeLabel
    ├── documents/[id]/DocumentDetailClient.tsx    # EDIT — add i18n hooks, localize, drop local formatter
    └── entries/
        ├── AttachmentAnalysisDetailDialog.tsx     # EDIT — add i18n hooks, localize, drop local formatter
        ├── PageImageViewer.tsx                     # EDIT — localize own strings + accept localized alt
        └── EntriesClient.tsx                       # VERIFY ONLY — notice already localized (A2)
```

**Structure Decision**: Web app (Next.js App Router). All edits are in existing client components and
the shared i18n catalog; no new files except the spec artifacts. The `contracts/` dir holds only a
note that there is no API contract change.

## Phase 0: Research

See [research.md](./research.md). No NEEDS CLARIFICATION markers — the only decisions are catalog key
naming/grouping and the client vs server import boundary, both resolved against the existing I18N-001
conventions and the prior I18N-003 feature (041) as precedent.

## Phase 1: Design

- [data-model.md](./data-model.md) — the catalog key inventory (new sections/keys, the pt-BR + en
  strings, and which existing keys are reused vs added).
- [quickstart.md](./quickstart.md) — how to verify each surface in the running app.
- [contracts/README.md](./contracts/README.md) — explicit "no contract change" note.
- Agent context updated via `update-agent-context.sh`.

## Complexity Tracking

No constitution violations — section intentionally empty.
