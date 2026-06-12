# Research: Shared alert type → label map

## Decision 1 — Module location & shape

**Decision**: New module `src/lib/alerts.ts` exporting a pure `alertTypeLabel(type: string): string`
and a curated `ALERT_TYPE_LABELS: Record<string, string>` constant.

**Rationale**: The issue explicitly names `src/lib/alerts.ts`. `src/lib/` is the established home for
framework-agnostic pure helpers (`src/lib/documents.ts`, `src/lib/utils.ts`) and is unit-testable
without React. A pure function with a generic fallback means the call sites never change for new types.

**Alternatives considered**:
- Co-locate in `src/app/dashboard/alerts/alerts.tsx` — rejected: that is a client `.tsx` module
  coupled to React/Badge components; the issue names `src/lib/alerts.ts`; a pure string fn shouldn't
  live behind a `"use client"`-adjacent JSX module.
- A `Map` instead of a record literal — rejected: a plain object record is simpler, matches the
  existing `KEY_LABELS` pattern in `alerts.tsx`, and is trivially type-checked.

## Decision 2 — Fallback transform

**Decision**: For an uncurated type, replace `_` with spaces, then capitalize the first character of
the whole string (sentence case), leaving the rest lowercase. Empty string → empty string.

**Rationale**: The issue asks for "snake_case → Title Case". Sentence-case ("Attachment amount
mismatch") reads more naturally for these phrase-like identifiers than capitalizing every word
("Attachment Amount Mismatch") and matches the friendly-label tone of the curated entries. The
curated map exists precisely so high-value/acronym types read exactly right; the fallback only needs
to be readable, not perfect. Total (never throws) for any input including empty/non-snake.

**Alternatives considered**:
- Capitalize every word — rejected: noisier for multi-word phrases; curated entries are sentence-case.
- Throw / return raw on unknown — rejected: violates FR-003/FR-007 (no surface may render raw).

## Decision 3 — Curated type list source

**Decision**: Seed the curated map from the alert types currently emitted by the pipeline, found by
grepping `scripts/analysis/checks/`, `scripts/analysis/`, and `scripts/scraper/`:
`attachment_amount_mismatch`, `attachment_vendor_mismatch`, `attachment_date_mismatch`,
`attachment_page_error`, `attachment_not_downloaded`, `document_overpayment`, `duplicate_billing`,
`duplicate_entry`, `negative_credit`, `large_expense_no_attachment`, `unit_delinquency`,
`subtotal_mismatch`, `balance_opening_mismatch`, `balance_month_mismatch`,
`balance_accumulated_mismatch`, `entries_revenue_mismatch`, `entries_expenses_mismatch`,
`portal_row_vanished`, `scrape_inconsistency`.

**Rationale**: Covers 100% of currently-emitted types (SC-001). The fallback covers anything missed
or added later (SC-002), so the list need not be perfectly exhaustive to be correct.

**Alternatives considered**: Deriving labels from the Python source at build time — rejected:
over-engineered; the type set changes rarely and the fallback already guarantees safety.

## Decision 4 — Testing

**Decision**: `src/lib/alerts.test.mjs` using Node's built-in `node:test` runner, importing the real
`alerts.ts` via native TS type-stripping (Node ≥ 22.18), mirroring `src/lib/documents.test.mjs`.

**Rationale**: No new dependency; the repo already runs `node --test "src/**/*.test.mjs"`. Tests the
total contract: curated lookup, fallback transform, empty string, and a non-snake input.
