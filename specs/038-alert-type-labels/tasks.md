# Tasks: Shared alert type → label map

**Feature**: 038-alert-type-labels | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests included (the spec's SC-004 requires a never-throws guarantee + the documents.test.mjs precedent).

## Phase 1: Setup

- [X] T001 Confirm Node version supports native TS type-stripping for `.test.mjs` (Node ≥ 22.18) by running `node --version` and the existing `node --test "src/**/*.test.mjs"`, so the new test will run.

## Phase 2: Foundational (blocking — shared module)

- [X] T002 Create the pure module `src/lib/alerts.ts` exporting `ALERT_TYPE_LABELS: Record<string, string>` (the 19 curated entries from `specs/038-alert-type-labels/data-model.md`) and `alertTypeLabel(type: string): string` — curated lookup with a `snake_case → Title Case` (sentence-case) fallback, `"" → ""`, never throws (per `contracts/alerts.md`).

## Phase 3: User Story 1 — Readable alert type filter (P1) 🎯 MVP

**Goal**: Type filter options render human-readable labels while filtering by the raw value.
**Independent test**: Open `/dashboard/alerts`, open the Type filter — labels are readable; selecting one still filters.

- [X] T003 [US1] In `src/app/dashboard/alerts/AlertsClient.tsx`, import `alertTypeLabel` from `@/lib/alerts` and change `typeOptions` to map each distinct type to `{ value: v, label: alertTypeLabel(v) }` (keep `value` as the raw type so filtering is unaffected).

## Phase 4: User Story 2 — Readable type on the detail page (P2)

**Goal**: The detail page Type field shows the friendly label.
**Independent test**: Open any alert's detail page — the Type field shows the curated/fallback label.

- [X] T004 [US2] In `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx`, import `alertTypeLabel` from `@/lib/alerts` and render the Type `<Field>` value as `alertTypeLabel(alert.type)`.

## Phase 5: User Story 3 — No surface renders raw type (P3)

**Goal**: Every alerts surface that renders a type routes through the shared function.
**Independent test**: Grep alerts UI for `\.type` rendering; none renders the raw string directly.

- [X] T005 [US3] Grep `src/app/dashboard/alerts/` for any remaining surface that renders an alert `type` as user-facing text; if found, route it through `alertTypeLabel`. (Expected: only T003/T004 sites exist; this is the consistency guarantee.)

## Phase 6: Polish & Cross-Cutting

- [X] T006 [P] Add `src/lib/alerts.test.mjs` (Node `node:test`, mirrors `src/lib/documents.test.mjs`): assert every `ALERT_TYPE_LABELS` key maps to its curated label; an uncurated snake_case input → sentence-cased label with no underscores; `""` → `""`; a single non-snake word → capitalized; no input throws.
- [X] T007 Run `node --test "src/**/*.test.mjs"`, then `pnpm lint` and `pnpm format`; fix any issues.
- [X] T008 Verify in the running app per `quickstart.md` (ui-login → check filter + detail page).

## Dependencies

- T002 blocks T003, T004, T005, T006 (all import the module).
- T001 is independent setup.
- T003/T004/T005 touch different files and may proceed in parallel once T002 lands.
- T006 may proceed in parallel with T003–T005 (different file).
- T007/T008 run last (gates + verification).

## Parallel example

After T002: T003, T004, T006 can run in parallel ([P] on T006; T003/T004 are different files).

## Implementation strategy

MVP = Phase 1 + 2 + Phase 3 (the filter, the issue's cited surface). Phases 4–5 are small,
independent increments that complete the "no surface renders raw" guarantee.
