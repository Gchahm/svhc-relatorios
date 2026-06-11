# Feature Specification: Reconcile Portal Deletions on Period Re-scrape

**Feature Branch**: `028-reconcile-portal-deletions`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "Reconcile portal deletions on period re-scrape: hard-delete entries/attachments/category_subtotals/approvers no longer present on the portal, cascade-clean their analysis-owned dependents, and raise a critical alert recording the vanished rows' frozen values as evidence"

## Context (BUG-004)

The scrape today is **add/update only**. A period re-scrape upserts the rows that still exist on
the brcondos portal and leaves any rows that were *removed* from the portal in the mirror forever.
The mirror tables (`entries`, `attachments`, `category_subtotals`, `approvers`) silently stop being
"exactly what exists on the portal." Because this project exists to detect fiscal manipulation, a
row that *vanishes* from the portal (e.g. an entry quietly removed after being questioned) is itself
a high-value signal — but today it is indistinguishable from current portal data and pollutes
subtotal checks, document links, and alert deep links.

## Clarifications

### Session 2026-06-11

Resolved automatically (unattended run) with informed defaults; recorded here and reflected in the
relevant Requirements/Assumptions:

- Q: Hard-delete the mirror rows or soft-flag them with a `portal_deleted_at` column? → A: Hard-delete
  (preserve the exact-mirror invariant — no analysis/soft-delete column on a mirror table) AND record
  evidence in the analysis-owned `alerts` table (Assumption 1, FR-002, FR-006).
- Q: How is the "freshly scraped id set" determined for the diff? → A: From the period payload the
  scrape just built (the upsert input), compared against the ids currently in D1 for that period read
  back via the existing `d1.query` seam, post-upsert (FR-001, FR-010).
- Q: One vanished-row alert per row, or one per period summarizing all? → A: One per period per
  re-scrape, with all vanished rows' frozen values in `metadata` (Assumption 3, FR-006).
- Q: How is the vanished-row alert kept idempotent across re-scrapes? → A: Stable derived id keyed to
  the period; the reconcile delete + alert write is one atomic batch that DELETEs the period's prior
  `portal_row_vanished` alert and re-inserts the current one (matching the feature-024 atomic
  delete-then-insert convention) — and is skipped entirely when nothing vanished (FR-007, FR-009).
- Q: Are `vendors`/`units`/`categories`/`subcategories` reference tables reconciled? → A: No — they
  are global/shared and accrete; an unused reference row is harmless (Assumption 8).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A re-scrape makes the mirror exactly match the portal (Priority: P1)

When an auditor re-scrapes a period that previously had data, any ledger row that no longer exists
on the portal is removed from the mirror, so `entries`, `attachments`, `category_subtotals`, and
`approvers` for that period reflect exactly what the portal shows now — no phantom rows.

**Why this priority**: This is the core mirror-invariant fix; without it the mirror keeps drifting
and every downstream check (subtotals, documents, alerts) inherits stale data.

**Independent Test**: Seed a period with N entries. Re-scrape the same period with one entry removed
from the source. Confirm the mirror for that period now holds exactly the surviving rows and the
removed entry (and its attachment) is gone.

**Acceptance Scenarios**:

1. **Given** a period with entries E1, E2, E3 already in the mirror, **When** the period is
   re-scraped and the portal now returns only E1, E2, **Then** E3 is removed from `entries` and the
   mirror holds exactly {E1, E2} for that period.
2. **Given** a removed entry E3 had an attachment A3, **When** E3 is reconciled away, **Then** A3 is
   also removed from `attachments` (no orphaned attachment).
3. **Given** the portal returns the same rows it had before, **When** the period is re-scraped,
   **Then** no rows are deleted (the reconciliation is a no-op).
4. **Given** a `category_subtotals` row or an `approvers` row for the period that the portal no
   longer returns, **When** the period is re-scraped, **Then** that subtotal/approver row is removed.

---

### User Story 2 - Disappeared rows raise a critical alert with frozen evidence (Priority: P1)

When a row is reconciled away, the system records what disappeared: a `critical` alert is raised that
names the period and carries the deleted rows' frozen field values (date, description, amount, ids)
in its metadata, so the auditor sees "an entry vanished from the portal between scrapes" rather than
silently losing the evidence.

**Why this priority**: The issue explicitly states deletions are evidence — silently deleting turns
a fraud signal into a missing-data bug. The alert is what converts the mirror fix into a
fraud-detection feature, so it ships together with US1.

**Independent Test**: Re-scrape a period with one entry removed; confirm a `critical` alert of the
new type exists for that period whose metadata contains the removed entry's frozen values, and whose
deep-link affected-entry resolves (or degrades gracefully now that the entry is gone).

**Acceptance Scenarios**:

1. **Given** entry E3 is reconciled away, **When** the re-scrape completes, **Then** exactly one
   `critical` alert exists for the period recording E3's frozen values (id, date, description,
   amount) in metadata.
2. **Given** multiple rows disappear in one re-scrape, **When** the re-scrape completes, **Then** the
   disappearances are recorded (one alert per period summarizing all vanished rows — see Assumptions)
   so none are lost.
3. **Given** a period re-scraped twice with no further deletions, **When** the second re-scrape
   completes, **Then** no duplicate vanished-row alert accrues for rows already deleted (the alert
   set is idempotent / stable across re-runs).

---

### User Story 3 - Analysis-owned state is cleaned without corrupting unrelated state (Priority: P2)

When a mirror row is reconciled away, every analysis-owned dependent that references it is removed
too (so no dangling analysis rows survive), while analysis state for *surviving* rows is left
untouched. The pipeline does not error on the next analysis run because of orphaned dependents.

**Why this priority**: Without cascade cleanup, deleting an attachment would either fail (FK
constraint) or leave orphaned `attachment_state` / `attachment_analyses` / `document_entries` rows
that crash or mislead later analysis. It is P2 only because it is internal hygiene riding on the P1
delete, not a user-visible deliverable.

**Independent Test**: Seed an attachment with `attachment_state`, an `attachment_analyses` row (+
records), a `page_classifications` row, and a `document_entries` link. Reconcile its entry away;
confirm all those dependents are gone and that another attachment's analysis state is unchanged.

**Acceptance Scenarios**:

1. **Given** a reconciled-away attachment A3 with rows in `attachment_state`,
   `attachment_analyses`, `attachment_analysis_records`, `page_classifications`, and a
   `document_entries` link, **When** A3 is deleted, **Then** all of those dependent rows are deleted.
2. **Given** a reconciled-away entry E3 with a `document_entries` link, **When** E3 is deleted,
   **Then** the link is deleted.
3. **Given** a surviving attachment A1 with analysis state, **When** A3 is reconciled away,
   **Then** A1's analysis state is unchanged.

---

### Edge Cases

- **Whole period emptied / removed on portal**: if the portal returns zero rows for a re-scraped
  period, every mirror row for that period is reconciled away and a vanished-row alert records the
  loss. (The `accountability_reports` row itself is upserted/retained as the period anchor.)
- **First scrape of a period**: there are no existing rows, so reconciliation deletes nothing.
- **Failed scrape**: a period whose scrape failed/raised must NOT trigger reconciliation — an empty
  or partial scrape result must never be mistaken for "the portal deleted everything." Reconciliation
  runs only for a period whose scrape succeeded and produced its row set.
- **Default skip of already-scraped periods**: the default scrape run skips periods already present
  in the mirror, so reconciliation only happens for periods explicitly re-scraped (`--periodo`) or
  re-scraped via `--book-ids`. (Out of scope to change the default-skip behavior here.)
- **Atomicity**: a partial failure must not commit some deletes without the alert (or vice versa) —
  the reconcile delete + alert write for a period is one transaction.
- **A `documents` row whose every linking entry is reconciled away**: the link rows
  (`document_entries`) are removed here; pruning a now-orphaned global `documents` row is left to the
  authoritative `build-documents` rebuild (feature 025), out of scope for this feature.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On a successful re-scrape of a period, the system MUST compute, per mirror table
  (`entries`, `attachments`, `category_subtotals`, `approvers`), the set of rows that exist in the
  mirror for that period but are absent from the freshly scraped row set ("stale" rows), keyed by
  primary id.
- **FR-002**: The system MUST remove the stale rows from the mirror so that, after the re-scrape,
  the mirror for that period contains exactly the freshly scraped rows.
- **FR-003**: When a stale `entries` row is removed, the system MUST also remove its attachment(s)
  and every analysis-owned dependent keyed to that entry or its attachment(s):
  `attachment_state`, `attachment_analyses`, `attachment_analysis_records`, `page_classifications`,
  and `document_entries` links (by `entry_id` and by `source_attachment_id`).
- **FR-004**: When a stale `attachments` row is removed (independently of an entry deletion), the
  system MUST also remove its `attachment_state`, `attachment_analyses` (+ their
  `attachment_analysis_records`), `page_classifications`, and `document_entries` links referencing it
  via `source_attachment_id`.
- **FR-005**: The reconciliation MUST NOT remove or alter mirror rows or analysis state for rows that
  still exist on the portal (surviving rows), nor rows belonging to other periods.
- **FR-006**: When any stale row is removed, the system MUST raise exactly one `critical` alert for
  the affected period recording the vanished rows as evidence; the alert's metadata MUST carry the
  frozen field values of the removed `entries` (at minimum id, date, description, amount) and the
  ids of removed attachments, so the loss is auditable after the rows are gone.
- **FR-007**: The vanished-row alert MUST be idempotent across re-scrapes of the same period: a
  re-scrape with no new deletions MUST NOT create an additional vanished-row alert, and a re-scrape
  with new deletions MUST reflect the current set of vanished rows for that re-scrape. The alert's
  user-set resolution/notes state is governed by the existing alert-preservation behavior
  (feature 023) and is out of scope to change.
- **FR-008**: Reconciliation MUST run only when a period's scrape succeeded (produced its row set);
  a failed or errored period scrape MUST NOT trigger any deletion.
- **FR-009**: The reconcile deletes, the cascade cleanup, and the vanished-row alert write for a
  period MUST be applied atomically (one transaction), so a partial failure leaves the mirror
  unchanged rather than half-deleted or with deletes but no evidence alert.
- **FR-010**: The reconciliation MUST be expressible as a pure function over (existing ids per table
  for the period, freshly scraped ids per table, frozen field values of stale rows) that produces the
  reconciliation statements + alert payload, so it is unit-testable without a live database (matching
  the project's `preserve.py` / writeback-builder convention).

### Key Entities *(include if feature involves data)*

- **Stale row set**: per mirror table, the ids present in the mirror for a period minus the ids the
  current scrape produced for that period. Drives the deletes.
- **Vanished-row alert**: a `critical` alert (new `type`) scoped to the period, carrying the frozen
  evidence of what disappeared in its metadata (deleted entry field values + deleted attachment ids).
  Idempotent per period.
- **Analysis-owned dependents**: `attachment_state`, `attachment_analyses`,
  `attachment_analysis_records`, `page_classifications`, `document_entries` — rows that reference a
  mirror row and must be cascade-cleaned when it is reconciled away (they live in their own tables;
  the mirror tables stay pure portal mirrors).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After re-scraping a period in which a row was removed from the portal, the mirror for
  that period contains exactly the rows the portal currently returns — 0 phantom rows remain.
- **SC-002**: Every reconciled-away row leaves a recorded trace: 100% of re-scrapes that delete at
  least one mirror row produce a `critical` vanished-row alert for that period containing the deleted
  rows' frozen values; no deletion is silent.
- **SC-003**: Re-scraping a period twice with no further portal deletions changes nothing on the
  second run — 0 rows deleted and no additional vanished-row alert created (idempotent).
- **SC-004**: After reconciliation, the analysis pipeline runs over the period without error and with
  0 orphaned analysis-owned rows referencing a deleted mirror row.
- **SC-005**: A re-scrape that produces the same rows it had before deletes 0 rows and creates 0
  vanished-row alerts.

## Assumptions

1. **Strict mirror + evidence-in-alert (combines both issue options).** The issue offered (a) hard
   delete + analysis-side record, or (b) flag with a `portal_deleted_at` soft-delete column. We adopt
   **hard delete of the mirror rows** (preserving the "`entries`/`attachments` are an EXACT portal
   mirror" invariant — no analysis/soft-delete column is added to a mirror table) **AND** record the
   evidence in a `critical` alert (whose `alerts` table / `metadata` JSON is analysis-owned, not a
   mirror table). This satisfies both the mirror invariant and the "deletions are evidence"
   requirement without a mirror-table schema change.
2. **No schema migration.** `alerts` already has the `metadata` JSON column and is the established
   home for findings; the cascade targets (`attachment_state`, etc.) already exist. The feature is
   pure scrape-path Python + SQL; no Drizzle migration is needed.
3. **One alert per period per re-scrape**, summarizing all rows that vanished in that re-scrape (a
   stable derived id keyed to the period), rather than one alert per vanished row — this keeps the
   alert list readable and idempotent. Affected-entry deep links use the existing `metadata.entry_ids`
   convention (feature 018), degrading gracefully since the entries are gone.
4. **New alert type** `portal_row_vanished` (severity `critical`), distinct from existing types.
5. **Reconciliation is per-period and runs inside the existing scrape run**, immediately after the
   period's upsert succeeds, against the same `target` (local/remote). It does not change the
   default behavior of skipping already-present periods; an auditor re-scrapes explicitly
   (`--periodo` / `--book-ids`) to trigger reconciliation.
6. **`accountability_reports` / `scrape_runs` rows are not reconciled-deleted** — the period anchor
   is retained (it is upserted by the scrape); only the four child mirror tables are reconciled.
7. **Pruning orphaned global `documents` rows is out of scope** — only the period-scoped
   `document_entries` links are cascade-cleaned here; the authoritative `build-documents` rebuild
   (feature 025) prunes documents whose links all disappeared.
8. **`vendors` / `units` / `categories` / `subcategories` reference tables are not reconciled** —
   they are global, shared across periods, and accrete; leaving an unused reference row is harmless
   and removing one could break other periods.
