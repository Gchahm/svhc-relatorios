# Tasks: Localize detail pages, dialogs, and notices to pt-BR (I18N-004)

**Feature**: `042-i18n-detail-surfaces` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Presentation-only i18n. All edits are in existing client components + the shared catalog. The
foundational phase (catalog keys) blocks every story because each surface reads keys from the catalog.

## Phase 1: Setup

- [ ] T001 Confirm branch `042-i18n-detail-surfaces` is checked out and the working tree has no broken
  build artifact committed (ignore/leave untracked `.next.broken.*`); confirm I18N-001 client
  entrypoints exist: `src/lib/i18n/client.tsx` (`useTranslation`/`useLocale`/`useAlertTypeLabel`) and
  `src/lib/i18n/formatters.client.ts`.

## Phase 2: Foundational (BLOCKS all user stories)

- [ ] T002 Add the `detail`, `analysis`, and `viewer` sections to the `CatalogShape` type in
  `src/lib/i18n/catalog.ts` (typed string slots per [data-model.md](./data-model.md)), placed in a
  sensible position among the existing sections.
- [ ] T003 Add the canonical **pt-BR** values for every new `detail.*`, `analysis.*`, `viewer.*` key
  in the `catalog["pt-BR"]` object of `src/lib/i18n/catalog.ts` (values from data-model.md).
- [ ] T004 Add the matching **en** values for every new key in the `catalog.en` object of
  `src/lib/i18n/catalog.ts` (keeps en a complete mirror so the type checks and the subset test pass).
- [ ] T005 Extend `src/lib/i18n/catalog.test.mjs`: add `"detail"`, `"analysis"`, `"viewer"` to the
  required-sections list, and add an `I18N-004` test asserting the new keys resolve to non-empty
  strings in both locales (mirror the existing I18N-003 test block).
- [ ] T006 Run `node --test src/lib/i18n/catalog.test.mjs` and confirm all catalog tests pass (so the
  keys are correct before any component reads them).

**Checkpoint**: catalog has all new keys, typed, mirrored in en, and tested.

## Phase 3: User Story 1 — Alert detail in pt-BR (P1)

**Goal**: Every chrome string in the alert detail page renders pt-BR; type via the localized label
map; per-file currency/date helpers removed.

**Independent test**: Open any alert detail; all chrome pt-BR, type label localized (never raw key),
currency `R$`, timestamp `dd/mm/aaaa hh:mm`, resolve/reopen writeback works.

- [ ] T007 [US1] In `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx`: delete the local
  `formatTimestamp` and `formatCurrency` helpers; import `formatCurrency` + `formatDateTime` from
  `@/lib/i18n/formatters.client` and call them with the active `useLocale()` value (timestamps →
  `formatDateTime`, falling back to the existing `—` when ms is null).
- [ ] T008 [US1] In the same file, replace the English `alertTypeLabel(alert.type)` (from
  `@/lib/alerts`) for the Type field with the localized `useAlertTypeLabel()` hook; remove the now
  unused `@/lib/alerts` import if nothing else uses it.
- [ ] T009 [US1] In the same file, replace every remaining inline English literal with `t("detail.…")`
  calls (back link, loading/not-found/error states, core field labels, Description/Notes headings,
  Resolution section + resolved message + reopen/resolve buttons incl. in-flight states + notes
  label/placeholder, Evidence heading + "view referenced document", Affected entries heading + empty
  state + per-entry field labels + "view attachment"/title/"no analysis"/Documents button, attached
  documents dialog title + empty state). Reuse existing keys where exact (`severity.*`/`alert_status.*`
  are already inside the shared badges; no change needed there).
- [ ] T010 [US1] Verify the affected-entries amount sign prefix (`+`/`-`) and the `—` null placeholders
  remain literal (locale-neutral), and that vendor/category/description/issuer/document-number values
  still render verbatim.

**Checkpoint**: alert detail fully pt-BR, behavior unchanged.

## Phase 4: User Story 2 — Document detail in pt-BR (P1)

**Goal**: Document detail page renders pt-BR chrome; local currency helper removed; values verbatim.

**Independent test**: Open a document detail; headings/labels/table headers/placeholders pt-BR;
currency locale-formatted; entry deep links navigate.

- [ ] T011 [US2] In `src/app/dashboard/documents/[id]/DocumentDetailClient.tsx`: make the component a
  client consumer of i18n — import `useTranslation` + `useLocale` from `@/lib/i18n/client` and
  `formatCurrency` from `@/lib/i18n/formatters.client`; delete the local `formatCurrency` helper and
  route all currency through the locale-aware one (preserve the `null → —` behavior).
- [ ] T012 [US2] In the same file, replace every inline English literal with `t("detail.…")`/reused
  keys: back link, loading/not-found/error states, header field labels (Issuer/CNPJ/Type/Total/Sum
  entries/Linked entries), the four section headings (Document image / Source attachments / Linked
  entries / Related documents) with their appended `(N)` counts kept as literal numerals, the
  "no image available"/"no image for this source" placeholders, the "this document"/"Unlabeled" page
  badges, the "From entry" label, the linked-entries + related-documents table column headers, the
  "Open"/"Abrir" link, and the two empty-state messages. Reuse `status.*` via the shared `StatusBadge`
  (already localized — no change). The `LabeledPage` alt text builds via the `viewer.*` templates (see
  T016) — pass localized alt strings.
- [ ] T013 [US2] Verify document number, issuer name, CNPJ, document type, vendor, and entry
  description still render verbatim, and the entry deep-link href is unchanged.

**Checkpoint**: document detail fully pt-BR, behavior unchanged.

## Phase 5: User Story 3 — Analysis dialog + page viewer in pt-BR (P2)

**Goal**: The attachment-analysis dialog and the page-image viewer render pt-BR chrome (shared by the
entries view and the alert detail), local currency helper removed, extracted values verbatim.

**Independent test**: Open the dialog from an entry with analysis; chrome pt-BR; match pills pt-BR;
images load or show the pt-BR unavailable placeholder; extracted values verbatim.

- [ ] T014 [US3] In `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx`: import
  `useTranslation` + `useLocale` (`@/lib/i18n/client`) and `formatCurrency`
  (`@/lib/i18n/formatters.client`); delete the local `formatCurrency`; route currency through the
  locale-aware one. Because `KNOWN_FIELDS`, `Field`, `RecordValues`, `MatchPill`, and
  `pageLabelDisplay` are module-scope (outside the component), refactor so the translation function is
  available where they render their labels — either move them inside the component, or pass `t` (and
  `locale`) as parameters. Keep the curated `KNOWN_FIELDS` *keys* (the extraction field keys) intact;
  only their human labels become catalog lookups (`analysis.field_*`).
- [ ] T015 [US3] In the same file, replace every inline English literal with catalog lookups: dialog
  title (`analysis.dialog_title`), processing-error prefix, the three section headings, Entry-source
  field labels, Roll-up field labels (incl. Entry amount / Document amount), the `MatchPill`
  label+verb (`analysis.match_ok`/`analysis.match_mismatch`, `—` stays literal), the
  "reconciled vs payment artifact" badge, the `Field` "not extracted" empty text, "No parsed values.",
  the parse-error prefix, the "No pages or per-page records" empty state, and `pageLabelDisplay`'s
  "page {n}" via `analysis.page_n` ({n}-substitution). Extra (uncurated) extracted keys keep the raw
  key as label (data, per A4); the `analysisType`/`artifactRole` raw values stay verbatim.
- [ ] T016 [US3] In `src/app/dashboard/entries/PageImageViewer.tsx`: import `useTranslation`
  (`@/lib/i18n/client`); localize the "Image unavailable" placeholder (`viewer.image_unavailable`) and
  the `aria-label` "Enlarge {alt}" via `viewer.enlarge` ({alt}-substitution). The `alt` prop value
  itself stays caller-supplied (callers now build it from `viewer.page_alt`/`viewer.page_alt_role`/
  `viewer.document_image_alt`); update the three call sites (AttachmentAnalysisDetailDialog,
  DocumentDetailClient `LabeledPage` + hero image) to build the `alt` from those templates so no raw
  English "Page …"/"… image" reaches the DOM.
- [ ] T017 [US3] Verify the dialog still loads records + pages independently (a page-list failure must
  not block extracted fields), the lightbox still opens, and extracted values (CNPJ, NF number, issuer,
  service description) render verbatim.

**Checkpoint**: dialog + viewer fully pt-BR (both call sites), behavior unchanged.

## Phase 6: User Story 4 — Deep-link not-found notice (P3, verification)

**Goal**: Confirm the feature-037 notice is pt-BR (already migrated in I18N-003).

**Independent test**: Navigate to a deep link for a missing entry; notice is pt-BR with id+period.

- [ ] T018 [US4] Inspect the deep-link notice block in
  `src/app/dashboard/entries/EntriesClient.tsx` (around the `deepLinkNotice` render): confirm it uses
  `t("notice.deeplink_invalid")` / `t("notice.deeplink_not_found_prefix")` / `_suffix` and that the
  interpolated short id + period render. If any residual English literal exists in this block, move it
  into the catalog and use `t(...)`; otherwise no code change (record "already localized").

## Phase 7: Polish & Cross-Cutting

- [ ] T019 Sweep the five in-scope files for any remaining hardcoded user-facing English literal
  (grep for capitalized English words in JSX text / `aria-label` / `title` / `placeholder`); ensure
  none remain (FR-007). The `—`, `·`, `+/-` signs, raw data values, and dev-only comments are exempt.
- [ ] T020 Run `node_modules/.bin/next lint` (or `pnpm lint`) and `node_modules/.bin/prettier --write`
  (or `pnpm format`) over the repo; fix any issues.
- [ ] T021 Run `node --test src/lib/i18n/catalog.test.mjs` again and confirm green.
- [ ] T022 Manual verification per [quickstart.md](./quickstart.md) using `ui-login` + the running app
  against local D1: alert detail, document detail, analysis dialog/viewer, deep-link notice; confirm
  resolution writeback + deep-link navigation unchanged. Record findings for the PR body.

## Dependencies & order

- Phase 1 (T001) → Phase 2 (T002–T006, sequential: type → pt-BR → en → test → run).
- Phase 2 blocks all of Phases 3–6 (every surface reads catalog keys).
- Phases 3, 4, 5 edit **different files** and are independent once Phase 2 is done — except T016
  touches DocumentDetailClient + AttachmentAnalysisDetailDialog call sites, so coordinate T012/T015
  with T016 (do T016's viewer change, then update both call sites). Phase 6 is verification-only.
- Phase 7 runs last.

## Parallel opportunities

- After Phase 2, US1 (AlertDetailClient) and US2 (DocumentDetailClient) touch disjoint files and could
  proceed in parallel. US3 shares the viewer alt-template wiring with US2's `LabeledPage`, so finalize
  the `viewer.*` templates (T016) before closing US2's T012.

## MVP

US1 + US2 (the two top-level detail pages) is the MVP; US3 deepens it; US4 is a regression guard.
