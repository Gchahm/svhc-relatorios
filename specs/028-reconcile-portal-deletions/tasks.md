# Tasks: Reconcile Portal Deletions on Period Re-scrape

**Feature**: `028-reconcile-portal-deletions` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are REQUESTED by the spec (FR-010) — test tasks are included.

## Phase 1: Setup

- [X] T001 Confirm the scrape-path runtime: from repo root run `cd scripts && python -m unittest discover -s tests -t .` to establish a green baseline, and note the existing pure-merge convention in `scripts/scraper/preserve.py` + its test `scripts/tests/test_attachment_preserve.py` that this feature mirrors.

## Phase 2: Foundational (blocking prerequisites)

- [X] T002 Create the pure module skeleton `scripts/scraper/reconcile.py`: module docstring (stdlib-only, playwright-free, mirrors `preserve.py`), `from __future__ import annotations`, imports limited to `json`, `dataclasses`, and `common.det_id`/`common.now_ms`; define the dataclasses `ExistingRows`, `ScrapedIds`, and `ReconcileResult` exactly as in `specs/028-reconcile-portal-deletions/contracts/reconcile.md`.
- [X] T003 In `scripts/scraper/reconcile.py` add the private SQL helpers: a single-quote `_sql_str()` escaper (mirror `scripts/common/d1.py:_escape_sql` string branch) and an `_in_list(ids)` that renders `('a','b')` for a non-empty id set (and signals "skip this statement" for an empty set), so every id-list literal is safely escaped.

## Phase 3: User Story 1 — Mirror exactly matches the portal (Priority: P1)

**Goal**: A re-scrape removes from the mirror every `entries`/`attachments`/`category_subtotals`/`approvers` row the portal no longer returns.

**Independent test**: `build_reconciliation` over (existing has E1,E2,E3; scraped has E1,E2) yields `stale_entry_ids={E3}` and emits a `DELETE FROM "entries" ... WHERE "id" IN ('E3')`; the no-op case (existing==scraped) emits no entry/attachment delete.

- [X] T004 [US1] In `scripts/scraper/reconcile.py` implement the diff inside `build_reconciliation`: compute `stale_entry_ids`, `stale_attachment_ids` (`(existing − scraped) ∪ {attachments whose entry_id ∈ stale_entry_ids}`), `stale_subtotal_ids`, `stale_approver_ids`, and an `anything_stale` flag, per `data-model.md`.
- [X] T005 [US1] In `scripts/scraper/reconcile.py` build the mirror DELETEs (only for non-empty id sets): `attachments` (id IN SA), `entries` (id IN SE), `category_subtotals` (id IN stale_subtotal_ids), `approvers` (id IN stale_approver_ids); populate `ReconcileResult.deleted_counts` with the per-table stale counts.
- [X] T006 [P] [US1] In `scripts/tests/test_reconcile.py` add `test_noop_when_identical`, `test_stale_entry_diffed`, `test_subtotals_and_approvers_diffed`, and `test_surviving_rows_untouched` asserting the diff + mirror DELETEs from the contract.

**Checkpoint**: stale mirror rows are computed and deleted; surviving rows untouched.

## Phase 4: User Story 2 — Vanished-row critical alert with frozen evidence (Priority: P1)

**Goal**: Every reconcile that removes rows raises one idempotent `critical` `portal_row_vanished` alert per period carrying the deleted rows' frozen values.

**Independent test**: `build_reconciliation` with a stale entry returns `alert` with `type='portal_row_vanished'`, `severity='critical'`, `id == det_id("alert", period, "portal_row_vanished")`, and `metadata.deleted_entries` listing E3's frozen id/date/description/amount; the sql always DELETEs that period's prior `portal_row_vanished` alert before the INSERT.

- [X] T007 [US2] In `scripts/scraper/reconcile.py` build the alert payload dict (per `data-model.md`): keys `id` (`det_id("alert", period, "portal_row_vanished")`), `created_at` (`now_ms()`), `type`, `severity="critical"`, `title`, `description` (counts + period), `reference_period`, `metadata` (JSON: `entry_ids`, `deleted_entries` frozen values, `deleted_attachment_ids`, `deleted_subtotal_ids`, `deleted_approver_ids`, `counts`), `resolved=0`, `resolved_at=None`, `notes=None`. Set `ReconcileResult.alert` to this dict when `anything_stale`, else `None`.
- [X] T008 [US2] In `scripts/scraper/reconcile.py` assemble `ReconcileResult.sql`: prefix `PRAGMA defer_foreign_keys = ON;`, then the cascade + mirror DELETEs, then ALWAYS `DELETE FROM "alerts" WHERE "type"='portal_row_vanished' AND "reference_period"=<p>`, then (only when `anything_stale`) the `INSERT OR REPLACE INTO "alerts" (...) VALUES (...)` for the alert dict — one batch string. When nothing is stale, `sql` is the clear-only alert DELETE.
- [X] T009 [P] [US2] In `scripts/tests/test_reconcile.py` add `test_alert_idempotent_id`, `test_atomic_single_batch` (one string, starts with the defer-FK pragma, contains the alerts DELETE then INSERT), and `test_escaping` (an id/description with a `'` is doubled).

**Checkpoint**: deletions produce exactly one idempotent critical alert with frozen evidence, in the same batch.

## Phase 5: User Story 3 — Cascade-clean analysis-owned dependents (Priority: P2)

**Goal**: Reconciling a mirror row away removes its analysis-owned dependents and never touches surviving rows' state.

**Independent test**: with a stale attachment SA, the sql contains DELETEs for `attachment_analysis_records` (via the `attachment_analyses` subquery), `attachment_analyses`, `attachment_state`, `page_classifications`, and `document_entries` (by `entry_id IN SE OR source_attachment_id IN SA`), all scoped to the stale id sets.

- [X] T010 [US3] In `scripts/scraper/reconcile.py` build the cascade DELETEs (only for non-empty sets), ordered child→parent, per `data-model.md` steps 1–5: `attachment_analysis_records` (`attachment_analysis_id IN (SELECT id FROM "attachment_analyses" WHERE "attachment_id" IN SA)`), `attachment_analyses` (attachment_id IN SA), `attachment_state` (attachment_id IN SA), `page_classifications` (attachment_id IN SA), `document_entries` (entry_id IN SE OR source_attachment_id IN SA). Place them before the `attachments`/`entries` mirror DELETEs in the batch.
- [X] T011 [P] [US3] In `scripts/tests/test_reconcile.py` add `test_stale_entry_cascades_attachment` (entry-gone forces its attachment into SA even if the scrape still listed it, and the five dependents are deleted) and `test_independent_stale_attachment` (an attachment gone from the scrape whose entry survives is still cascade-cleaned).

**Checkpoint**: all dependents of a removed mirror row are cleaned; surviving rows' analysis state untouched.

## Phase 6: Wire reconciliation into the scrape runner (integration)

- [X] T012 In `scripts/scraper/runner.py` import `build_reconciliation`, `ExistingRows`, `ScrapedIds` from `.reconcile`. On the period scrape-success path in `run_scrape` (after `d1.upsert_tables(period_data)` succeeds, before `break`): build `ScrapedIds` from `period_data` (entries/attachments/category_subtotals/approvers ids), `d1.query` the four `ExistingRows` sets for the period (mirror the existing period-join read at runner.py:500-506, threading `target`), call `build_reconciliation(periodo, existing, scraped)`, and if `result.sql` is non-empty run `d1.execute_sql(result.sql, target=target)` and log `result.deleted_counts` + whether an alert fired. Reconciliation runs ONLY here (success path) so a failed/retried period never reconciles (FR-008).

## Phase 7: Polish & cross-cutting

- [X] T013 Run the full Python test suite (`cd scripts && python -m unittest discover -s tests -t .`) and confirm green; fix any failures in `scripts/scraper/reconcile.py`.
- [X] T014 Update `CLAUDE.md`'s "Important Patterns" with a one-paragraph note on the re-scrape reconciliation (mirror-authoritative re-scrape: stale-row hard-delete + cascade cleanup + `portal_row_vanished` critical alert, atomic batch via `reconcile.py`), matching the BUG-001/feature-024 note style.
- [X] T015 Verify against running app + local D1 per `quickstart.md` (simulate a portal deletion against local 2026-01 data, confirm rows + dependents removed and the `portal_row_vanished` alert renders in `/dashboard/alerts`); record the verification in the PR body.

## Dependencies & order

- Setup (T001) → Foundational (T002–T003) → US1 (T004–T006) → US2 (T007–T009) → US3 (T010–T011) → Integration (T012) → Polish (T013–T015).
- US2 and US3 build SQL pieces consumed by the single `sql` assembly (T008) — implement T004–T011 in order; the `[P]` test tasks (T006, T009, T011) may be written in parallel with each other once their target behavior exists.
- T012 depends on the full `build_reconciliation` (T004–T011). T015 depends on T012.

## Implementation strategy

MVP = US1 + US2 (P1): a re-scrape makes the mirror exact and records the loss as a critical alert.
US3 (P2) is the cascade hygiene that must ship with the deletes (FK `ON DELETE no action` means the
attachment DELETE would otherwise fail), so all three land together in one PR — the pure module
makes them a single cohesive unit. Integration (T012) is the only impure change; everything else is
unit-tested in isolation.
