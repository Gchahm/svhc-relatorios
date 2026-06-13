# Feature Specification: Localize detail pages, dialogs, and notices to pt-BR (I18N-004)

**Feature Branch**: `042-i18n-detail-surfaces`
**Created**: 2026-06-12
**Status**: Draft
**Input**: GitHub issue #67 — "I18N-004: Localize detail pages, dialogs, and notices to pt-BR"

## Overview

This feature completes the localization track (I18N-001 foundation → I18N-002 auth/shell → I18N-003
dashboard lists → **I18N-004 detail surfaces**). The dashboard's *drill-down* surfaces still render
chrome (headings, field labels, badges, buttons, placeholders, dialog titles, image-viewer controls,
and accessibility text) in English. They must render Brazilian Portuguese (pt-BR) by default, using
the established I18N-001 catalog + locale-aware formatters, while leaving the underlying fiscal data
(vendor names, NF numbers, raw portal text, extracted document values) verbatim.

The surfaces in scope:

- **Alert detail** — `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx` (the resolution/notes UI,
  core fields, evidence, affected-entries cards, attached-documents dialog).
- **Document detail** — `src/app/dashboard/documents/[id]/DocumentDetailClient.tsx` (header, document
  image section, source-attachment galleries, linked-entries table, related-documents table).
- **Attachment-analysis dialog** — `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx`
  (per-page extraction records next to page images, field labels, match/mismatch pills).
- **Page-image viewer** — `src/app/dashboard/entries/PageImageViewer.tsx` (loading/error placeholder,
  zoom control, alt/aria text — including the alt strings the *callers* build).
- **Entries deep-link not-found notice** — feature 037 in `src/app/dashboard/entries/EntriesClient.tsx`
  (the non-blocking "entry could not be found" / "invalid link" notice with its interpolated
  entry-id + period message).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alert detail reads in pt-BR (Priority: P1)

A síndico (condo manager) opens an alert from the alerts list to investigate it. Every part of the
detail page — section headings ("Resolução", "Evidências", "Lançamentos afetados"), field labels
("Tipo", "Período", "Criado em"), the resolve/reopen buttons and their in-flight states, the notes
placeholder, the alert *type* (rendered through the localized label map), and the attached-documents
dialog — reads in Portuguese. The alert's own title/description and the fiscal data (vendor, amounts,
dates formatted as R$ and dd/mm/aaaa) stay accurate.

**Why this priority**: Alerts are the primary fraud/forgery surface; a manager investigating a finding
must not hit raw English or machine `snake_case` types. It exercises the catalog, the formatters, AND
the localized alert-type label map in one screen.

**Independent Test**: Log in, open any alert detail page; confirm all chrome is pt-BR, the type label
is human-readable Portuguese (never `snake_case`), currency is `R$ x.xxx,xx`, timestamps are
`dd/mm/aaaa hh:mm`, and resolving/reopening still writes back correctly.

**Acceptance Scenarios**:

1. **Given** a resolved alert, **When** the detail page renders, **Then** the resolution card shows a
   Portuguese "this alert is resolved" message and a Portuguese "Reabrir alerta" button.
2. **Given** an unresolved alert, **When** the user types notes and clicks resolve, **Then** the
   button label is Portuguese in both idle and in-flight ("Resolvendo…") states and the writeback
   succeeds unchanged.
3. **Given** an alert of type `document_overpayment`, **When** the Type field renders, **Then** it
   shows the Portuguese label from the catalog, never the raw key.

### User Story 2 - Document detail reads in pt-BR (Priority: P1)

A manager opens a fiscal document (NF) detail page. Header field labels ("Emitente", "CNPJ", "Tipo",
"Total", "Soma dos lançamentos", "Lançamentos vinculados"), the "Imagem do documento" /
"Anexos de origem" / "Lançamentos vinculados" / "Documentos relacionados" section headings, the
column headers of the linked-entries and related-documents tables, the "this document"/"Unlabeled"
page badges, the "No image available" placeholders, and the over/within/under status badge all read
in Portuguese; the document number, issuer name, CNPJ, and amounts render verbatim/locale-formatted.

**Why this priority**: Document detail is the second core drill-down and is currently entirely
un-localized (no i18n hooks at all). Equal-weight P1 with alert detail.

**Independent Test**: Open a document detail page; confirm all headings, labels, table headers, and
placeholders are pt-BR, currency is locale-formatted, and the deep links to entries still work.

**Acceptance Scenarios**:

1. **Given** a document with linked entries, **When** the page renders, **Then** the linked-entries
   table column headers and the "Abrir" link are Portuguese and the deep link still navigates.
2. **Given** a document with no image, **When** the image section renders, **Then** the placeholder
   reads a Portuguese "no image available" message.

### User Story 3 - Attachment-analysis dialog & page viewer read in pt-BR (Priority: P2)

From an entry (or from the alert detail), a manager opens the attachment-analysis dialog to compare
the ledger entry against the extracted document. The dialog title, the "Lançamento (origem)" /
"Consolidado (extraído)" / "Páginas" section headings, the extracted-field labels (Gross→"Bruto",
Net→"Líquido", Paid→"Pago", Issuer, "Nº do documento", etc.), the amount/vendor/date match pills
("OK"/"divergência"/"—"), the "amount reconciled vs payment artifact" badge, the page-viewer's
"Imagem indisponível" placeholder, zoom control, and the alt/aria texts all read in Portuguese.
Extracted values (CNPJ, NF number, issuer name, service description) stay verbatim.

**Why this priority**: This is the deepest drill-down and is shared between the entries view and the
alert detail, so localizing it fixes both call sites. Slightly lower priority than the two top-level
detail pages because it is one dialog level deeper.

**Independent Test**: Open the dialog from an entry with an analysis; confirm all chrome is pt-BR, the
match pills read Portuguese, and the page images still load (or show the Portuguese unavailable
placeholder on error).

**Acceptance Scenarios**:

1. **Given** an analysis whose amount matches, **When** the pill renders, **Then** it reads a
   Portuguese "OK"-style label, not English "mismatch".
2. **Given** a page image that fails to load, **When** the viewer renders, **Then** it shows the
   Portuguese "image unavailable" placeholder and a Portuguese enlarge aria-label.

### User Story 4 - Deep-link not-found notice reads in pt-BR (Priority: P3)

A manager follows a deep link to an entry that no longer exists (or an invalid link). The non-blocking
notice that explains this renders in Portuguese, including the interpolated short entry-id and period.

**Why this priority**: Lowest priority and lowest surface area — the notice was already moved to the
catalog in I18N-003; this story is a verification/regression guard, not new work.

**Independent Test**: Navigate to `/dashboard/entries?period=<p>&entry=<missing-id>`; confirm the
notice is Portuguese with the id/period interpolated.

**Acceptance Scenarios**:

1. **Given** a deep link to a missing entry, **When** the notice renders, **Then** it reads the
   Portuguese not-found message with the short id and period shown.

### Edge Cases

- **Unknown alert type**: a pipeline type not present in the catalog `alert.types.*` map must degrade
  to a readable humanized fallback (Title Case from snake_case), never a raw key — handled by the
  existing `useAlertTypeLabel()` hook.
- **Extra/unknown extracted fields**: the analysis dialog renders extra (non-curated) extracted keys
  using the raw key as the label — these are *data*, not chrome, so they remain verbatim (not
  translated). Curated KNOWN_FIELDS labels ARE translated.
- **Null/missing values**: the em-dash placeholder (`—`) for empty fields is locale-neutral and stays.
- **"not extracted" / "No parsed values" empty states**: these are chrome and ARE translated.
- **Locale fallback**: if a new key is somehow missing for the active locale, the I18N-001 lookup
  falls back to pt-BR (the canonical locale) and warns — it never renders a raw dotted key.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every user-facing chrome string in the five listed surfaces MUST resolve from the
  I18N-001 catalog (via `useTranslation()` for client components), not from inline English literals.
  This includes: section headings, field labels, match/mismatch/error badges, resolve/unresolve
  buttons (idle + in-flight), the notes placeholder + label, dialog titles, "back to …" links,
  loading/not-found/error states, table column headers, image-viewer controls, and accessibility
  (alt/aria) text.
- **FR-002**: Currency and date/timestamp rendering MUST use the I18N-001 locale-aware formatters
  (`formatCurrency`/`formatDate`/`formatDateTime` from `@/lib/i18n/formatters.client`, passing the
  active locale from `useLocale()`). The local helper copies in the in-scope files (e.g.
  `AlertDetailClient.tsx` `formatCurrency`/`formatTimestamp`, `DocumentDetailClient.tsx`
  `formatCurrency`, `AttachmentAnalysisDetailDialog.tsx` `formatCurrency`) MUST be removed.
- **FR-003**: Mismatch *kinds* and alert *types* MUST render through the localized label maps — the
  alert detail's Type field MUST use the localized alert-type label (the `useAlertTypeLabel()` hook /
  catalog `alert.types.*`), so machine keys (`document_overpayment`, `attachment_amount_mismatch`, …)
  never appear raw.
- **FR-004**: Underlying fiscal data MUST render verbatim — vendor names, issuer names, NF/document
  numbers, CNPJs, raw portal descriptions, and extracted document field *values* are never translated
  or transformed (only locale-formatted for currency/date where the value is numeric/temporal).
- **FR-005**: The catalog MUST gain all new keys these surfaces need, with both pt-BR (canonical) and
  en entries, and the catalog-completeness test MUST cover them (every pt-BR key has a typed slot).
- **FR-006**: Behavior MUST be unchanged — alert resolution writeback, deep-link navigation, image
  loading/lightbox, and all data fetching continue to work exactly as before; this is a
  presentation-only change.
- **FR-007**: After this feature, a repo-wide check SHOULD find no hardcoded user-facing English
  literal in the five in-scope files (best-effort sweep; the broader `src/app/`/`src/components/`
  sweep is the cumulative goal of the localization track, not re-audited here beyond the in-scope
  files and any shared helper they render through).

### Key Entities

- **Catalog** (`src/lib/i18n/catalog.ts`): the typed nested dictionary; this feature adds keys under
  new/existing sections (e.g. `detail.*` for shared detail-page chrome, `analysis.*` for the dialog,
  `viewer.*` for the page viewer, extending `match.*` / `table.*` / `meta.*` where a key already fits).
- **Localized label maps**: catalog `alert.types.*` + the `useAlertTypeLabel()` client hook (existing).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of chrome strings in the five in-scope surfaces render in pt-BR by default (zero
  raw English literals and zero raw `snake_case` keys visible to the user).
- **SC-002**: Currency renders as `R$ 1.234,56` and timestamps as `dd/mm/aaaa hh:mm` on every in-scope
  surface, with no per-file currency/date helper remaining.
- **SC-003**: Alert resolution writeback and entry deep links behave identically before and after
  (verified in the running app).
- **SC-004**: `pnpm lint`, `pnpm format --check`, and the i18n catalog-completeness test all pass.

## Assumptions

- **A1 (locale)**: pt-BR is the default and only fully-translated locale; `en` entries are added for
  catalog completeness/type-safety but the app renders pt-BR (consistent with I18N-001/002/003).
- **A2 (notice already done)**: the feature-037 deep-link not-found notice in `EntriesClient.tsx` was
  already migrated to the catalog (`notice.deeplink_*`) during I18N-003. This feature only *verifies*
  it (US4 is a regression guard) and does not re-implement it. If a residual literal is found in the
  notice block, it is brought into scope.
- **A3 (catalog key naming)**: new keys are grouped under intent-revealing sections; where an existing
  key already expresses the exact concept (e.g. `status.over`, `button.close`, `table.period`,
  `match.amount`), it is reused rather than duplicated.
- **A4 (extracted-field labels)**: the curated KNOWN_FIELDS labels in the analysis dialog (Gross/Net/
  Paid/Issuer/etc.) are chrome and ARE translated; the *extra* (uncurated) keys keep the raw key as
  their label because they are data, not chrome.
- **A5 (shared helpers already localized)**: `alerts.tsx` (SeverityBadge/StatusBadge/evidenceFields),
  `documents/StatusBadge.tsx`, and `@/lib/i18n` are already localized; this feature does not change
  them except to switch AlertDetailClient from the English-only `@/lib/alerts:alertTypeLabel` to the
  localized `useAlertTypeLabel()` for the Type field.
- **A6 (en fallback)**: the existing runtime fallback to pt-BR for any missing key is retained; no new
  fallback logic is added.

## Dependencies

- **#64 / I18N-001** (merged): the `@/lib/i18n` catalog, client hooks (`useTranslation`, `useLocale`,
  `useAlertTypeLabel`), and locale-aware formatters.
- **#66 / I18N-003** (merged): the shared label maps (`alert.types.*`) and the already-localized list
  pages + shared badge helpers + the deep-link notice catalog keys.
- Glossary from **#65** for term consistency.
