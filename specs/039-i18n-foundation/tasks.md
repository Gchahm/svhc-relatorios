# Tasks: I18N-001 Localization Foundation

**Branch**: `039-i18n-foundation` | **Date**: 2026-06-12  
**Spec**: `specs/039-i18n-foundation/spec.md`  
**Plan**: `specs/039-i18n-foundation/plan.md`

## Summary

Implement a typed message catalog foundation with pt-BR as the default locale, centralized formatting helpers, and localized alert-type labels. Wire sign-in page and dashboard navigation as reference examples. No new dependencies; all TypeScript/React.

---

## Phase 1: Setup & Foundational Infrastructure

### Phase Goal
Create the i18n module structure and establish the message catalog framework that all user stories depend on.

### Tasks

- [ ] T001 Create i18n module directory structure (`src/lib/i18n/`) with index.ts, catalog.ts, server.ts, client.tsx, formatters.ts
- [ ] T002 Implement `src/lib/i18n/catalog.ts` with typed message dictionary (pt-BR canonical, en optional) including sections for nav, button, page, dialog, table, form, badge, alert.types, error, common
- [ ] T003 Implement `src/lib/i18n/server.ts` with `getLocale()` function for server-side locale resolution (returns "pt-BR" by default)
- [ ] T004 Implement `src/lib/i18n/client.tsx` with `LocaleProvider` component and `useTranslation()` hook for client-side locale resolution
- [ ] T005 Implement `src/lib/i18n/formatters.ts` with centralized helpers: `formatCurrency()`, `formatDate()`, `formatPercent()`, `formatNumber()` all deriving locale from i18n layer
- [ ] T006 Implement `src/lib/i18n/index.ts` exporting all public APIs: `t()` for server, types, catalog constants
- [ ] T007 Create `tests/i18n/catalog.test.mjs` with unit tests for catalog completeness (every pt-BR key is defined, no orphan en keys, all values non-empty)
- [ ] T008 Update `src/app/layout.tsx` to import `getLocale()` and set `<html lang>` attribute dynamically to active locale (default "pt-BR")
- [ ] T009 Wrap dashboard and app content with `LocaleProvider` in `src/app/layout.tsx` to seed React context for client components

---

## Phase 2: User Story 1 — Administrator Views Localized UI in pt-BR (P1)

### Story Goal
All UI text on the dashboard is rendered in Portuguese (pt-BR) with no hardcoded English strings. All numbers, dates, and currency are formatted per pt-BR conventions.

### Independent Test Criteria
- Navigate the dashboard and verify all text (headers, buttons, labels, dialogs, placeholders, badges) is in Portuguese
- Open browser DevTools and confirm `<html lang="pt-BR">`
- Verify all currency amounts display as `"R$ X.XXX,XX"`
- Verify all dates display as `"DD/MM/YYYY"`

### Tasks

- [ ] T010 [P] [US1] Replace hardcoded "Select period" with catalog key in Entries page (src/app/dashboard/entries/page.tsx or components)
- [ ] T011 [P] [US1] Replace hardcoded "Search description" and form placeholders with catalog keys in all form components
- [ ] T012 [P] [US1] Replace hardcoded page titles ("Entries", "Documents", "Alerts") with catalog keys in all dashboard pages
- [ ] T013 [P] [US1] Replace hardcoded button labels ("Submit", "Cancel", "Save", "Delete", "Search") with catalog keys across all components
- [ ] T014 [P] [US1] Replace hardcoded table column headers ("Period", "Date", "Amount", "Vendor", "Description", etc.) with catalog keys in all tables
- [ ] T015 [P] [US1] Replace hardcoded badge labels ("Pending", "Classified", "Analyzed", "Error") with catalog keys in attachment/alert badges
- [ ] T016 [P] [US1] Replace hardcoded error messages ("Not found", "Unauthorized", "Server error", "Network error") with catalog keys in error boundaries and modals
- [ ] T017 [P] [US1] Replace hardcoded "Loading..." and "No data" messages with catalog keys in loading/empty states
- [ ] T018 [US1] Verify all Entries page components use `t()` or `useTranslation()` and zero hardcoded English; manual smoke test in browser
- [ ] T019 [US1] Verify all Documents page components use `t()` or `useTranslation()` and zero hardcoded English; manual smoke test in browser
- [ ] T020 [US1] Verify all Alerts page components use `t()` or `useTranslation()` and zero hardcoded English; manual smoke test in browser

---

## Phase 3: User Story 2 — Developer Adds New UI Strings Using Typed Catalog (P1)

### Story Goal
A developer can add a new UI string by editing the catalog, importing the translation function, and TypeScript validates the key exists at build time. Missing keys cause type errors, preventing the build.

### Independent Test Criteria
- Add a new key to the catalog and verify a component using it builds successfully
- Try to reference a non-existent key and confirm TypeScript raises an error and build fails
- Run the catalog completeness test and verify it passes (all pt-BR keys are defined, no orphans)

### Tasks

- [ ] T021 [P] [US2] Add example keys to `src/lib/i18n/catalog.ts` for "new feature" section (myFeature.title, myFeature.description, myFeature.button_label) with both pt-BR and en translations
- [ ] T022 [US2] Create a test component (`src/components/i18n-example.tsx`) that demonstrates the correct pattern: server component using `t()`, client component using `useTranslation()`, and formatting helpers
- [ ] T023 [US2] Run `pnpm build` and confirm TypeScript catches a deliberately-misspelled catalog key and fails the build
- [ ] T024 [US2] Run `tests/i18n/catalog.test.mjs` (or `pnpm test`) and confirm the catalog completeness test passes
- [ ] T025 [US2] Create `specs/039-i18n-foundation/quickstart.md` documentation with code examples (already done in plan phase; verify in place and linked in PR)
- [ ] T026 [US2] Verify that TypeScript IntelliSense in VS Code suggests catalog keys when typing `t("` (type-ahead validation)

---

## Phase 4: User Story 3 — Alert Type Labels Render as Localized Text (P1)

### Story Goal
When an alert is displayed (e.g., type `"attachment_amount_mismatch"`), the label renders as a localized Portuguese phrase (e.g., `"Divergência de Valor"`) via the catalog, not the machine key.

### Independent Test Criteria
- Display an alert on the Alerts page and verify the type label is in Portuguese and matches the catalog
- Check that the label comes from the `getAlertTypeLabel()` function, not hardcoded
- Verify all ~40 alert types have Portuguese labels in the catalog
- Add a new alert type and confirm the label can be added to the catalog without code changes

### Tasks

- [ ] T027 Create a mapping in `src/lib/i18n/catalog.ts` of all alert type machine keys to Portuguese labels (e.g., `alert.types.attachment_amount_mismatch: "Divergência de Valor"`) for all alert types (review `src/lib/alerts.ts` for the full list)
- [ ] T028 Implement `src/lib/i18n/index.ts` export: `getAlertTypeLabel(type: AlertType): string` that looks up the localized label in the catalog and falls back to pt-BR if en lacks the key
- [ ] T029 [P] [US3] Update `src/lib/alerts.ts` to replace the static `ALERT_TYPE_LABELS` object with a getter/function that calls `getAlertTypeLabel()` from the i18n module
- [ ] T030 [P] [US3] Update all alert display components (e.g., `AlertBadge`, `AlertsClient`, alert detail dialogs) to use `getAlertTypeLabel()` for rendering the label instead of direct lookup
- [ ] T031 [US3] Add all ~40 alert type translations to the catalog (enumerate from current `ALERT_TYPE_LABELS` or database if alert types are defined elsewhere)
- [ ] T032 [US3] Manual test: Open Alerts page, verify all displayed alert type labels are in Portuguese and match the catalog entries; verify new alert types would inherit catalog labels

---

## Phase 5: User Story 4 — Reference Surface Fully Localized (P2)

### Story Goal
The sign-in page and dashboard navigation are fully localized as reference examples. All text, labels, buttons, and error messages are in Portuguese and come from the catalog.

### Independent Test Criteria
- Sign-in page loads and all text is in Portuguese
- All form labels, placeholders, buttons, and error messages are localized
- Dashboard navbar loads and all navigation labels are in Portuguese
- Code review shows clear, idiomatic patterns for server and client components using the i18n API
- New developers can reference these pages as examples when adding localized text elsewhere

### Tasks

- [ ] T033 [US4] Update `src/app/(auth)/sign-in/page.tsx` to replace hardcoded English text with catalog keys (form labels, placeholders, button labels, error messages, page title)
- [ ] T034 [US4] Verify sign-in page uses `t()` for server-rendered text and `useTranslation()` for client-side interactive elements (if any)
- [ ] T035 [US4] Add all sign-in page strings to the catalog under an appropriate section (e.g., `auth.signIn.*`)
- [ ] T036 [P] [US4] Update `src/app/dashboard/layout.tsx` (nav bar) to replace hardcoded navigation labels ("Entries", "Documents", "Alerts", etc.) with catalog keys
- [ ] T037 [P] [US4] Update nav component to use `t()` for all navigation labels, menu items, and breadcrumbs
- [ ] T038 [US4] Add all navigation strings to the catalog under `nav.*` section
- [ ] T039 [US4] Verify sign-in page renders correctly with all Portuguese text; manual browser test
- [ ] T040 [US4] Verify dashboard navbar renders correctly with all Portuguese navigation labels; manual browser test
- [ ] T041 [US4] Create a code review checklist in PR description: "Sign-in and nav are reference examples for i18n usage; future features should follow these patterns"

---

## Phase 6: Polish & Cross-Cutting Concerns

### Tasks

- [ ] T042 Run `pnpm format` to format all new files (catalog, server, client, formatters, tests, updated components)
- [ ] T043 Run `pnpm lint` to verify no ESLint violations in new code and refactored components
- [ ] T044 Run `pnpm build` and confirm the Next.js build succeeds with no errors or warnings
- [ ] T045 Run `pnpm test` (or `node tests/i18n/catalog.test.mjs` directly) and confirm all i18n unit tests pass
- [ ] T046 Add i18n module documentation to CLAUDE.md under "Key Patterns" section (optional but helpful): brief explanation of how to use `t()` and `useTranslation()`
- [ ] T047 Verify Git status shows all new/modified files and commit them with a message like "feat(I18N-001): localization foundation — typed catalog, server/client locale resolution, centralized formatters, reference surfaces"
- [ ] T048 Push the branch and open a PR with the feature description, spec link, and the success criteria checklist from the spec

---

## Dependencies & Execution Order

### Critical Path (Must Complete in Order)

1. **Phase 1** (Setup & Infrastructure): All foundational tasks must complete before any story work begins
   - T001–T009: Create i18n module, catalog, locale resolution, formatters, unit test, update layout
   - **Blocker**: Phase 1 complete = foundation ready for all user stories

2. **Phase 2** (US1 — Localized UI): High-priority; makes the app visible in Portuguese
   - T010–T020: Replace hardcoded strings, verify no English visible
   - **Dependency**: Phase 1 complete
   - **Parallel**: T010–T017 can run in parallel (different components/pages)

3. **Phase 3** (US2 — Typed Catalog): Medium-priority; ensures future strings are type-safe
   - T021–T026: Add example keys, test TypeScript validation, run completeness test
   - **Dependency**: Phase 1 complete
   - **Parallel**: Some can run in parallel with Phase 2 if Phase 1 is done

4. **Phase 4** (US3 — Alert Labels): High-priority; critical user-facing feature
   - T027–T032: Map all alert types, implement `getAlertTypeLabel()`, update alert components
   - **Dependency**: Phase 1 complete, Phase 2 preferably near completion
   - **Parallel**: T029–T030 can run in parallel (different components)

5. **Phase 5** (US4 — Reference Surfaces): Medium-priority; serves as pattern documentation
   - T033–T041: Localize sign-in and nav, verify rendering
   - **Dependency**: Phase 1 complete, Phases 2–4 preferably done
   - **Parallel**: T033–T035 (sign-in) and T036–T038 (nav) can run in parallel

6. **Phase 6** (Polish & Testing): Must complete last before PR
   - T042–T048: Format, lint, build, test, document, commit, push PR
   - **Dependency**: All previous phases complete

### Parallelization Opportunities

**Within Phase 2 (US1 — Localized UI)**:
- T010–T017 are all parallelizable (different pages/components, no interdependencies):
  - Task T010: Entries page
  - Task T011: Form components
  - Task T012: Page titles (can hit multiple pages in parallel)
  - Task T013: Buttons (across all components in parallel)
  - Task T014: Table headers (across all tables in parallel)
  - Task T015: Badges (independent components)
  - Task T016: Error messages (independent)
  - Task T017: Loading states (independent)

**Within Phase 4 (US3 — Alert Labels)**:
- T029–T030 are parallelizable:
  - T029: Update `alerts.ts` (global)
  - T030: Update alert display components (parallel to T029)

**Within Phase 5 (US4 — Reference Surfaces)**:
- T033–T035 (sign-in) and T036–T038 (nav) can run in parallel (independent pages)

### Sequential Blockers

- **T001–T009 MUST complete before any other phase** (establishes the foundation)
- **Catalog completeness test (T007) must pass before merging** (quality gate)
- **TypeScript build (T044) must succeed before merging** (quality gate)

---

## Implementation Strategy

### MVP Scope (for fastest delivery)

**Minimum Viable Product** focuses on **User Story 1 (US1)** only:
- Phase 1: Complete all setup tasks (T001–T009)
- Phase 2: Complete US1 tasks (T010–T020)
- Phase 6: Polish (T042–T048)

This delivers the core value: **users see Portuguese UI with no English strings**. Alert labels and reference surfaces can follow in a subsequent PR if time is constrained.

### Full Feature Scope (all stories)

**Complete MVP + Stories 2, 3, 4**:
- Phase 1: Setup (T001–T009) — ~4 hours
- Phase 2: US1 (T010–T020) — ~3 hours (parallelizable)
- Phase 3: US2 (T021–T026) — ~2 hours
- Phase 4: US3 (T027–T032) — ~2 hours (parallelizable)
- Phase 5: US4 (T033–T041) — ~2 hours (parallelizable with Phase 4)
- Phase 6: Polish (T042–T048) — ~1 hour

**Estimated total**: ~14 hours for full feature.

### Suggested Execution Plan

1. **Single developer** → Complete sequentially (Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6)
2. **Two developers** → Parallelization opportunities:
   - Dev A: Phase 1 (setup) → Phase 2 (US1, parallelizable tasks) → Phase 4 (US3, parallelizable tasks)
   - Dev B: (waits for Phase 1) → Phase 3 (US2) and Phase 5 (US4) in parallel with Dev A's Phase 2/4
   - Both: Phase 6 (final polish and testing)

---

## Quality Gates

Before merging the PR:

1. ✅ **Catalog completeness test passes** (`pnpm test`)
2. ✅ **TypeScript build succeeds** (`pnpm build`)
3. ✅ **Linting passes** (`pnpm lint`)
4. ✅ **Formatting passes** (`pnpm format`)
5. ✅ **Manual browser testing**: All dashboard text is in Portuguese, no hardcoded English visible
6. ✅ **All tasks marked [x] (completed)**
7. ✅ **PR includes reference to issue #64** (`Closes #64`)

---

## Acceptance Criteria (from Spec)

This task list delivers:

- ✅ **SC-001**: All user-facing text on dashboard is in Portuguese with no English visible
- ✅ **SC-002**: TypeScript build fails if catalog key is missing or referenced incorrectly
- ✅ **SC-003**: All alert type labels are localized via catalog (100% of alert types have pt-BR labels)
- ✅ **SC-004**: Sign-in and nav are fully localized reference examples
- ✅ **SC-005**: Unit test suite verifies catalog completeness; runs in CI
- ✅ **SC-006**: Currency, date, number formatting is centralized in one module and derives locale from i18n layer
- ✅ **SC-007**: `<html lang>` attribute reflects active locale (default pt-BR) on page load
