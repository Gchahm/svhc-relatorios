# Feature Specification: Scrape-time consistency validation

**Feature Branch**: `029-scrape-consistency-validation`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "add scrape-time consistency validation that cross-checks entries vs category subtotals vs demonstrativo totals and records mismatches"

## Context

The scraper extracts three independent views of the same money for each accountability period:

1. **Entries** (`lancamentos`) — every individual ledger line, each with an amount and a movement type (C = revenue/credit, D = expense/debit) and a subcategory.
2. **Category subtotals** (`category_subtotals`) — the portal's consolidated per-subcategory totals (one amount per subcategory + movement type).
3. **Demonstrativo totals** — the portal's headline figures: total revenue (`total_receitas`) and total expenses (`total_despesas`).

These three are scraped from different parts of the portal's HTML and written to the database with no cross-check. If an HTML-parsing regression drops a row, double-counts a row, or mis-attributes a value, nothing notices at scrape time. The inconsistency only surfaces much later as confusing analysis output, by which point it is hard to tell a scraper bug from genuine (or manipulated) portal data.

A ledger whose own three views do not add up is a finding worth surfacing regardless of cause: it indicates either a scraper bug **or** manipulated portal HTML.

## Clarifications

### Session 2026-06-12

Running unattended (no interactive clarifier); the decisions below were taken as reasonable defaults and are recorded here so downstream phases treat them as settled. Full rationale is in the Assumptions section.

- Q: Where is a consistency mismatch persisted — a new dedicated table or the existing alerts surface? → A: The existing `alerts` table/dashboard, as a new `scrape_inconsistency` alert type (no schema migration).
- Q: What severity should a "ledger doesn't add up" finding carry? → A: `warning` (an integrity signal that can be benign parsing noise or a tampering signal; not auto-escalated to `critical`).
- Q: How do the demonstrativo totals map to movement type for the cross-check? → A: `total_receitas` ↔ credit (C) subtotal sum; `total_despesas` ↔ debit (D) subtotal sum. Saldo/balance figures are not separately cross-checked (they carry prior-period state).
- Q: What tolerance distinguishes rounding from a real discrepancy? → A: Reuse the pipeline's existing reconciliation tolerance (~5% relative OR ~R$0.05 absolute) — one meaning of "consistent" across the system.
- Q: When the entry-vs-subtotal granularity differs, what is the comparison key? → A: Per `(subcategory, movement_type)`, so credit and debit lines in the same subcategory never net against each other; a present side with no counterpart is compared against zero.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect and record a ledger that does not add up (Priority: P1)

As an auditor relying on the scraped ledger, when the scraper captures a period whose three internal views of the money disagree beyond the portal's own rounding, the system records that disagreement as a queryable, dashboard-visible finding so I can investigate whether it is a scraper bug or tampered data — instead of the discrepancy silently passing through.

**Why this priority**: This is the core value of the feature — turning a silent, late-surfacing inconsistency into an immediate, attributable signal. Everything else is supporting detail.

**Independent Test**: Scrape (or re-scrape) a period whose entries do not sum to its category subtotals, or whose subtotals do not sum to the demonstrativo revenue/expense totals; confirm a consistency finding is recorded for that period (visible on the alerts dashboard and queryable in the data store) carrying both the computed sum and the reported total.

**Acceptance Scenarios**:

1. **Given** a scraped period whose per-subcategory entry sums match the category subtotals and whose subtotal-by-movement-type sums match the demonstrativo revenue/expense totals (within tolerance), **When** the period is scraped, **Then** no consistency finding is recorded for that period and any prior consistency finding for that period is cleared.
2. **Given** a scraped period where the entries for a subcategory sum to a value differing from that subcategory's recorded subtotal beyond tolerance, **When** the period is scraped, **Then** a consistency finding is recorded for that period that identifies the affected subcategory and reports both the entry-sum and the subtotal.
3. **Given** a scraped period where the sum of all expense (D) subtotals differs from the demonstrativo total expenses (or revenue/credit sum differs from total revenue) beyond tolerance, **When** the period is scraped, **Then** a consistency finding is recorded for that period reporting both the computed total and the demonstrativo total.
4. **Given** a period that previously had a consistency finding, **When** it is re-scraped and now adds up, **Then** the prior finding for that period is cleared (no stale finding lingers).

### User Story 2 - Prominent operator warning at scrape time (Priority: P2)

As the operator running the scrape, when a period fails the consistency cross-check, I see a prominent warning in the scrape log naming the period and showing the disagreeing numbers, so I notice the problem during the run rather than discovering it days later.

**Why this priority**: Improves the operator's loop and helps distinguish a fresh parsing regression from old data, but the durable, queryable record (P1) is what makes the signal not get lost.

**Independent Test**: Run a scrape over a period crafted to fail the cross-check and confirm the run log contains a clearly-marked warning naming the period and both disagreeing numbers.

**Acceptance Scenarios**:

1. **Given** a period that fails the cross-check, **When** the scrape processes it, **Then** the run log emits a warning-level message identifying the period and the disagreeing computed-vs-reported numbers.
2. **Given** the scrape run record for that run, **When** it is inspected after the run, **Then** the consistency mismatch is recorded on the run's error/notes field so it is queryable.

### User Story 3 - No false alarms on legitimate rounding (Priority: P2)

As an auditor, I do not want to be flooded with findings caused by the portal's own cent-level rounding, so the cross-check tolerates a small absolute difference and a small relative difference, and only records a finding for a genuine discrepancy.

**Why this priority**: A noisy check that fires on every period would be ignored, defeating the purpose. Tolerance is essential to the check's credibility.

**Independent Test**: Scrape a representative set of historically-good periods (the local prod-like data) and confirm zero consistency findings are recorded for periods whose only differences are sub-tolerance rounding.

**Acceptance Scenarios**:

1. **Given** a subcategory whose entry sum differs from its subtotal by an amount within the rounding tolerance, **When** the period is scraped, **Then** no finding is recorded for that subcategory.
2. **Given** the demonstrativo totals differing from the subtotal sums by an amount within tolerance, **When** the period is scraped, **Then** no demonstrativo-level finding is recorded.

### Edge Cases

- **A subcategory has entries but no subtotal (or a subtotal but no entries).** Treated as a discrepancy: the missing side is taken as zero, so a non-zero present side that exceeds tolerance is reported. This is exactly the "dropped row" regression the feature targets.
- **A period with no entries / no subtotals at all.** Vacuously consistent (all sums are zero) — no finding.
- **Both credit (C) and debit (D) lines exist within the same subcategory** (the source consolidates subtotals per `(subcategory, movement_type)`). Entry sums are compared per `(subcategory, movement_type)` so credit and debit lines never net against each other.
- **A re-scrape that fixes a previously-inconsistent period.** The prior finding for the period is cleared (idempotent, period-scoped).
- **A re-scrape that still finds the period inconsistent.** The finding is re-recorded idempotently (stable per-period identity) and the operator's prior disposition (resolved state / notes) on that finding is preserved across the re-scrape.
- **The scrape of a period fails or is retried.** The consistency check runs only on the scrape-success path for that period, so a failed/empty scrape is never mistaken for an inconsistency.
- **A period whose `accountability_reports` row is absent** (no demonstrativo) — does not occur, because the report is always built before the check; the demonstrativo totals are available in memory.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: After a period is extracted and its rows are persisted successfully, the system MUST cross-check that period's three views of the money: (a) per-`(subcategory, movement_type)` entry sums against the recorded category subtotals, and (b) the subtotal sums grouped by movement type against the demonstrativo total revenue (credit) and total expenses (debit).
- **FR-002**: The cross-check MUST treat two numbers as consistent when they agree within a tolerance that accommodates the portal's own rounding (a small absolute floor combined with a small relative band), and as a discrepancy otherwise. The tolerance MUST be the same notion already used elsewhere in the pipeline for reconciliation so behavior is consistent.
- **FR-003**: When any cross-check for a period fails, the system MUST record one durable, queryable consistency finding for that period that enumerates the specific failing comparisons, each carrying the computed sum, the reported total, and enough identity (subcategory and/or movement type) to locate the source.
- **FR-004**: The consistency finding MUST be surfaced on the alerts dashboard with a severity reflecting that a ledger that does not add up is a meaningful integrity signal, and MUST follow the established alert metadata convention so any affected entries are deep-linkable from the dashboard.
- **FR-005**: When a period passes all cross-checks (or a previously-failing period is re-scraped and now passes), the system MUST ensure no consistency finding remains for that period (the finding is cleared idempotently). A period's finding MUST have a stable identity so re-scrapes do not accumulate duplicates.
- **FR-006**: When a period fails the cross-check, the system MUST emit a prominent warning in the scrape run log naming the period and the disagreeing numbers, and MUST record the mismatch on the scrape run's error/notes record so it is queryable after the run.
- **FR-007**: The consistency check MUST run only on the scrape-success path for a period (never on a failed or retried-away period), consistent with how the existing portal-deletion reconciliation is gated.
- **FR-008**: A consistency finding's operator disposition (its resolved state and notes) MUST be preserved when the same period is re-scraped and the finding re-fires, matching the existing behavior for re-emitted scrape-time findings.
- **FR-009**: The recording of a consistency finding (clearing the prior one and inserting the new one) MUST be atomic for the period, so a partial failure can never leave a period with a cleared-but-not-replaced or duplicated finding, matching the existing atomic delete-then-insert convention for scrape/analysis writebacks.
- **FR-010**: The feature MUST NOT alter the mirror data model: it adds no column to the mirror tables and writes no new mirror data; the only new persisted state is the analysis-owned finding (and the existing scrape-run error/notes field). The check is a read-only pass over data already in memory plus the finding writeback.

### Key Entities *(include if feature involves data)*

- **Consistency finding**: An analysis-owned record that a period's three views of the money disagree. Period-scoped, stably identified per period (so re-scrapes are idempotent), carrying: the list of failing comparisons (each with a kind — subcategory-level or demonstrativo-level — an identifier, the computed sum, and the reported total), and following the dashboard alert conventions (severity, title, description, period, and metadata with affected entry ids for deep-linking). Stored alongside the other scrape-time findings; not a mirror table change.
- **Scrape run error/notes**: The existing per-run field that records run-level problems; a consistency mismatch is appended here so it is queryable per run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any period whose three internal views of the money disagree beyond the rounding tolerance, a consistency finding is recorded within the same scrape run — 100% of such periods are flagged, with zero requiring a later analysis pass to surface the disagreement.
- **SC-002**: Across the full set of historically-good local (prod-like) periods, the cross-check records zero consistency findings — no false alarms from legitimate cent-level rounding.
- **SC-003**: A single dropped or double-counted entry that shifts a subcategory total beyond tolerance is detected at scrape time, with the finding naming the affected subcategory and reporting both the entry-sum and the recorded subtotal.
- **SC-004**: Re-scraping a period never accumulates duplicate consistency findings for that period, and re-scraping a now-consistent period leaves no stale finding — verified by scraping the same period twice and observing exactly zero or one finding (matching the period's current state) each time.
- **SC-005**: An operator watching the scrape log sees a clearly-marked warning naming any inconsistent period and its disagreeing numbers during the run.

## Assumptions

- **Movement-type partitioning of demonstrativo totals**: The demonstrativo `total_receitas` corresponds to the sum of credit (C) movement and `total_despesas` to the sum of debit (D) movement. The cross-check compares the sum of C-typed subtotals against `total_receitas` and the sum of D-typed subtotals against `total_despesas`. (Saldo/balance figures are derived from these and are not separately cross-checked, since they carry forward prior-period state not present in this period's entries.)
- **Tolerance reuse**: The existing reconciliation tolerance used elsewhere in the pipeline (within ~5% relative OR ~R$0.05 absolute) is reused for the cent-level rounding band, rather than introducing a new, separately-tuned tolerance. This keeps "consistent" meaning one thing across the system.
- **Finding type & severity**: The finding is recorded as a new alert type `scrape_inconsistency`. A ledger whose own subtotals don't add up is treated as a `warning`-severity integrity signal (it can be a benign parsing artifact or a serious tampering signal; surfacing it without over-escalating every cent of historical noise). It reuses the existing `alerts` table and dashboard with no schema change, following the same per-period idempotent-id + atomic delete-then-insert + resolution-graft conventions as the `portal_row_vanished` scrape-time alert.
- **Where the check runs**: Inside the scraper's per-period success path (after the upsert + portal-deletion reconciliation), reusing the in-memory extracted entries, subtotals, and demonstrativo totals — no extra portal round-trip and no extra full table read beyond the small per-period reads the surrounding steps already perform.
- **Pure, testable core**: The discrepancy detection + finding/SQL construction is a pure, dependency-free module (no portal/browser import) so it is unit-testable directly, mirroring the existing `preserve.py` / `reconcile.py` modules; the impure database reads/writes stay in the runner.
- **Metadata deep-link convention**: The finding's metadata carries the affected entry ids (the entries belonging to any subcategory that failed its subcategory-level check) under the established `entry_ids` key, so the alerts dashboard deep-links them like the other findings. Demonstrativo-level-only failures (no specific subcategory) carry an empty entry id list.
- **No new dependencies**: Python stdlib only for the new module; no new npm or pip dependencies; no Drizzle migration.
