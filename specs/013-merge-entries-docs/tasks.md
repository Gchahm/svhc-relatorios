---
description: "Task list for merging Document Analyses into the Entries page"
---

# Tasks: Merge Document Analyses into the Entries page

**Input**: Design documents from `/specs/013-merge-entries-docs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/document-analyses.md

**Tests**: None — the repo has no test framework and the spec does not request tests (Constitution III). Validation is manual (quickstart.md) + `pnpm lint`/`pnpm format`.

**Organization**: Grouped by user story (priority order). MVP = US1 + US2.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare the shared pieces both the API and the merged client depend on.

- [X] T001 [P] Relocate `src/app/dashboard/document-analyses/PageImageViewer.tsx` to `src/app/dashboard/entries/PageImageViewer.tsx` (move file; no content change).
- [X] T002 Relocate `src/app/dashboard/document-analyses/DocumentAnalysisDetailDialog.tsx` to `src/app/dashboard/entries/DocumentAnalysisDetailDialog.tsx`; update its `PageImageViewer` import to `./PageImageViewer` and its `DocAnalysisRow` import to `./EntriesClient`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data plumbing that every user story relies on. MUST complete before US1–US3.

- [X] T003 Add optional `?period=` filter to `GET /api/document-analyses` in `src/app/api/document-analyses/route.ts`: import `accountabilityReports` from `@/db/fiscal.schema`, add `innerJoin(accountabilityReports, eq(entries.reportId, accountabilityReports.id))`, read `request.nextUrl.searchParams.get("period")` (change the handler signature to accept `request: NextRequest`), and when present add `.where(eq(accountabilityReports.period, period))`. Keep `orderBy(desc(analyzedAt))` and the existing response shape (per contracts/document-analyses.md).
- [X] T004 In `src/app/dashboard/entries/EntriesClient.tsx`, define and `export` the `DocAnalysisRow` interface (same shape currently in `DocumentAnalysesClient.tsx`) so the relocated dialog imports it from here.
- [X] T005 In `EntriesClient.tsx`, fetch period-scoped analyses alongside entries: on period change, `fetch(/api/document-analyses?period=<p>)`, store as state, and build a `useMemo` `analysisByEntry: Map<string, DocAnalysisRow>` keyed by `entryId` keeping the first (latest) per entry. Reset it on period change consistent with existing filter-reset behavior.

**Checkpoint**: Endpoint scopes by period; client holds a per-entry analysis map. No UI yet.

---

## Phase 3: User Story 1 — See document-match status alongside each entry (Priority: P1) 🎯 MVP

**Goal**: Each entry that has an analysed document shows inline amount/vendor/date match badges + a doc-type indicator; entries without one stay neutral; errors are distinguished.

**Independent Test**: Open a period with analysed docs; confirm badges appear only on entries with an analysis, neutral state otherwise, and error rows look distinct from match/mismatch.

- [X] T006 [US1] In `EntriesClient.tsx`, add a `MatchBadge` helper (port from `DocumentAnalysesClient.tsx`: `null → em-dash`, `true → OK`, `false → MISMATCH`) and a doc-type/error indicator.
- [X] T007 [US1] Add header columns and per-row cells to the virtualized entries table for: Doc type, Amount match, Vendor match, Date match. Render badges from `analysisByEntry.get(String(entry.id))`; when no analysis, render a neutral em-dash (NOT a mismatch). Use fixed-width columns to preserve the virtualized layout; adjust `estimateSize`/row height only if needed (FR-002, FR-003, SC-006).
- [X] T008 [US1] Mark entries whose analysis has a non-null `error` distinctly (e.g. an "error" doc-type label / muted destructive treatment) so they differ from both clean match and value mismatch (FR-004).

**Checkpoint**: US1 is independently demoable — status visible inline; no click-through yet.

---

## Phase 4: User Story 2 — Open the full document detail from an entry (Priority: P1) 🎯 MVP

**Goal**: Clicking an entry with an analysis opens the existing detail dialog; entries without an analysis are not clickable.

**Independent Test**: Click an analysed entry → dialog with fields + page images; click a plain entry → nothing; close → filters/scroll intact.

- [X] T009 [US2] In `EntriesClient.tsx`, import the relocated `DocumentAnalysisDetailDialog` and add `selectedAnalysis` state (`DocAnalysisRow | null`); render the dialog with `onOpenChange` clearing it (mirror the standalone page).
- [X] T010 [US2] Make a virtual row clickable only when an analysis exists for that entry: `onClick` sets `selectedAnalysis` to the mapped `DocAnalysisRow`; add `cursor-pointer` and a helpful `title` only for those rows. Rows without an analysis remain non-interactive (FR-005, FR-006).

**Checkpoint**: MVP complete — inline status + drill-down to existing detail with page images.

---

## Phase 5: User Story 3 — Find entries with document discrepancies for a period (Priority: P2)

**Goal**: Document-type and match-status filters + a period document-health summary, composing with existing filters and resetting on period change.

**Independent Test**: Apply "has discrepancy" and a doc-type filter; confirm the list reduces correctly and combines with search/category; switch period → filters reset and summary recounts.

- [X] T011 [US3] In `EntriesClient.tsx`, add `selectedDocTypes` and `selectedDocMatchStatus` state plus `MultiSelect` controls (import `@/components/ui/multi-select`) next to the existing sidebar filters; build `docTypeOptions` from `analysisByEntry` values; reset both on period change (FR-008, FR-009).
- [X] T012 [US3] Extend the `filtered` memo to AND the document filters with existing subcategory + search filters: an entry passes the doc-type filter if its analysis `documentType` is selected; it passes the match-status filter per `all_match` / `has_mismatch (incl. error)` semantics ported from `DocumentAnalysesClient.tsx` (FR-007, FR-009).
- [X] T013 [US3] Add a period document-health summary (counts of amount/vendor/date mismatches + errors over `analysisByEntry` values) to the Entries card header, alongside the existing revenue/expense/net badges (FR-010, SC-005).

**Checkpoint**: Auditor can isolate discrepancies for the period; summary matches the old page's counts for that period.

---

## Phase 6: User Story 4 — Reach the merged view from old links (Priority: P3)

**Goal**: Old route redirects; duplicate nav item removed.

**Independent Test**: Visit `/dashboard/document-analyses` → lands on `/dashboard/entries`; nav shows one entry point, no "Docs".

- [X] T014 [US4] Replace `src/app/dashboard/document-analyses/page.tsx` with a server component that calls `redirect("/dashboard/entries")` from `next/navigation` (FR-013).
- [X] T015 [P] [US4] Delete `src/app/dashboard/document-analyses/DocumentAnalysesClient.tsx` (now unused; type + dialog + viewer relocated).
- [X] T016 [US4] In `src/app/dashboard/layout.tsx`, remove the "Docs" `NavLink` to `/dashboard/document-analyses` and drop the now-unused `FileSearch` import (FR-014).

**Checkpoint**: Single entry point; old links preserved.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T017 Run `pnpm lint` and `pnpm format`; fix any issues (Constitution III). Confirm no `drizzle/` migration or schema files changed (read-only feature, FR-015).
- [X] T018 Build verification: `next build` succeeds — `/dashboard/entries` builds with the merged client+dialog and `/dashboard/document-analyses` collapses to a 196 B redirect. Interactive verification per `specs/013-merge-entries-docs/quickstart.md` (US1–US4, SC-005 count cross-check, SC-006 scroll smoothness) is deferred to human review on the PR (no headless data env).

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T005)** must complete before user-story phases.
- **US1 (T006–T008)** depends on Foundational. **US2 (T009–T010)** depends on US1 (uses the same map/rows) and the relocated dialog (T002).
- **US3 (T011–T013)** depends on Foundational + US1 (reuses `analysisByEntry`). **US4 (T014–T016)** depends only on T002/T004 (relocation done) and is otherwise independent of US1–US3.
- **Polish (T017–T018)** last.

## Parallel Opportunities

- T001 ∥ (independent file move) can start immediately.
- Within US4, T015 [P] (delete) is independent of T014/T016.
- US4 (T014–T016) can proceed in parallel with US3 once Setup/Foundational are done, since they touch different files.

## Implementation Strategy

- **MVP**: Phases 1–4 (Setup → Foundational → US1 → US2) — inline document status + drill-down, the core of the merge.
- **Increment 2**: Phase 5 (US3) — discrepancy filters + period summary.
- **Increment 3**: Phase 6 (US4) — redirect + nav cleanup.
- Ship each increment behind the same page; all are read-only over existing data.
