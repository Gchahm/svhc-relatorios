# Feature Specification: Preserve Raw Portal Values on Mirror Rows

**Feature Branch**: `030-preserve-raw-portal-values`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "preserve raw portal values on mirror rows (raw provenance for amounts/text) and harden parse_brl to fail the row not the period"

## Overview

The fiscal-auditing tool exists to prove "this is exactly what the brcondos portal said". Today the
mirror tables store only *derived* values: monetary amounts are parsed into floats (the raw portal
string `"1.234,56"` is discarded), and text fields (descriptions) are whitespace-normalized before
storage. When a dispute arises over a value, the original portal text can no longer be recovered
from the database alone — the evidence chain has a gap. Additionally, the currency parser has no
error handling: a single malformed cell raises and aborts the entire period's scrape attempt.

This feature preserves the **raw portal cell text** alongside the derived value on the mirror ledger
rows (scraper-owned columns), and hardens the currency parser so a single bad cell fails **that row**
with a visible, recorded warning instead of taking down the whole period.

## Clarifications

### Session 2026-06-12 (unattended)

Ran in one-shot mode; resolved by informed assumption rather than user prompt (recorded in
**Assumptions**). Key decisions:

- **Provenance representation**: two discrete nullable TEXT columns on `entries`
  (`raw_amount`, `raw_description`), not a single JSON `raw_row` blob — queryable, Drizzle-mappable.
- **Amount type**: keep `amount` REAL; integer-centavos migration (issue suggestion #1) deferred to a
  follow-up. Raw text alone satisfies the audit-trail (round-trip provability) goal.
- **`scrape_run_id` on mirror rows** (issue suggestion #4): out of scope for this feature.
- **Parse-failure policy**: skip the offending row (no sentinel), warn quoting the raw text, and record
  a non-fatal note on the run (IMP-002 convention) — do not abort the period, do not flip status to
  `error` solely for a parse skip.

No outstanding ambiguities block planning.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Settle a disputed amount from the database alone (Priority: P1)

An auditor reviewing a condominium ledger entry questions a stored amount. They need to confirm what
the portal literally displayed for that cell — the exact characters, including any currency symbol,
thousands separators, and decimal comma — without re-opening the portal (which may have since changed
or become unavailable).

**Why this priority**: This is the core audit-trail-fidelity value of the feature. Without it the
"exactly what the portal said" guarantee is unprovable from D1.

**Independent Test**: Scrape a period; inspect any entry row in D1 and confirm it carries both the
parsed numeric amount and the verbatim original portal cell text for that amount.

**Acceptance Scenarios**:

1. **Given** a portal amount cell displaying `"R$ 1.234,56"`, **When** the period is scraped, **Then**
   the entry row stores the parsed amount `1234.56` AND the verbatim raw text `"R$ 1.234,56"`.
2. **Given** a portal description cell with irregular internal spacing, **When** the period is
   scraped, **Then** the entry row stores the normalized description used for matching/ids AND the
   verbatim original (pre-normalization) description text.
3. **Given** a previously scraped period whose entries lack raw provenance, **When** that period is
   re-scraped, **Then** the entry rows are populated with the raw provenance values (no manual
   backfill required).

---

### User Story 2 - One malformed cell does not abort the whole period (Priority: P1)

An operator runs a scrape. One amount cell on the portal is malformed (unexpected characters, empty,
or otherwise unparseable). The operator wants the scrape of that period to continue and produce a
result, with the bad row clearly flagged, rather than the whole period failing.

**Why this priority**: Robustness of the scrape pipeline. A single corrupt cell currently aborts the
period (no try/except around the parser), wasting all the work already done for that period and
masking which cell was at fault.

**Independent Test**: Feed the parser a malformed currency string and confirm it does not raise an
unhandled exception that aborts the run; confirm a visible warning identifying the offending raw text
is emitted and the row is handled per the failure policy.

**Acceptance Scenarios**:

1. **Given** a row whose amount cell is unparseable, **When** the period is scraped, **Then** the
   parser logs a warning quoting the offending raw text and the period scrape continues to completion
   for the remaining rows.
2. **Given** a parser result that is `NaN` or infinite, **When** parsing runs, **Then** it is rejected
   as invalid (treated the same as unparseable), not silently stored.
3. **Given** at least one row failed to parse during a period scrape, **When** the run completes,
   **Then** the failure is surfaced in the run record (so it is queryable later) without flipping an
   otherwise-successful period to a hard `error` status.

---

### Edge Cases

- **Empty / whitespace-only amount cell**: treated as unparseable → row-level failure policy applies
  (warning + row skipped), not a silent `0`.
- **Negative or parenthesized amounts**: the raw text is preserved verbatim regardless of how the
  numeric parse handles sign; reconciliation continues to use the existing movement-type semantics.
- **Description that is already clean** (no normalization change): raw description still stored
  verbatim (it equals the normalized value — preserved for a uniform, complete audit trail).
- **Re-scrape after the columns exist but a cell is now unparseable**: the row is skipped per the
  failure policy; the mirror reconciliation (feature 028) still applies to the rows that were produced
  (a skipped row is simply absent from the fresh set).
- **Existing rows scraped before this feature**: raw provenance columns are nullable; old rows read
  back as `NULL` until that period is re-scraped. No analysis or UI path may assume non-null.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The scraper MUST store, on each ledger entry mirror row, the **verbatim original portal
  cell text** for the entry's monetary amount (the string before any parsing/cleaning), alongside the
  existing parsed numeric amount.
- **FR-002**: The scraper MUST store, on each ledger entry mirror row, the **verbatim original
  description text** (the string before whitespace normalization and before any fornecedor-prefix
  stripping), alongside the existing normalized/derived description.
- **FR-003**: The raw-provenance columns MUST be **scraper-owned** mirror columns: only the scraper
  writes them, and the analysis pipeline MUST NOT write them (mirror-table invariant, feature 026).
- **FR-004**: The currency parser MUST validate its result and **reject** `NaN`, infinite, and
  otherwise-unparseable inputs rather than returning a bogus number or raising an unhandled exception
  that aborts the period.
- **FR-005**: On an unparseable amount cell, the scraper MUST emit a **visible warning that quotes the
  offending raw text** and MUST fail only **that row** (skip it), allowing the rest of the period to be
  scraped to completion.
- **FR-006**: When one or more rows fail to parse during a period scrape, the run MUST record that fact
  in a **queryable** location (the scrape run's error/notes channel) WITHOUT, on its own, flipping an
  otherwise-successful period to a hard `error` status (consistent with the IMP-002 non-fatal-notes
  convention).
- **FR-007**: The raw-provenance columns MUST be **nullable** and existing rows (scraped before this
  feature) MUST remain readable; no analysis, reconciliation, or UI code path may assume the raw
  columns are non-null.
- **FR-008**: Re-scraping a period MUST populate the raw-provenance columns for that period's rows, and
  MUST preserve the feature-027 / feature-028 scrape semantics (linkage-column preservation and
  authoritative reconciliation) unchanged.
- **FR-009**: The derived values currently used downstream (parsed `amount`, normalized `description`,
  deterministic ids) MUST remain unchanged in value and meaning; adding raw provenance MUST NOT alter
  id derivation, reconciliation tolerance math, or any existing alert.

### Key Entities *(include if feature involves data)*

- **Entry (ledger row / `lancamento`)**: a mirror of one portal ledger line. Gains two scraper-owned,
  nullable provenance attributes: the raw amount cell text and the raw (pre-normalized) description
  text. Its derived `amount` and `description` are unchanged.
- **Scrape run**: the run record that already carries an errors/notes channel; row-level parse failures
  are recorded there as non-fatal notes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After scraping any period, **100%** of that period's entry rows carry a non-null raw
  amount text and a non-null raw description text equal to what the portal displayed.
- **SC-002**: A single malformed amount cell in a period causes **0** period-level aborts attributable
  to currency parsing — the period still completes and stores its parseable rows.
- **SC-003**: For every successfully stored entry, the parsed amount equals the value obtained by
  applying the documented BRL parse rules to that row's stored raw amount text (round-trip
  consistency), verifiable from D1 alone.
- **SC-004**: A row-level parse failure is discoverable after the fact from the run record (the
  offending raw text is recorded), with **0** silent data loss (no failed cell stored as a bogus
  numeric value).

## Assumptions

- **Provenance shape — separate raw columns, not a JSON blob.** The issue offered "a `raw` provenance
  column OR one JSON `raw_row` per entry". We add two discrete nullable TEXT columns on `entries`
  (`raw_amount`, `raw_description`) rather than a JSON blob, because they are queryable with plain SQL,
  map cleanly to Drizzle columns, and the audit-relevant raw fields on an entry are exactly these two
  (amount + description). Subtotal/approver/demonstrativo raw text is out of scope for this feature.
- **Keep `amount` as REAL; do NOT migrate to integer centavos.** The issue's first suggestion (store
  integer centavos) is deferred. Changing the column type would ripple through analysis Python, the
  TypeScript/UI tolerance math, the reconciliation tolerances, and several migrations — a far larger,
  riskier change — while the raw-text column already removes the "float-representation question" for
  audit purposes (the exact portal text is recoverable). Centavos remains a candidate for a separate
  follow-up (it pairs with IMP-006).
- **`scrape_run_id` on mirror rows is out of scope.** The issue's fourth suggestion (carry
  `scrape_run_id` on `entries`/`attachments`) is a distinct provenance concern and is left to a
  separate feature; it does not block the raw-value preservation goal.
- **Attachments need no raw column.** `attachments` mirror rows carry no parsed monetary/text field
  that is lossy at scrape time (their amount/vendor/date come from analysis of page images, not from a
  parsed portal cell), so the raw-provenance need is on `entries` only.
- **Row-skip is the failure policy.** On an unparseable amount we skip the row (it never enters D1)
  rather than storing a sentinel; this keeps the mirror an exact-portal mirror of *parseable* rows and
  lets feature-028 reconciliation behave naturally. The skip is recorded as a non-fatal run note.
- **Raw description = pre-normalization, pre-prefix-strip.** "Raw description" is the text exactly as
  extracted from the portal cell (`.strip()` of the cell only), before whitespace normalization and
  before fornecedor-prefix stripping, so the most original recoverable form is stored.
