# Implementation Plan: Shared alert type → label map

**Branch**: `038-alert-type-labels` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/038-alert-type-labels/spec.md`

## Summary

Add one pure module `src/lib/alerts.ts` exporting `alertTypeLabel(type: string): string` — a curated
`type → label` map for every alert type the pipeline currently emits, with a generic
`snake_case → Title Case` fallback for anything not curated (and total/never-throwing on empty or
malformed input). Route the three type-rendering alert surfaces through it: the alerts list **Type
filter** options (`AlertsClient.tsx`), the alert **detail page** Type field (`AlertDetailClient.tsx`),
and any future list type rendering. Presentation-only: no data, schema, API, or behavior change.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router, client components)  
**Primary Dependencies**: Existing only — React; no new npm dependency. Unit test via Node's
built-in `node:test`/`node:assert` with native TS type-stripping (the pattern feature 036 set for
`src/lib/documents.ts` → `src/lib/documents.test.mjs`).  
**Storage**: N/A — reads no data, writes nothing.  
**Testing**: `node --test` over a `src/lib/alerts.test.mjs` importing `alerts.ts` directly (no bundler).  
**Target Platform**: Cloudflare Workers (browser-rendered client components).  
**Project Type**: Web app (single Next.js project).  
**Performance Goals**: N/A (trivial pure string lookup).  
**Constraints**: Function must be pure and total (never throws). One module owns the mapping.  
**Scale/Scope**: One new ~40-line module + one test file; two small edits to existing client components.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS — typed signature `(type: string) => string`, no
  `any`, no schema/migration (no persisted data touched).
- **II. Cloudflare-Native Architecture**: PASS — no DB/binding access; pure client/lib code.
- **III. Quality Gates Before Commit**: PASS — `pnpm lint` + `pnpm format` before commit; a unit
  test covers curated/unknown/empty/non-snake inputs.
- **IV. Security & Auth by Default**: PASS — no auth surface, no new route, no user input persisted.
- **V. Simplicity & Incremental Delivery**: PASS — smallest possible change: one helper + two call
  sites; the generic fallback removes any need to ever touch call sites for new types.

No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/038-alert-type-labels/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the module's public contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── lib/
│   ├── alerts.ts            # NEW — alertTypeLabel() curated map + snake_case→Title Case fallback
│   └── alerts.test.mjs      # NEW — node:test unit test (mirrors documents.test.mjs)
└── app/dashboard/alerts/
    ├── AlertsClient.tsx     # EDIT — typeOptions label uses alertTypeLabel(v)
    └── [id]/
        └── AlertDetailClient.tsx  # EDIT — Type field value uses alertTypeLabel(alert.type)
```

**Structure Decision**: Single Next.js project. The pure mapping lives in `src/lib/` (framework-
agnostic, unit-testable without React), matching the existing `src/lib/documents.ts` precedent. The
existing alert UI helpers in `src/app/dashboard/alerts/alerts.tsx` (entry links, evidence fields,
severity/status badges) stay put — this feature adds only the type-label concern.

## Complexity Tracking

> No constitution violations — section intentionally empty.
