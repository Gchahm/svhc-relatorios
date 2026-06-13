# Tasks: TypeScript component/unit test harness for the dashboard

**Feature**: `045-ts-test-harness` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests ARE the deliverable here (this is the testing track). Each user story = one independently
shippable, independently testable slice. Zero new dependencies. Pure logic is extracted from
`.tsx` into sibling `.ts` modules (Node `node:test` cannot import `.tsx`).

## Phase 1: Setup

- [x] T001 Confirm the test runner + coverage flags work on this checkout: run
  `node --test --experimental-test-coverage --test-coverage-exclude='**/*.test.mjs' "src/**/*.test.mjs"`
  and note the current coverage of the tested module set (to seed the baseline in T020).

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Extract the shared auth decision into `src/lib/auth-access.ts`: export
  `ALLOWED_ROLES` (`["admin","member"]`), `UNAUTHORIZED_STATUS` (`403`), `SessionLike` type, and
  pure `isAuthorized(session): boolean`. No Cloudflare/better-auth import. (Blocks US5.)
- [x] T003 Refactor `src/app/api/alerts/route.ts`, `src/app/api/documents/route.ts`, and
  `src/app/api/attachment-analyses/route.ts` to import `ALLOWED_ROLES`/`UNAUTHORIZED_STATUS`/
  `isAuthorized` from `@/lib/auth-access` and gate with
  `if (!isAuthorized(session)) return NextResponse.json({ error: "Unauthorized" }, { status: UNAUTHORIZED_STATUS })`
  — behavior-preserving (still 403, still same roles).

## Phase 3: User Story 1 — single command + coverage (Priority: P1) 🎯 MVP

**Goal**: One command runs all TS tests; a second reports `src/` coverage and enforces a baseline;
both wired into CI.
**Independent test**: `pnpm test:ts` runs every `*.test.mjs` and exits nonzero on failure;
`pnpm test:ts:cov` prints a coverage report and exits nonzero below the baseline; CI invokes both.

- [x] T004 [US1] Extend `package.json` `test:ts` to keep running `node --test "src/**/*.test.mjs"`
  (already correct) and add `test:ts:cov` running
  `node --test --experimental-test-coverage --test-coverage-exclude='**/*.test.mjs' --test-coverage-lines=<B> --test-coverage-branches=<B> --test-coverage-functions=<B> "src/**/*.test.mjs"`
  (placeholders set in T020 once all tests land).
- [x] T005 [US1] Add a "TypeScript coverage" step to `.github/workflows/ci.yml` running
  `pnpm test:ts:cov`, placed after the existing "TypeScript tests" step.

## Phase 4: User Story 2 — alerts metadata + labels (Priority: P1)

**Goal**: Pin affected-entry derivation, deep-link URL shape, and localized type labels.
**Independent test**: feed representative metadata; assert affected ids, URL, and that every type
renders a no-underscore pt-BR catalog label.

- [x] T006 [US2] Create `src/app/dashboard/alerts/alerts-helpers.ts` by moving `affectedEntryIds`,
  `entryHref`, `referencedDocumentId` out of `src/app/dashboard/alerts/alerts.tsx` (verbatim).
- [x] T007 [US2] Edit `src/app/dashboard/alerts/alerts.tsx` to import (and re-export, to keep its
  public surface) those helpers from `./alerts-helpers` — no behavior change.
- [x] T008 [P] [US2] Add `src/app/dashboard/alerts/alerts-helpers.test.mjs` per
  contracts/alerts-helpers.md (single id, array, mixed-type array, malformed, null, URL encoding,
  document id).
- [x] T009 [US2] Extract the pure label logic from `useAlertTypeLabel` into
  `src/lib/i18n/alert-type-label.ts` as `alertTypeLabelFor(type, locale)`; refactor
  `src/lib/i18n/client.tsx`'s `useAlertTypeLabel` to call it (no behavior change).
- [x] T010 [P] [US2] Add `src/lib/i18n/alert-type-label.test.mjs`: assert every type in
  `catalog["pt-BR"].alert.types` maps to its pt-BR catalog value (read from catalog, not hardcoded);
  unknown type → no-underscore fallback; `""`→`""`; never throws.

## Phase 5: User Story 3 — document status badge label (Priority: P2)

**Goal**: Each `DocumentStatus` maps to its pt-BR catalog badge label; status math contract retained.
**Independent test**: for each status assert the catalog label key; existing `documents.test.mjs`
retained for the math.

- [x] T011 [US3] Create `src/lib/documents-label.ts` exporting
  `documentStatusLabelKey(status): DeepCatalogKey` (over→`status.over`, etc.).
- [x] T012 [US3] Edit `src/app/dashboard/documents/StatusBadge.tsx` to render its label via
  `t(documentStatusLabelKey(status))` (behavior-preserving — same visible label).
- [x] T013 [P] [US3] Add `src/lib/documents-label.test.mjs`: for each status assert
  `catalog["pt-BR"].status[<status>]` is the label the key resolves to (no English literal).

## Phase 6: User Story 4 — entries deep-link view-state (Priority: P2)

**Goal**: Pin the deep-link → view-state decision (present/absent/invalid/recovered), incl. the
localized not-found/invalid notice keys, for the highest-risk interactive flow.
**Independent test**: drive `deepLinkView` for present+analysis, absent, invalid, recovered, and
period-mismatch; assert highlight/dialog/notice/clearFilters/selectPeriod.

- [x] T014 [US4] Create `src/app/dashboard/entries/deeplinkView.ts` with `deepLinkView(input)`
  per contracts/entries-deeplink-viewstate.md, built on the existing `resolveDeepLink` (unchanged).
- [x] T015 [US4] Refactor `src/app/dashboard/entries/EntriesClient.tsx` to derive its deep-link
  view-state from `deepLinkView` (replace the inline outcome→action branching), keeping behavior
  identical (notice text still from `catalog.notice.*`, dialog auto-open unchanged).
- [x] T016 [P] [US4] Add `src/app/dashboard/entries/deeplinkView.test.mjs`: present+analysis →
  highlight+openDialog no notice; present no-analysis → highlight no dialog; absent →
  `noticeKey` not-found, no dialog; invalid → `noticeKey` invalid, no lookup; recovered →
  `clearFilters`; period mismatch → `selectPeriod`. Notice text asserted from `catalog["pt-BR"].notice.*`.

## Phase 7: User Story 5 — API auth + shaping (Priority: P2)

**Goal**: Pin the auth decision and the row→response shaping for the three routes without the
Cloudflare runtime.
**Independent test**: `isAuthorized` allow/deny matrix; shaping functions over representative rows.

- [x] T017 [P] [US5] Add `src/lib/auth-access.test.mjs` per contracts/auth-decision.md (deny:
  null/undefined/no-role/disallowed; allow: each role in `ALLOWED_ROLES`; `UNAUTHORIZED_STATUS===403`).
- [x] T018 [US5] Create shaping modules + wire routes to call them (behavior-preserving):
  `src/app/api/alerts/shape.ts` (`shapeAlertRow`), `src/app/api/documents/shape.ts`
  (`shapeDocumentRow` adding `status` via `documentStatus`), `src/app/api/attachment-analyses/shape.ts`
  (`attachmentAnalysesPeriodScoped` + `ATTACHMENT_ANALYSIS_RESPONSE_FIELDS`); edit the three
  `route.ts` to use them.
- [x] T019 [P] [US5] Add `src/app/api/alerts/shape.test.mjs`, `src/app/api/documents/shape.test.mjs`,
  `src/app/api/attachment-analyses/shape.test.mjs` per contracts/route-shaping.md (shape/key sets,
  documents `status` over/within/under/unknown, period-scope predicate).

## Phase 8: Polish & cross-cutting

- [x] T020 Run `pnpm test:ts` with `--experimental-test-coverage --test-coverage-exclude='**/*.test.mjs'`,
  read the final coverage of the tested module set, and set the `test:ts:cov` baseline thresholds
  in `package.json` (T004) to those measured values (the ratchet). Record the baseline in
  quickstart.md.
- [x] T021 Run `pnpm lint` and `pnpm format` (Constitution III gate); run `pnpm typecheck` to
  confirm the extractions type-check (no `any`); run `pnpm test:ts:cov` green.
- [x] T022 Sanity: introduce a temporary deliberate regression in one covered behavior, confirm a
  test fails (SC-003 — suite is not vacuous), then revert it.

## Dependencies & order

- Setup (T001) → Foundational (T002–T003) → US phases.
- US1 (T004–T005) depends on T001; its baseline (T020) is finalized in Polish after all tests land.
- US2/US3/US4/US5 are mutually independent once Foundational is done; the `[P]` test-writing tasks
  within each can run in parallel with other stories' tasks (different files).
- US5's auth test (T017) depends on T002; its shaping (T018–T019) is independent of T002.
- Polish (T020–T022) runs last (needs every test present to set the baseline).

## Parallel example

After T002–T003, these can proceed concurrently (distinct files):
`T006/T009 (US2)`, `T011 (US3)`, `T014 (US4)`, `T017/T018 (US5)`.

## MVP

US1 (single command + coverage wired into CI) is the minimum viable slice; US2 (alerts metadata +
labels, the core auditing-evidence routing) is the highest-value behavior to add first after it.
