# Feature Specification: Correct `Entry.id` client type to UUID string

**Feature Branch**: `031-entry-id-string-type`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "fix EntriesClient Entry.id type to UUID string"

## Context

GitHub issue #44 (IMP-007). The entries ledger client (`EntriesClient`) declares its row
identifier as a numeric type, but the persisted ledger identifier is a text UUID and every
data source (the database mirror and the entries API) delivers it as a string. The client
only works today because every use of the identifier is defensively coerced to a string at
the call site. The type therefore "lies": it permits a future change that treats the
identifier as a number — arithmetic, a numeric object key, or a strict comparison against a
string without the coercion — to type-check while failing silently at runtime. The
identifier is used to match deep-linked rows (from an alert) and to look up a row's
attachment analysis, so this is exactly the code path most exposed to such a bug.

## Clarifications

### Session 2026-06-12

- No critical ambiguities detected worth formal clarification. This is a tightly-scoped,
  mechanical type-correctness refactor; all taxonomy categories (functional scope, data
  model, interaction/UX, edge cases, constraints, terminology, completion signals) are Clear
  or already resolved in the Assumptions section. Running unattended, the open decision —
  whether to also extract shared row types into a dedicated module — was resolved as
  in-scope per A-003 (directly serves FR-006), with an explicit fallback to drop it if it
  introduces risk.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Deep link from an alert opens the correct entry (Priority: P1)

A reviewer follows a deep link from an alert (`?period=<YYYY-MM>&entry=<entryId>`) into the
entries ledger. The targeted row is scrolled into view, highlighted, and its attachment
analysis dialog opens automatically.

**Why this priority**: This is the identifier's primary cross-feature use and the path most
exposed to a silent type mismatch. It must keep working byte-for-byte after the type is
corrected.

**Independent Test**: Open the entries page via an alert deep link to a known entry and
confirm the correct row highlights and its detail dialog opens.

**Acceptance Scenarios**:

1. **Given** an alert linking to a known entry in a period, **When** the reviewer follows
   the deep link, **Then** that entry's row is highlighted and its attachment analysis
   dialog opens.
2. **Given** the entries page loaded normally (no deep link), **When** the reviewer clicks a
   row that has an attachment analysis, **Then** that row's analysis dialog opens.

### User Story 2 - Document-type / match-status filters still apply per row (Priority: P2)

A reviewer filters the ledger by document type or match status. Rows are kept or hidden
based on the attachment analysis associated with each entry by identifier.

**Why this priority**: The per-row analysis lookup uses the same identifier; a broken lookup
would silently drop or keep the wrong rows.

**Independent Test**: Apply a document-type filter on a period that has analyses and confirm
only rows whose analysis matches remain visible.

**Acceptance Scenarios**:

1. **Given** a period with attachment analyses, **When** the reviewer selects a document-type
   filter, **Then** only entries whose associated analysis has that document type remain.

### Edge Cases

- An entry that has **no** associated attachment analysis: its analysis lookup returns
  nothing and no dialog is opened — unchanged behavior.
- A deep-link entry id that does not exist in the loaded period: no row is highlighted and no
  dialog opens — unchanged behavior.
- A React list `key` derived from the identifier must remain a stable, unique string.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The client row entity's identifier MUST be typed as the text identifier it
  actually is (a string), matching the database mirror and the entries API payload.
- **FR-002**: Identifier comparisons, map keys, list keys, and lookups MUST operate directly
  on the string identifier without redundant string coercion at the call site.
- **FR-003**: The deep-link matching behavior (find the targeted entry, highlight it, open
  its analysis dialog) MUST be unchanged at runtime.
- **FR-004**: The per-entry attachment-analysis lookup used by row rendering and by the
  document-type / match-status filters MUST be unchanged at runtime.
- **FR-005**: No change to any data source — the database schema, migrations, the entries
  API contract, and the attachment-analyses API contract are untouched.
- **FR-006**: Shared row types consumed by more than one feature client MUST remain importable
  by their existing consumers without breaking those consumers' behavior.

### Key Entities

- **Entry (client row)**: One ledger line as rendered by the entries client. Its identifier
  is a text UUID string; other fields (date, description, amount, movement type, period,
  category, subcategory, vendor, unit) are unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The entries page loads and renders rows for a selected period with no console
  errors.
- **SC-002**: Following an alert deep link highlights the correct entry and opens its analysis
  dialog (100% of valid deep links resolve to the intended row).
- **SC-003**: Document-type and match-status filters keep exactly the same set of rows as
  before the change for the same data.
- **SC-004**: The project's type-check, lint, and format checks all pass with zero new
  warnings or errors.
- **SC-005**: Zero runtime string-coercion wrappers remain at identifier call sites in the
  entries client.

## Assumptions

- **A-001**: Scope is type-correctness only — no behavior, data, or API change. This is a
  mechanical refactor.
- **A-002**: The entries API and the database mirror deliver the entry id as a string today;
  no defensive coercion at the call sites is required once the type is corrected, so all such
  wrappers at identifier call sites are removed.
- **A-003**: The issue's secondary suggestion — extracting the shared row types (`Entry`,
  `AttachmentAnalysisRow`) into a shared `types.ts` so feature clients no longer import each
  other's component modules for types — is **in scope** as a low-risk follow-on, because it
  directly serves FR-006 and removes a cross-feature component-for-types import that the issue
  explicitly flags. It is a pure move of type declarations with import-path updates and no
  behavior change. If it proves to introduce risk during implementation it will be dropped and
  noted, leaving FR-001–FR-005 as the irreducible fix.
- **A-004**: No new runtime tests are added for a type-only change; verification is the
  existing build/type-check/lint plus a manual UI check of the entries page and deep links.
