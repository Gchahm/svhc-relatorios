# Implementation Plan: Type-aware extraction UI

**Branch**: `057-type-aware-extraction-ui` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/057-type-aware-extraction-ui/spec.md`

## Summary

Make `AttachmentAnalysisDetailDialog`'s per-page record view **type-aware**: when a stored response is a typed transcription (carries `doc_type`), render it grouped by the document's natural structure with localized labels, and visibly mark the fields the deterministic reconciliation mapper derives its values from (total / issuer / number / date / service), labelled with the role they feed. `outro`/unknown/malformed typed records fall back to the existing generic flatten view; legacy flat records and error/unparseable records render exactly as today. UI-only — no schema, no pipeline, no API, no stored-format change.

The provenance (which transcribed field becomes which reconciliation value, per type) mirrors `scripts/analysis/type_mappers.py`. It is extracted into a **pure, testable TypeScript module** (`typed-transcription.ts`) — the doc-type-aware row builder plus the provenance map — that the dialog consumes, so the rendering logic is unit-testable with `node:test` (the repo's existing `.test.mjs` pattern) and the provenance can be asserted field-by-field against the documented mapper rules.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 (Next.js 15 App Router, client component)  
**Primary Dependencies**: existing — shadcn/ui (Badge, Dialog), the i18n catalog (`@/lib/i18n`), `formatCurrency`. No new dependency.  
**Storage**: N/A (read-only consumer of `attachment_analysis_records.response`; no DB/schema change)  
**Testing**: `node --test "src/**/*.test.mjs"` (`pnpm test:ts`) — pure module unit tests importing the `.ts` directly, as `deeplinkView.test.mjs` does. The existing `catalog.test.mjs` enforces catalog parity.  
**Target Platform**: Cloudflare Workers (OpenNext) browser client  
**Project Type**: Web (single Next.js app)  
**Performance Goals**: N/A (renders a handful of fields per page in an already-open dialog)  
**Constraints**: must never throw on a partial/odd typed shape; no hardcoded display strings (all chrome via catalog); pt-BR + en catalogs stay in parity (enforced by `catalog.test.mjs`)  
**Scale/Scope**: one component (`AttachmentAnalysisDetailDialog.tsx`), one new pure helper module + its test, catalog additions in `src/lib/i18n/catalog.ts`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS — TypeScript, no `any` without justification; no schema change (UI-only), so no migration/Drizzle concern.
- **II. Cloudflare-Native Architecture**: PASS — no DB access added; consumes the existing `/api/attachment-analyses/[id]` payload already fetched by the dialog.
- **III. Quality Gates Before Commit**: PASS — `pnpm lint` + `pnpm format` will run; tests are added for the new pure module (the spec requests them, SC-005), and `pnpm test` must pass.
- **IV. Security & Auth by Default**: PASS — no new route; the dialog is already inside the auth-gated dashboard.
- **V. Simplicity & Incremental Delivery**: PASS — reuses existing Badge/Field primitives and the existing flatten fallback; introduces one small pure helper module rather than a per-type component zoo. The provenance is a data table, not new abstraction layers.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/057-type-aware-extraction-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (provenance contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── app/dashboard/entries/
│   ├── AttachmentAnalysisDetailDialog.tsx     # MODIFY: consume the type-aware builder for typed records
│   ├── typed-transcription.ts                 # NEW: pure doc-type-aware row/section builder + provenance map
│   └── typed-transcription.test.mjs           # NEW: node:test unit tests for the builder + provenance
└── lib/i18n/
    ├── catalog.ts                             # MODIFY: add analysis.* section/role/label keys (pt-BR + en + type)
    └── catalog.test.mjs                       # (existing parity test — keys must stay in parity)
```

**Structure Decision**: Single Next.js app (web). The rendering decision logic lives in a pure, dependency-light `.ts` module (`typed-transcription.ts`) so it is unit-testable with the repo's `node --test` `.test.mjs` convention (mirrors `deeplinkView.ts` / `deeplinkView.test.mjs`). The component keeps only React/presentation concerns; the builder returns plain data (sections → rows, each row optionally tagged with a provenance role) that the component maps to `Field`/`Badge` elements. The provenance map is the single TS source of truth mirroring the Python mapper.

## Complexity Tracking

> No constitution violations — section intentionally empty.
