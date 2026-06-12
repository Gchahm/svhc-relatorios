# Implementation Plan: Correct `Entry.id` client type to UUID string

**Branch**: `031-entry-id-string-type` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/031-entry-id-string-type/spec.md`

## Summary

The entries-ledger client types its row id as `number` while the data is a text UUID string,
forcing `String(...)` coercion at every id call site. Correct the client `Entry.id` type to
`string`, delete the now-redundant `String(e.id)` / `String(entry.id)` wrappers, and (per
A-003) extract the shared row types (`Entry`, `AttachmentAnalysisRow`) out of the
`EntriesClient` component module into a sibling `types.ts` so `AttachmentAnalysisDetailDialog`
and the alert-detail client import types from a module instead of from a component. Pure
type-correctness refactor — no behavior, data, schema, or API change.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)
**Primary Dependencies**: @tanstack/react-virtual, shadcn/ui, lucide-react (all existing — none added)
**Storage**: Cloudflare D1 (read-only here; `entries.id` is `text` UUID — no schema change)
**Testing**: No test framework configured; verification is `pnpm lint` + `tsc` (via `pnpm build`) + manual UI check (`verify` skill)
**Target Platform**: Cloudflare Workers via OpenNext
**Project Type**: Web application (Next.js App Router, single repo)
**Performance Goals**: N/A (no runtime cost change; removing coercion is neutral-to-faster)
**Constraints**: Mirror-table invariant unaffected (frontend read path only); no new dependency
**Scale/Scope**: 3 source files touched (`EntriesClient.tsx`, `AttachmentAnalysisDetailDialog.tsx`, `alerts/[id]/AlertDetailClient.tsx`) + 1 new `types.ts`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — DIRECTLY ADVANCED. The change makes the client type
  honest against the Drizzle schema (`entries.id` text) and the API payload; no `any`
  introduced; no schema/migration touched (D1 unchanged).
- **II. Cloudflare-Native Architecture** — UNAFFECTED. No DB access path changes; this is a
  client-side type declaration.
- **III. Quality Gates Before Commit** — HONORED. `pnpm lint` + `pnpm format` (and `tsc` via
  build) run before commit; manual UI verification per the `verify` skill.
- **IV. Security & Auth by Default** — UNAFFECTED. No auth or route-protection change.
- **V. Simplicity & Incremental Delivery** — ADVANCED. Net code reduction (deletes coercion
  wrappers); the shared-types extraction is a small, contained move that reduces coupling.

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/031-entry-id-string-type/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (no API contracts — see note)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/app/dashboard/entries/
├── EntriesClient.tsx                 # MODIFY: import types from ./types; delete String() wrappers
├── AttachmentAnalysisDetailDialog.tsx# MODIFY: import AttachmentAnalysisRow from ./types
├── types.ts                          # NEW: shared Entry + AttachmentAnalysisRow row types
└── page.tsx                          # UNCHANGED

src/app/dashboard/alerts/[id]/
└── AlertDetailClient.tsx             # MODIFY: import AttachmentAnalysisRow from ../../entries/types
```

**Structure Decision**: Existing Next.js App Router layout. The shared row types move to a new
`src/app/dashboard/entries/types.ts` co-located with the entries feature (its canonical owner),
keeping the import distance short for the cross-feature consumer in `alerts/[id]`.

## Complexity Tracking

No constitution violations — section intentionally empty.
