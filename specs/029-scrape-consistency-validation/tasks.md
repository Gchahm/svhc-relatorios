# Tasks: Scrape-time consistency validation

**Feature**: 029-scrape-consistency-validation
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests ARE requested by the spec (SC-002/SC-004 + the constitution's "tests added when the spec requests them"). The pure detection module is the testable surface; the unittest file is included.

## Phase 1: Setup

- [X] T001 Confirm the scraper package layout and the `reconcile.py` pattern this feature mirrors: read `scripts/scraper/reconcile.py`, `scripts/scraper/runner.py` (`run_scrape` + `_reconcile_period`), and `scripts/common/__init__.py` (`det_id`, `now_ms`). No code change — orientation only.

## Phase 2: Foundational (blocking prerequisite for all stories)

- [X] T002 Create the pure, stdlib-only module `scripts/scraper/consistency.py` skeleton: module docstring (mirrors `reconcile.py`: PURE, no I/O, no `playwright`, no `scripts.analysis` import, unit-testable), the constants `AMOUNT_REL_TOL = 0.05`, `AMOUNT_ABS_TOL = 0.05`, `ALERT_TYPE = "scrape_inconsistency"`, `ALERT_SEVERITY = "warning"`, the `_sql_str` escape helper (copy the semantics from `reconcile._sql_str`), and the `Discrepancy` + `ConsistencyResult` dataclasses per data-model.md. Import only `json`, `dataclasses`, and `common.det_id`/`common.now_ms`.

## Phase 3: User Story 1 — Detect and record a ledger that does not add up (Priority: P1) 🎯 MVP

**Goal**: A successfully-scraped period whose three views disagree beyond tolerance produces one idempotent, period-scoped `scrape_inconsistency` alert; a consistent (or re-scraped-and-fixed) period leaves no finding.

**Independent test**: Run the unittest suite + (PR phase) the local-D1 cross-check; a crafted inconsistent period yields one alert row carrying both numbers, a consistent one yields none, and a now-fixed re-scrape clears the prior alert.

- [X] T003 [P] [US1] In `scripts/scraper/consistency.py`, implement `within_tolerance(value, reference)` exactly mirroring `nf_groups.within_tolerance` (abs floor OR relative band; ref>0 guard).
- [X] T004 [US1] In `scripts/scraper/consistency.py`, implement `detect_inconsistencies(entries, category_subtotals, total_receitas, total_despesas) -> (list[Discrepancy], list[str])` per data-model.md detection rules: subcategory-level per `(subcategory_id, movement_type)` (union of both maps, missing side = 0.0, rounded sums) and demonstrativo-level (C/D subtotal sums vs totals). Collect `affected_entry_ids` = sorted union of entry ids whose `(subcategory_id, movement_type)` key failed the subcategory check.
- [X] T005 [US1] In `scripts/scraper/consistency.py`, implement `_build_alert(period, discrepancies, affected_entry_ids)` returning the alerts row dict (stable id `det_id("alert", period, ALERT_TYPE)`, severity `warning`, title/description naming failing layers + largest disagreement, `reference_period`, default resolution fields, `metadata` JSON with `entry_ids`/`checks`/`counts`) — shape per data-model.md, mirroring `reconcile._build_alert`.
- [X] T006 [US1] In `scripts/scraper/consistency.py`, implement `_graft_resolution(alert, prior_resolution)` identical in semantics to `reconcile._graft_resolution` (coerce `resolved` via `int(... or 0)`; apply only when prior `resolved` truthy or `notes` non-empty).
- [X] T007 [US1] In `scripts/scraper/consistency.py`, implement `build_consistency_writeback(period, entries, category_subtotals, total_receitas, total_despesas, prior_resolution=None) -> ConsistencyResult`: call `detect_inconsistencies`; ALWAYS emit `DELETE FROM "alerts" WHERE "id" = '<id>';`; when inconsistent, build+graft the alert and append the `INSERT OR REPLACE INTO "alerts" (...) VALUES (...);` (columns/escaping per contract); set `summary` to a one-line human string (None when consistent); return the result.
- [X] T008 [US1] In `scripts/scraper/runner.py`, add the impure `_check_consistency(periodo, period_data, report, target)`: build the alert id, `d1.query` the prior `{resolved, resolved_at, notes}` for that id, call `build_consistency_writeback(...)`, `d1.execute_sql(result.sql, target=target)` (one batch), and return `result.summary` (or None). Import `build_consistency_writeback` (+ `ALERT_TYPE`) from `.consistency`.
- [X] T009 [US1] In `scripts/scraper/runner.py` `run_scrape`, call `_check_consistency(periodo, period_data, report, target)` on the per-period success path immediately after `_reconcile_period(...)`. NOTE: `report` is built inside `_scrape_periodo`; expose the demonstrativo totals to the success path by having `_check_consistency` read `total_revenue`/`total_expenses` from `period_data["accountability_reports"][0]` (the report dict is already inside `period_data`), so no signature change to `_scrape_periodo` is needed.

**Checkpoint**: US1 is a complete, testable MVP — detection + idempotent period-scoped alert writeback wired into the success path.

## Phase 4: User Story 2 — Prominent operator warning at scrape time (Priority: P2)

**Goal**: An inconsistent period logs a clearly-marked warning and is recorded on the scrape run's `errors` field without flipping the run to `error`.

**Independent test**: A scrape over an inconsistent period emits a `logger.warning` naming the period + numbers and, after the run, the run row's `errors` contains the consistency note while `status` stays `success`.

- [X] T010 [US2] In `scripts/scraper/runner.py` `_check_consistency`, when `result.discrepancies` is non-empty `logger.warning("  Consistency mismatch in %s: %s", periodo, result.summary)`; else `logger.info("  Consistency OK for %s", periodo)`.
- [X] T011 [US2] In `scripts/scraper/runner.py` `run_scrape`, introduce a `consistency_notes: list[str]` accumulator alongside `errors`; append the returned summary (when non-None) as `f"Consistency mismatch in {label}: {summary}"`. In the `finally`, compose `scrape_run["errors"]` from `errors + consistency_notes` (joined with `"\n"`, `None` when both empty) so the note is queryable, while `scrape_run["status"]` stays driven ONLY by the fatal `errors` list (an inconsistent-but-otherwise-successful run is still `success`).

**Checkpoint**: US2 adds the operator-facing log + run-record trail on top of US1.

## Phase 5: User Story 3 — No false alarms on legitimate rounding (Priority: P2)

**Goal**: Sub-tolerance differences never fire; the tolerance is the reused reconciliation band.

**Independent test**: Unit cases with sub-tolerance subcategory and demonstrativo differences produce zero discrepancies; the local-D1 cross-check (PR phase) reports no false alarms on historically-good periods.

- [X] T012 [US3] Confirm (in code review of `detect_inconsistencies`) that every comparison goes through `within_tolerance` and that rounding to 2 decimals on sums does not itself introduce a > tolerance artifact; add a brief comment documenting the band. (No new logic — this story is satisfied by US1's tolerance reuse; this task guards against a future regression.)

**Checkpoint**: US3 is satisfied by the shared tolerance; the guard task makes that explicit.

## Phase 6: Tests & Polish

- [X] T013 [P] Create `scripts/tests/test_scrape_consistency.py` (stdlib `unittest`, mirrors `test_reconcile.py`) covering: (a) fully consistent period → no discrepancies, `sql` is the lone DELETE, `alert is None`; (b) dropped-entry subcategory mismatch → one `subcategory` discrepancy + INSERT, `affected_entry_ids` populated; (c) demonstrativo C and D mismatches → `demonstrativo` discrepancies; (d) sub-tolerance rounding (abs and relative) → no discrepancies; (e) one-sided key (entries present, subtotal absent → reported 0) → discrepancy; (f) resolution graft (prior resolved/notes carried onto re-emitted alert; default kept when no prior); (g) C/D within the same subcategory never net against each other.
- [X] T014 Run `python -m unittest discover -s scripts/tests -t scripts` and fix any failures.
- [X] T015 Update `CLAUDE.md` "Important Patterns" with a concise bullet for the scrape-time consistency check (mirrors the `reconcile.py` bullet): the `scrape_inconsistency` `warning` alert, the pure `consistency.py` module, the success-path gating, idempotent per-period id + atomic writeback + resolution graft, the `scrape_runs.errors` note, and the no-mirror-write / no-migration / no-analysis-import invariants.
- [X] T016 Run `pnpm lint` and `pnpm format` (quality gate); ensure the Python change is consistent with the repo's style. (TS unaffected.)

## Dependencies & order

- T001 → T002 (foundational module skeleton) → US1 (T003–T009) → US2 (T010–T011) → US3 (T012) → Tests/Polish (T013–T016).
- T003 is parallelizable [P] with nothing else pending in its file; T013 [P] can be drafted alongside US1 once the function signatures from T002 exist but must be run (T014) after US1 lands.
- US2 and US3 both build on US1's `_check_consistency`/`detect_inconsistencies`; do them after US1.

## Implementation strategy

MVP = Phase 1–3 (US1): detection + idempotent alert. US2/US3 are thin add-ons (logging/run-record + tolerance guard) on the same module. Tests + the CLAUDE.md note + lint/format close out.
