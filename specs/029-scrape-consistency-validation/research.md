# Phase 0 Research: Scrape-time consistency validation

All spec clarifications were resolved as documented defaults (see spec `## Clarifications` + `## Assumptions`); no open NEEDS CLARIFICATION remained. The research below records the concrete technical decisions and the existing patterns reused.

## Decision 1: Persist as a `scrape_inconsistency` alert (no new table)

- **Decision**: Record the finding in the existing `alerts` table as a new `type = "scrape_inconsistency"`, `severity = "warning"`, period-scoped, with a stable per-period deterministic id.
- **Rationale**: The `alerts` table + `/api/alerts` + `/dashboard/alerts` already exist and render any alert type generically (title/description/severity/metadata, with `metadata.entry_ids` driving feature-018 deep links — no per-type UI switch). A "ledger that doesn't add up" is exactly an alert-shaped integrity signal. Adding a dedicated table would mean a Drizzle migration, a new API route, and new UI for no extra value.
- **Alternatives considered**: (a) New `scrape_consistency_checks` table — rejected: migration + API + UI churn, violates Simplicity. (b) Only the `scrape_runs.errors` text — rejected: not dashboard-visible, not deep-linkable, not per-period queryable. We do BOTH: the alert (durable, dashboard) AND the `errors` note (per-run operator trail), per FR-006.

## Decision 2: Reuse the reconciliation tolerance (~5% rel OR ~R$0.05 abs)

- **Decision**: Treat two amounts as consistent when `abs(diff) <= 0.05` OR (`reference > 0` and `abs(diff)/reference < 0.05`). Mirror `scripts/analysis/nf_groups.py:within_tolerance` (`AMOUNT_ABS_TOL = 0.05`, `AMOUNT_REL_TOL = 0.05`).
- **Rationale**: The spec mandates one meaning of "consistent" across the system. This band already keeps small (rounding-dominated) and large (percentage-dominated) totals sane for the NF reconciliation, so it generalizes cleanly to subtotal/demonstrativo sums.
- **Subsystem-decoupling note**: The scraper MUST NOT import the analysis package (`scripts/analysis/*`) — the two subsystems share only `scripts/common`. So `consistency.py` defines its own `AMOUNT_REL_TOL`/`AMOUNT_ABS_TOL` constants (same values) with a comment that they mirror `nf_groups.within_tolerance`. This is consistent with how `nf_groups.py` itself documents mirroring values from `attachments.py`. The values are not a candidate for `scripts/common` because `common` is deliberately minimal (only `det_id`/`now_ms`/hashing) and pulling a numeric policy constant in would couple the two subsystems' tolerance evolution.

## Decision 3: Comparison granularity

- **Decision**: Two cross-checks per period:
  1. **Subcategory-level**: group entries by `(subcategory_id, movement_type)` and sum `amount`; group `category_subtotals` by the same key (the subtotal row already carries `subcategory_id` + `movement_type` + `amount`); compare each key's entry-sum vs. subtotal. A key present on only one side compares the present value against `0` (catches a dropped row / a phantom subtotal).
  2. **Demonstrativo-level**: sum the `category_subtotals` amounts grouped by `movement_type` — `C` sum vs `total_receitas`, `D` sum vs `total_despesas`.
- **Rationale**: The portal consolidates subtotals per `(subcategory, movement_type)` (see `runner.py:_consolidate_subtotais`), so the entry-sum must use the same key — netting C and D within a subcategory would hide a sign-flip regression. The demonstrativo headline figures are revenue/expense totals, which map to C/D; subtotals are the natural intermediate granularity to roll up. Comparing subtotals→demonstrativo (rather than entries→demonstrativo directly) localizes a failure to one of the two layers, which is more diagnostic.
- **Alternatives considered**: Compare entries directly against the demonstrativo (skip subtotals) — rejected: loses the ability to say *which* layer broke. Comparing the saldo/balance figures — rejected: they carry prior-period state not present in this period's entries (documented assumption).

## Decision 4: Where the check runs + idempotency + atomicity

- **Decision**: Call the check inside the per-period success branch in `run_scrape` (right after `_reconcile_period(...)` returns), where the in-memory `period_data` and the demonstrativo are available, before `scraped_count += 1`. The impure glue function in `runner.py` (a) reads the prior alert's `{resolved, resolved_at, notes}` for the stable id (mirrors `_reconcile_period`), (b) calls the pure `build_consistency_writeback(...)` which returns the one-batch SQL (`DELETE FROM alerts WHERE id = <id>` always, then `INSERT OR REPLACE` only when inconsistent) + the discrepancy list, (c) runs one `d1.execute_sql`, (d) on inconsistency logs `logger.warning(...)` and appends a one-line summary to the run's `errors` accumulator.
- **Rationale**: This is the exact gating + atomicity + resolution-graft pattern `reconcile.py`/`_reconcile_period` already use (feature 024/023/028). Running only on the success path satisfies FR-007 (a failed/empty period never falsely fires). A stable deterministic id (`det_id("alert", period, "scrape_inconsistency")`) makes re-scrapes idempotent (FR-005) and the always-issued DELETE clears a now-consistent period's stale alert.
- **`scrape_runs.errors` note**: The current code accumulates `errors` only on the *failure* path (`errors.append(f"Error scraping {label}: ...")`) and writes `scrape_run["errors"]` in the `finally`. A consistency mismatch is not a fatal scrape error, so it is appended to the same `errors` list (as a distinct `"Consistency mismatch in <period>: ..."` line) — it surfaces in the run record's `errors` field without flipping the run `status` to `error` (the existing status is set by `errors` being non-empty, so to avoid wrongly marking a successful-but-inconsistent run as failed, the consistency note is tracked in a SEPARATE accumulator that is merged into `scrape_run["errors"]` for queryability but does NOT drive `status`). See data-model for the exact handling.

## Decision 5: Metadata / deep-link shape

- **Decision**: `metadata` JSON carries `entry_ids` (sorted union of the ids of entries belonging to any subcategory that failed its subcategory-level check — empty list if only the demonstrativo-level check failed), plus `checks` (the structured discrepancy list: each `{level, subcategory_id?, movement_type, computed_sum, reported_total, difference}`), and `counts`.
- **Rationale**: `entry_ids` is the established feature-018 deep-link key the alerts UI reads; `checks` is the auditable evidence. Mirrors the `portal_row_vanished` metadata shape.
