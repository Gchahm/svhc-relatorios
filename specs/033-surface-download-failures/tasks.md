# Tasks: Surface partial attachment-download failures

**Feature**: 033-surface-download-failures | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests ARE included: the spec's Independent Tests + plan call for stdlib `unittest` coverage of the
pure helpers and the analysis check. Run: `python -m unittest discover -s scripts/tests -t scripts`.

## Phase 1: Setup

- [x] T001 Confirm the Python test harness runs green on the current branch before changes:
  `cd scripts && python -m unittest discover -s tests -t scripts` (baseline).

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Create the pure, stdlib-only helper module `scripts/scraper/download_failures.py`
  implementing `failed_attachment_ids(attachments_out, attempted_ids) -> list[str]`,
  `format_failure_note(period, failed_ids) -> str | None`, and
  `resolve_status(has_fatal_errors, any_download_failed) -> str`, per `contracts/contracts.md` C1
  (importable without `playwright`; mirror the `preserve.py`/`consistency.py` style + module
  docstring referencing IMP-004 / issue #41).

## Phase 3: User Story 1 — Operator sees a partial run and knows to re-fetch (Priority: P1)

**Goal**: A download-enabled run that has any failed attachment download reports `partial` status,
records the count + ids on `scrape_runs.errors`, and logs a final per-period summary; a clean or
download-disabled run is unchanged.

**Independent Test**: Run a scrape where ≥1 attachment fails to download; verify the run record's
status is `partial` and its `errors` names the count + failed ids; verify a clean download run stays
`success` with no failure note.

- [x] T003 [P] [US1] Add `scripts/tests/test_download_failures.py` covering the pure helpers:
  `failed_attachment_ids` (attempted + falsy file_path counted; preserved-pages NOT counted;
  not-attempted NOT counted; empty-string file_path counted as missing; input order preserved),
  `format_failure_note` (None on empty, formatted line otherwise), and `resolve_status` (the three
  precedence cases).
- [x] T004 [US1] In `scripts/scraper/runner.py` `_scrape_periodo`, collect the set of attachment ids
  a download was attempted for this run (from `doc_download_tasks` when `download_docs` is true) and,
  after the existing `preserve_existing_attachment_cols` merge, compute the period's failed ids via
  `download_failures.failed_attachment_ids(...)`; attach them to the returned `period_data` under a
  non-table key (e.g. `_download_failed_ids`) so the upsert/reconcile id sets never see it (mirror
  the `_parse_notes` convention: pop it in `run_scrape` before upsert).
- [x] T005 [US1] In `scripts/scraper/runner.py` `run_scrape`, pop `_download_failed_ids` from each
  `period_data` (before `upsert_tables`), accumulate a per-period `format_failure_note(...)` line
  into a `download_failure_notes` accumulator and a global `any_download_failed` flag, append those
  notes to the run's notes channel (alongside `errors`/`consistency_notes`), emit a final run-log
  summary naming affected periods + per-period counts when any failed, and in the `finally` set
  `scrape_run["status"]` via `download_failures.resolve_status(bool(errors), any_download_failed)`
  (fatal error still dominates).
- [x] T006 [US1] Update the `scrape_runs.status` comment in `src/db/fiscal.schema.ts` to include
  `partial` (documentation only — no schema/migration change; the column already allows it).

**Checkpoint**: US1 is independently complete — run status + queryable note + run-log summary work.

## Phase 4: User Story 2 — Auditor sees an alert for unfetchable attachments (Priority: P2)

**Goal**: Every attachment whose mirror row has a falsy `file_path` produces exactly one idempotent
`attachment_not_downloaded` (`warning`) alert, deep-linkable to its entry, that self-clears once
pages are fetched.

**Independent Test**: With a period that has a `file_path IS NULL` attachment, run `analyze`; verify
one alert of that type; re-run → no duplicate; set `file_path` → re-run → alert gone.

- [x] T007 [P] [US2] Add `scripts/tests/test_attachment_not_downloaded.py` covering
  `check_attachment_not_downloaded`: one alert per falsy-`file_path` attachment, none for present
  `file_path` (and none for empty-string treated as missing — assert it IS flagged), deterministic
  idempotent id (`det_id("alert", period, "attachment_not_downloaded", attachment_id)`), and metadata
  carrying `attachment_id`/`entry_id`/`external_document_id`.
- [x] T008 [US2] In `scripts/analysis/checks/attachments.py`, add
  `check_attachment_not_downloaded(period: PeriodData) -> list[Alert]` per `contracts/contracts.md`
  C3 (type `attachment_not_downloaded`, severity `warning`, deterministic id, PT-BR title/description,
  metadata `{attachment_id, entry_id, external_document_id}`); a `file_path` is "missing" when falsy
  (NULL or empty string).
- [x] T009 [US2] Wire the new check into `scripts/analysis/checks/advanced.py` `run_advanced`
  (`alerts.extend(check_attachment_not_downloaded(period))`) so it rides the existing per-period
  delete-then-insert writeback in `run_analysis` (idempotent + self-clearing, no new writeback code).

**Checkpoint**: US2 is independently complete — the alert appears, idempotent, self-clearing,
deep-linkable on the existing dashboard.

## Phase 5: User Story 3 — Recovery closes the loop (Priority: P3)

**Goal**: Document/verify that the existing `download-docs` backfill clears both signals on success;
no new code.

- [x] T010 [US3] Verify (no code) that after fetching an attachment's pages (existing
  `run_download_docs` backfill sets `file_path`), a subsequent `analyze` drops its
  `attachment_not_downloaded` alert and a subsequent download-enabled scrape no longer counts it as
  failed — capture the verification steps/results for the PR body per `quickstart.md`.

## Phase 6: Polish & Cross-Cutting

- [x] T011 Run the full Python test suite green:
  `cd scripts && python -m unittest discover -s tests -t scripts`.
- [x] T012 Run `pnpm lint` and `pnpm format` (TS docs-only change in T006 must stay clean); confirm
  no unintended formatting churn.
- [x] T013 Verify end-to-end against local D1 per `quickstart.md` (alert appears/idempotent/clears;
  status precedence is unit-covered) and record the evidence for the PR body.

## Dependencies & Execution Order

- T001 (baseline) → T002 (foundational helper) blocks US1 (T004/T005 import it).
- **US1 (T003–T006)** depends on T002. T003 is parallel-safe (new test file). T004 → T005 are
  sequential (same file, T005 consumes T004's `_download_failed_ids`). T006 is independent docs.
- **US2 (T007–T009)** is independent of US1 (different files: analysis side). T007 parallel-safe;
  T008 → T009 sequential (T009 imports T008's function).
- **US3 (T010)** depends on US2 existing (verification only).
- Polish (T011–T013) last.

## Parallel Opportunities

- T003 and T007 (the two new test files) can be written in parallel.
- US1 (scraper) and US2 (analysis) touch disjoint files and can proceed in parallel once T002 lands.

## Implementation Strategy

MVP = US1 (the operability signal — the core of IMP-004). US2 adds the auditor-facing alert; US3 is
verification only. Deliver US1 then US2; both ship together in this PR.
