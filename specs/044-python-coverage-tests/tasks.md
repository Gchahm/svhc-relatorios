# Tasks: Python coverage measurement + analysis-core unit tests

**Feature**: `044-python-coverage-tests` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

All test files live under `scripts/tests/`; the runner is `pnpm test:py`
(`unittest discover -s tests -t .` from `scripts/`). `[P]` = parallelizable (independent file).

This feature *is* the tests, so there is no separate "tests vs implementation" split — each user
story's tasks ARE its tests plus the coverage plumbing.

## Phase 1: Setup

- [x] T001 Confirm baseline: from `scripts/`, run
  `uv run --with coverage python -m coverage run --source=analysis,scraper --omit='scraper/extractors/*,scraper/browser.py,scraper/runner.py,scraper/config.py,analysis/__main__.py,scraper/__main__.py,tests/*' -m unittest discover -s tests -t . && uv run --with coverage python -m coverage report`.
  Record the TOTAL % (baseline = 39%).

## Phase 2: Foundational (none)

No blocking prerequisites — tests are independent; coverage config (US2) only needs US1's tests to
set a meaningful floor, captured in dependency order below.

## Phase 3: User Story 1 — analysis-core tests (Priority: P1) 🎯 MVP

**Goal**: stdlib-`unittest` tests for the risk-prioritized modules; suite passes with no
wrangler/D1/network/playwright.

**Independent test**: `pnpm test:py` passes with the new files; per-module coverage of the
prioritized modules ≥ 80% (SC-001).

- [x] T010 [P] `scripts/tests/test_mismatches.py` — `detect_attachment_mismatches`: one mismatch per
  failing flag (`amount_match==0`/`vendor_match==0`/`date_match==0`); page-error short-circuits field
  checks; ledger/extracted values populated; entry/vendor resolution via `RefIndex`; missing
  entry/attachment → `entry_id=None`.
- [x] T011 [P] `scripts/tests/test_nf_groups.py` — `within_tolerance` boundaries (≤R$0.05 abs, <5%
  rel, reference≤0); `reconcile_group` (None when total None/≤0, reconciled, over_claim, under_claim);
  `group_attachments` (same `content_hash` merges, missing-hash → singleton `doc:<id>` key).
- [x] T012 [P] `scripts/tests/test_attachments_rollup.py` — `build_attachment_analysis` with an
  injected fake provider: invoice-only gross/net, payment-proof paid precedence, boleto, multi-invoice
  sum, all-pages-fail → error, no-paths → error; `_map_artifact_role` (aliases + payment-proof
  override); `_parse_brl_value`; `_page_label_from_path`; `_check_date_in_period` (period + prev
  month, Jan→Dec rollover); `_pick_attachment_date`/`_pick_payment_amount` ranking; `_fanout_result`
  reuses rep extraction + re-derives vendor/date; `_apply_group_amount_match`; `select_work`
  (pending filter, min_amount, limit, group sibling-sum); `summarize_results` (smoke, no raise).
- [x] T013 [P] `scripts/tests/test_check_attachments.py` — `check_attachment_mismatches` (one alert
  per (attachment,kind), type+severity per `_TYPE_BY_KIND`, deterministic id, metadata incl. detail
  for page-error); `check_attachment_not_downloaded` (alert iff falsy `file_path`, metadata fields).
- [x] T014 [P] `scripts/tests/test_check_advanced.py` — `check_vendor_concentration` (>30% fires,
  ≤30% / total≤0 silent); `check_category_growth` (<6 prior periods → none; growth>2×overall & >100%
  fires); `check_seasonality` (>50% YoY, severity bands, no prior-year → none); `check_delinquency`
  (no units / no taxa subcat → none; rate bands critical/warning/info); `run_advanced` aggregates.
- [x] T015 [P] `scripts/tests/test_check_trends.py` — `check_subcategory_above_average` (<2 prior →
  none; >50% above avg fires); `check_month_over_month` (first period → none; >30% var fires);
  `check_missing_recurring_subcategory` (<3 prior → none; present-3-then-absent fires); `run_trends`.
- [x] T016 [P] `scripts/tests/test_check_consistency.py` — `check_balance_month` /
  `check_balance_accumulated` (approx-eq tolerance, mismatch fires critical); entry-sum vs reported
  expenses/revenue checks; `run_consistency` aggregates.
- [x] T017 [P] `scripts/tests/test_verdicts.py` — `mismatch_key` (per-attachment + document_overpayment
  forms); `validate_verdict` (false requires root_cause; forbidden otherwise; bad verdict/confidence);
  `validate_fix` (rejects `merged`); `upsert_verdict` latest-wins idempotent; `record_verdict`
  (tmp dir, attach fix); `load/save_verdicts_file` round-trip; `_attachment_ids_of`; `loop_state`
  with `unittest.mock.patch("analysis.verdicts.summarize_mismatches", ...)` feeding a fixed list —
  converged (all reviewed true/page-error), open set + affected ids, no-progress (flip & stagnant),
  max-iterations precedence.

**Checkpoint**: `pnpm test:py` green; prioritized modules ≥80% (verified in T030).

## Phase 4: User Story 1 (cont.) — secondary-coverage tests [P]

These lift total coverage and cover the remaining pure surfaces named in FR-005.

- [x] T020 [P] `scripts/tests/test_vendor_match.py` — `normalize_tokens`/`normalize_company_name`
  (accents, abbreviations, legal suffix + stopword drop, single-letter join); `is_payer_name`
  (denylist); `names_match` (equality, alias groups, substring ≥min-len, token-superset, payer guard,
  short-name guard); `reconcile_vendor` (None when no vendor / no non-payer name; True/False).
- [x] T021 [P] `scripts/tests/test_documents_build.py` — `normalize_number`, `normalize_cnpj`
  (14-digit gate), `document_key` (None unless both confident), `_sql_id_list` (escaping),
  `_prune_sql` (empty set → unconditional DELETE; else NOT IN), `_analysis_total` (gross pref else
  fallback).
- [x] T022 [P] `scripts/tests/test_extractions_plan.py` — `build_plan` over in-memory periods/refs
  (one envelope per period, group rep pages with `recorded` flag from `page_classifications`, members
  + is_representative); `_page_refs_for_doc` (tokens → read_path); `mark_pending` no-ids → returns 0.
- [x] T023 [P] `scripts/tests/test_images_loader.py` — `images.attachments_needing_hash_backfill`
  (page-bearing + falsy content_hash, scope filter, page-less excluded) + `_split_tokens`;
  `loader._sql_str` (escaping) + `_in_clause` (None when empty).

## Phase 5: User Story 2 — coverage config + ratchet (Priority: P2)

**Goal**: measurable coverage with a recorded floor that fails on regression.

**Independent test**: `pnpm test:py:cov` prints the table and exits non-zero below floor, zero at/above.

- [x] T030 Add `scripts/.coveragerc` (`[run] source/omit`, `[report] fail_under`). Re-measure total
  with all new tests; set `fail_under` a few points below the measured total. Confirm prioritized
  modules ≥80% (SC-001); if a module is short, extend its test file in Phase 3/4.
- [x] T031 Add `"test:py:cov"` to `package.json` scripts (additive; `"test:py"` unchanged). Run it;
  confirm exit 0 at floor and (by temporarily raising `fail_under`) exit non-zero below floor, then
  restore. Run `pnpm format` so `package.json`/`.coveragerc` are Prettier-clean.

## Phase 6: User Story 3 — CI wiring (Priority: P3)

**Goal**: coverage runs as a visible CI step.

**Independent test**: `.github/workflows/ci.yml` has a "Python coverage" step running `test:py:cov`.

- [x] T040 Add a "Python coverage" step to `.github/workflows/ci.yml` after "Python tests" running
  `pnpm test:py:cov`. (Push caveat: workflow edits need the `workflow` OAuth scope; if `git push`
  rejects the workflow file, commit it on the branch and request a manual push — see spec Assumptions.)

## Phase 7: Polish

- [x] T050 Run `pnpm test:py` and `pnpm test:py:cov` from a clean checkout; confirm green + floor met.
- [x] T051 Run `pnpm lint` and `pnpm format` (repo root); confirm no diffs left. Record the measured
  baseline % for the PR body.

## Dependencies

- T001 → all (baseline first).
- Phase 3/4 tests (T010-T023) are mutually `[P]` (distinct files), and must precede T030 (floor needs
  final coverage).
- T030 → T031 → T040 → T050/T051.

## Parallel example

T010-T023 can all be authored in parallel (independent files). Run `pnpm test:py` after each to keep
green.

## MVP

User Story 1 (T010-T017) alone delivers the core value: the alert-generating analysis core is tested.
US2/US3 add the durable ratchet + CI enforcement.
