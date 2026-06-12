# Phase 0 Research: Reconcile Portal Deletions on Period Re-scrape

All Technical-Context unknowns were resolvable from the existing codebase — no external research
needed. Decisions below are grounded in concrete files.

## D1. Where reconciliation hooks into the scrape

- **Decision**: Reconcile inside `scripts/scraper/runner.py:run_scrape`, immediately after a
  period's `d1.upsert_tables(period_data)` succeeds (the `last_error = None; break` path), before
  moving to the next period. The freshly-scraped id sets come from `period_data`; the existing id
  sets are read from D1 with `d1.query` scoped to the period.
- **Rationale**: Upserting first guarantees the surviving rows are present, so the diff "existing in
  D1 − scraped" yields exactly the rows the portal no longer returns. Running it on the success path
  (not the retry/error path) satisfies FR-008 (no reconciliation on a failed scrape).
- **Alternatives considered**: A separate `reconcile` CLI command — rejected; the issue frames this
  as making *the re-scrape* authoritative, and a separate command would let drift persist until a
  human remembers to run it.

## D2. Strict delete vs. soft-delete flag

- **Decision**: Hard-delete the mirror rows; record evidence in a `critical` `alerts` row.
- **Rationale**: The mirror-table invariant (`entries`/`attachments` are an EXACT portal mirror)
  forbids adding analysis/soft-delete columns to a mirror table. The `alerts` table is analysis-owned
  and already the home for findings (`metadata` JSON column exists), so it carries the evidence
  without touching a mirror table or a migration. This is the spec's Assumption 1 — combining both
  options the issue offered.
- **Alternatives considered**: `portal_deleted_at` soft-delete column on `entries`/`attachments`
  (BUG-002 style) — rejected: violates the exact-mirror invariant and keeps phantom rows that still
  pollute subtotal checks / document links. Requires a migration.

## D3. Atomicity mechanism

- **Decision**: Build the whole reconciliation as one SQL string (a `PRAGMA defer_foreign_keys =
  ON;` header + the cascade DELETEs ordered child-before-parent-agnostic + the `alerts` DELETE +
  the `alerts` INSERT) and run it through a single `d1.execute_sql(sql, target=target)` call — one
  D1 batch / implicit transaction.
- **Rationale**: This is the exact convention feature 024 established
  (`scripts/analysis/__init__.py` writes `DELETE FROM alerts … ; <upsert_sql>` in one
  `execute_sql`; `scripts/analysis/attachments.py:_merge_and_write` folds DELETEs + INSERT +
  UPDATE in one batch). `PRAGMA defer_foreign_keys = ON` (already emitted by `d1.build_sql`) lets
  the deletes ignore intra-batch FK ordering. A partial failure leaves the mirror untouched
  (FR-009).
- **Alternatives considered**: Two `execute_sql` calls (delete, then alert) — rejected; a failure
  between them could delete without recording evidence. Drizzle/`getDb()` transaction — N/A, this is
  the Python scrape path which only reaches D1 via the wrangler wrapper.

## D4. Alert row shape + id (idempotency)

- **Decision**: Build the `alerts` row dict directly in the reconcile module (stdlib only), matching
  `scripts/analysis/models.py:Alert.to_dict()`: keys `id, created_at, type, severity, title,
  description, reference_period, metadata (JSON text), resolved (0), resolved_at (None), notes
  (None)`. `type = "portal_row_vanished"`, `severity = "critical"`, `id = det_id("alert", period,
  "portal_row_vanished")` (stable per period). Idempotency: the batch always `DELETE FROM alerts
  WHERE type = 'portal_row_vanished' AND reference_period = '<p>'` then INSERTs the current row —
  so a re-scrape with the same deletions replaces (not accumulates), and a re-scrape with **no**
  deletions runs the DELETE only (clearing a stale vanished alert) and inserts nothing.
- **Rationale**: Reuses the deterministic-id + delete-then-insert idempotency the rest of the alert
  pipeline uses (FR-007). The stable per-period id means the frontend deep links and the
  feature-023 resolution-preservation behavior work unchanged.
- **Alternatives considered**: One alert per vanished row (id keyed to the row) — rejected per
  spec Assumption 3 (noisy, harder to keep idempotent across partial re-deletions). Reusing the
  Python `Alert` dataclass from `scripts/analysis` — rejected to keep the scraper free of an
  analysis-package import; a plain dict is trivial and keeps `reconcile.py` dependency-light.

## D5. Reading existing ids + frozen values per table

- **Decision**: One `d1.query` per period for the four mirror tables (joined to
  `accountability_reports` by `period` where needed):
  - `entries` (id, date, description, amount) — frozen evidence + diff.
  - `attachments` (id, entry_id, external_document_id) via join `entries → reports` — diff + cascade
    keys.
  - `category_subtotals` (id) via `report_id` for the period's report — diff.
  - `approvers` (id) via `report_id` — diff.
- **Rationale**: `entries`/`category_subtotals`/`approvers` hang off `report_id`
  (`_report_id(period)` is deterministic); `attachments` reach the period only via `entries`
  (mirrors the join the scraper's preserve step already uses). Reading the full frozen `entries`
  fields lets the alert metadata carry evidence after the rows are gone (FR-006).
- **Alternatives considered**: Reading ids from `period_data` only and trusting it as the existing
  set — wrong; `period_data` is the *new* set; the existing set must come from D1.

## D6. Cascade targets and ordering

- **Decision**: For the set of stale entry ids `SE` and stale attachment ids `SA` (where `SA` =
  attachments whose `entry_id ∈ SE` **plus** any attachment independently stale), delete in this
  logical grouping inside the deferred-FK batch:
  - `attachment_analysis_records` WHERE `attachment_analysis_id IN (SELECT id FROM
    attachment_analyses WHERE attachment_id IN SA)`
  - `attachment_analyses` WHERE `attachment_id IN SA`
  - `attachment_state` WHERE `attachment_id IN SA`
  - `page_classifications` WHERE `attachment_id IN SA`
  - `document_entries` WHERE `entry_id IN SE` OR `source_attachment_id IN SA`
  - `attachments` WHERE `id IN SA`
  - `entries` WHERE `id IN SE`
  - `category_subtotals` WHERE `id IN <stale subtotal ids>`
  - `approvers` WHERE `id IN <stale approver ids>`
- **Rationale**: Covers every FK dependent the schema map found (all `ON DELETE no action`, so the
  cascade must be explicit). `defer_foreign_keys = ON` makes the within-batch order safe, but the
  list above is already child-before-parent for clarity. Surviving rows and other periods are never
  matched because every WHERE is scoped to the stale id sets / the period's report (FR-005).
- **Alternatives considered**: Adding `ON DELETE CASCADE` via migration — rejected: a migration is
  out of scope (Assumption 2) and cascade-on-the-FK would also fire on legitimate deletes elsewhere,
  and the analysis-owned `attachment_state`/`document_entries` cleanup is a deliberate decision, not
  an automatic side effect we want hidden in the schema.

## D7. Pure, testable seam

- **Decision**: `scripts/scraper/reconcile.py` exposes a pure
  `build_reconciliation(period, existing, scraped, frozen) -> ReconcileResult` returning
  `(sql: str, deleted_counts: dict, alert: dict | None)`, with `sql == ""` and `alert is None` when
  nothing is stale. `runner.py` does the impure I/O (the `d1.query` reads and the `d1.execute_sql`).
- **Rationale**: Mirrors `scripts/scraper/preserve.py` (pure merge, playwright-free, unit-tested in
  `scripts/tests/test_attachment_preserve.py`). Satisfies FR-010 and the test convention.
