# Feature Specification: Shared alert type → label map

**Feature Branch**: `038-alert-type-labels`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "add a shared alert type→label map (src/lib/alerts.ts) with snake_case→Title Case fallback, used by the alerts list type filter, row badges, and detail page so no surface renders raw type values"

## Clarifications

### Session 2026-06-12

- No critical ambiguities detected worth formal clarification. Running unattended per the issue
  brief; all reasonable defaults are recorded in the Assumptions section (target module
  `src/lib/alerts.ts`, existing `alerts.tsx` helpers left in place, curated list seeded from
  pipeline source, generic Title-Case fallback for unknown types, no new list badge introduced).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Readable alert type filter (Priority: P1)

An auditor opens the Alerts page and uses the **Type** filter dropdown to narrow the list to a
specific kind of alert. Today the dropdown lists raw machine identifiers like
`attachment_amount_mismatch` and `document_overpayment`, which read inconsistently next to the
neighbouring Severity and Status filters (which already show human labels like "Critical" /
"Active"). The auditor should instead see friendly, human-readable type names (e.g. "Attachment
amount mismatch", "Document overpayment").

**Why this priority**: This is the exact surface the issue cites and the one most users touch.
Fixing it delivers the visible UX win on its own.

**Independent Test**: Open `/dashboard/alerts`, open the Type filter, and confirm every option
shows a human-readable label (no underscores, no all-lowercase machine identifier). Selecting an
option still filters the list correctly.

**Acceptance Scenarios**:

1. **Given** alerts of various types exist, **When** the auditor opens the Type filter, **Then**
   each option's label is human-readable (no raw `snake_case`) while filtering still works by the
   underlying type value.
2. **Given** an alert whose type is not in the curated map (a new pipeline type), **When** the
   Type filter is opened, **Then** that type's option is shown as a Title-Cased, space-separated
   label derived from its identifier rather than the raw value.

---

### User Story 2 - Readable type on the alert detail page (Priority: P2)

An auditor clicks an alert row to open its detail page, which shows a **Type** field. Today that
field renders the raw identifier (e.g. `document_overpayment`). It should show the same friendly
label the filter uses.

**Why this priority**: The detail page is the second place the raw value is exposed; sharing one
map keeps the filter and the detail page consistent.

**Independent Test**: Open any alert's detail page and confirm the Type field shows a
human-readable label matching the filter's label for that type.

**Acceptance Scenarios**:

1. **Given** an alert of a known type, **When** its detail page renders, **Then** the Type field
   shows the curated human-readable label.
2. **Given** an alert of an unknown type, **When** its detail page renders, **Then** the Type
   field shows the Title-Cased fallback label.

---

### User Story 3 - Readable type wherever a type is shown in the list (Priority: P3)

Wherever the alerts list surfaces an alert's type as a label/badge to the user, it shows the same
friendly label rather than the raw identifier, so the three surfaces (filter, list, detail) never
disagree and never expose a raw value.

**Why this priority**: Consistency across surfaces is the issue's stated goal ("the three surfaces
can't drift"); it is lower priority only because the current list rows display the alert *title*,
not the type, so this is a forward-looking guarantee rather than a visible bug.

**Independent Test**: Inspect every alerts UI surface that renders an alert's `type` and confirm it
routes through the shared label function; none renders the raw `type` string directly.

**Acceptance Scenarios**:

1. **Given** the shared label function, **When** any alerts UI surface needs to display a type,
   **Then** it calls the shared function rather than rendering the raw `type`.

---

### Edge Cases

- **Unknown / new type**: a type added by the pipeline but absent from the curated map MUST render
  as a Title-Cased, space-separated label (e.g. `some_new_check` → "Some new check"), never the raw
  value.
- **Empty / malformed type**: an empty string returns an empty label; a value that is not
  `snake_case` (e.g. already spaced, or single word) is still returned readably without throwing.
- **Acronyms in identifiers**: the fallback is a best-effort generic transform; curated entries
  exist precisely so known types (including any acronyms like CNPJ/NF) read correctly. The fallback
  is not expected to perfectly capitalize acronyms.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single shared function that maps an alert `type` identifier
  to a human-readable label, living in one module so all alert UI surfaces consume it.
- **FR-002**: The function MUST return a curated, human-readable label for every alert type the
  pipeline currently emits (see Key Entities / Assumptions for the enumerated list).
- **FR-003**: For any type NOT in the curated map, the function MUST return a generic
  `snake_case → Title Case` transform (underscores replaced with spaces, first word capitalized),
  never the raw identifier.
- **FR-004**: The alerts list **Type filter** MUST display the human-readable label for each option
  while still filtering by the underlying raw type value.
- **FR-005**: The alert **detail page** Type field MUST display the human-readable label.
- **FR-006**: Any alerts list surface that renders an alert's type to the user MUST use the shared
  function (no surface renders the raw `type`).
- **FR-007**: The function MUST be pure and total — it never throws for any string input (including
  empty string), so a malformed or unexpected type degrades gracefully to a readable label.

### Key Entities

- **Alert type**: a machine identifier (`snake_case` string) attached to each alert, produced by the
  analysis/scraper pipeline. Examples currently in use: `attachment_amount_mismatch`,
  `attachment_vendor_mismatch`, `attachment_date_mismatch`, `attachment_page_error`,
  `attachment_not_downloaded`, `document_overpayment`, `duplicate_billing`, `duplicate_entry`,
  `negative_credit`, `large_expense_no_attachment`, `unit_delinquency`, `subtotal_mismatch`,
  `balance_opening_mismatch`, `balance_month_mismatch`, `balance_accumulated_mismatch`,
  `entries_revenue_mismatch`, `entries_expenses_mismatch`, `portal_row_vanished`,
  `scrape_inconsistency`.
- **Type label**: the human-readable string shown to the user for a given alert type.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of alert types currently emitted by the pipeline render as a human-readable label
  (no underscores, not all-lowercase machine identifier) in the Type filter and on the detail page.
- **SC-002**: A newly added, uncurated alert type renders as a readable Title-Cased label on every
  surface with zero code changes to those surfaces.
- **SC-003**: Exactly one module defines the type→label mapping; the filter, the detail page, and
  any list type rendering all import from it (no duplicated label logic).
- **SC-004**: The label function never throws for any string input, verified by tests covering
  curated, unknown, empty, and non-snake_case inputs.

## Assumptions

- The shared module is `src/lib/alerts.ts` (named in the issue). The existing alert UI helpers in
  `src/app/dashboard/alerts/alerts.tsx` (entry links, evidence fields, severity/status badges) are
  **not** moved; only the new type-label concern lives in `src/lib/alerts.ts`. Co-locating the new
  function in the existing `alerts.tsx` was considered but rejected because the issue explicitly
  names `src/lib/alerts.ts` and `alerts.tsx` is a client-component-coupled `.tsx` module, whereas a
  pure string function belongs in a framework-agnostic `lib` file (testable without React).
- The current alerts list rows display the alert **title**, not the type, so FR-006 is satisfied
  today by routing the only type-rendering surfaces (filter options + detail field) through the
  shared function; no new type badge is added to the list rows (out of scope — the issue asks that
  surfaces that *do* render type use the map, not that a new badge be introduced).
- The curated label list is seeded from the alert types found in the pipeline source at
  implementation time; the generic fallback guarantees forward-compatibility for any not enumerated.
- No data, schema, or API change is involved — this is a presentation-only change to existing
  client components plus one new pure helper module and its unit test.
