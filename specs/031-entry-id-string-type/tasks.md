# Tasks: Correct `Entry.id` client type to UUID string

**Feature**: 031-entry-id-string-type
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are NOT generated — no test framework is configured (constitution Principle III; A-004).
Verification is `pnpm lint` + type-check (build) + manual UI check via the `verify` skill.

## Phase 1: Setup

- [X] T001 Confirm clean working tree on branch `031-entry-id-string-type` and that the entries client builds before changes (`pnpm lint`).

## Phase 2: Foundational (shared types extraction — blocks both user stories)

- [X] T002 Create `src/app/dashboard/entries/types.ts` exporting the `Entry` interface (with `id: string`) and the `AttachmentAnalysisRow` interface, copied verbatim from `src/app/dashboard/entries/EntriesClient.tsx` except `Entry.id` is `string` not `number`.
- [X] T003 In `src/app/dashboard/entries/EntriesClient.tsx`, remove the inline `Entry` and `AttachmentAnalysisRow` declarations and `import type { Entry, AttachmentAnalysisRow } from "./types";` instead.
- [X] T004 [P] In `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx`, change the `AttachmentAnalysisRow` import to `import type { AttachmentAnalysisRow } from "./types";`.
- [X] T005 [P] In `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx`, change the `AttachmentAnalysisRow` import from `"../../entries/EntriesClient"` to `import type { AttachmentAnalysisRow } from "../../entries/types";`.

## Phase 3: User Story 1 — Deep link opens the correct entry (P1)

**Goal**: Deep-link match + row highlight + analysis dialog work with `id: string` and no coercion.
**Independent test**: Follow an alert deep link to a known entry → that row highlights and its dialog opens.

- [X] T006 [US1] In `src/app/dashboard/entries/EntriesClient.tsx`, replace `analysisByEntry.get(String(e.id))` (in the `filtered` memo) with `analysisByEntry.get(e.id)`.
- [X] T007 [US1] In `src/app/dashboard/entries/EntriesClient.tsx`, replace `filtered.findIndex(e => String(e.id) === deepLinkEntry)` with `filtered.findIndex(e => e.id === deepLinkEntry)`.
- [X] T008 [US1] In `src/app/dashboard/entries/EntriesClient.tsx`, in the row render, replace `analysisByEntry.get(String(entry.id))` with `analysisByEntry.get(entry.id)` and `highlightedEntryId === String(entry.id)` with `highlightedEntryId === entry.id`; confirm `key={entry.id}` is already a string (no change needed).

## Phase 4: User Story 2 — Doc-type / match-status filters per row (P2)

**Goal**: The per-row analysis lookup driving the filters works on the string id.
**Independent test**: Apply a doc-type filter on a period with analyses → only matching rows remain.

- [X] T009 [US2] Verify (covered by T006) that the doc-type / match-status filter branch reads the analysis via `analysisByEntry.get(e.id)`; no separate edit if T006 already removed the wrapper. Add no new coercion.

## Phase 5: Polish & Verification

- [X] T010 Grep the repo for any remaining `String(...id)` coercion at entry-id call sites and for stale imports of types from `EntriesClient` (`rg "String\((e|entry)\.id\)" src; rg "from \"\\./EntriesClient\"|entries/EntriesClient\"" src`) — expect zero matches except the `page.tsx` default-component import of `EntriesClient` itself.
- [X] T011 Run `pnpm lint` and `pnpm format` (or `node_modules/.bin/prettier --write` per the sandbox workaround) — must pass clean.
- [X] T012 Type-check via build (`node_modules/.bin/next build` or `pnpm build`) — must compile with no new TS errors.
- [X] T013 Verify in the running app (the `verify` / `ui-login` skill): entries page loads, a doc-type filter narrows rows, and an alert deep link highlights the right row and opens its analysis dialog. Record the result for the PR body.

## Dependencies

- Phase 2 (shared types) blocks Phases 3–4 (the clients import the new module).
- T002 → T003 (EntriesClient must import once types.ts exists); T004, T005 are `[P]` (independent files).
- T006 → T009 (US2 reuses the US1 lookup edit).
- Phase 5 runs last.

## MVP

User Story 1 (deep link) is the MVP: it exercises the id comparison, the map lookup, and the
highlight — the entire risk surface of the type lie. US2 is the same lookup applied to filters.
