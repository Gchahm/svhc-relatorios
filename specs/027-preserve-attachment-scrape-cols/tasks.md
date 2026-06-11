# Tasks: Preserve scraper-owned attachment columns across re-scrapes

**Feature**: `027-preserve-attachment-scrape-cols` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

All paths are absolute from the repo root `/home/agent/workspace/svhc-relatorios`.

## Phase 1: Setup

- [X] T001 Confirm baseline: run `python -m unittest discover -s scripts/tests -t scripts` from the repo root and confirm the existing suite passes before any change (establishes a clean starting point).

## Phase 2: Foundational (the shared merge seam — blocks all user stories)

- [X] T002 Add the pure helper `_preserve_existing_attachment_cols(attachments_out: list[dict], existing_by_id: dict[str, dict]) -> None` to `scripts/scraper/runner.py`, implementing the contract in `specs/027-preserve-attachment-scrape-cols/contracts/preserve-helper.md`: for each row, for each of `("file_path", "content_hash")`, if the row's value is falsy AND `existing_by_id[row["id"]]` has a non-falsy value, copy it onto the row; never touch `id`/`entry_id`/`external_document_id`; decide each column independently; no-op for ids absent from `existing_by_id`.

## Phase 3: User Story 1 — Refresh a period without re-downloading images (P1) 🎯 MVP

**Goal**: A re-scrape that omits (or fails) image download preserves existing `file_path`/`content_hash`.

**Independent test**: Seed an attachment with non-NULL values, build a fresh row with NULLs for the same id, run the merge, assert the values survive.

- [X] T003 [US1] In `scripts/scraper/runner.py:_scrape_periodo`, before the upsert (the `return _build_period_data(...)` is consumed by `run_scrape`'s `d1.upsert_tables` — so do the read+merge inside `_scrape_periodo` and bake the merged rows into the returned `attachments_out`): read the existing column map for the period via `d1.query("SELECT d.id, d.file_path, d.content_hash FROM attachments d JOIN entries e ON d.entry_id = e.id JOIN accountability_reports r ON e.report_id = r.id WHERE r.period = '<escaped periodo>'", target=target)`, build `existing_by_id = {row["id"]: row for row in ...}`, and call `_preserve_existing_attachment_cols(attachments_out, existing_by_id)`.
- [X] T004 [P] [US1] Add `scripts/tests/test_attachment_preserve.py` (stdlib `unittest`, module-docstring + run hint like sibling `test_attachment_state.py`) covering: (a) re-scrape no-download preserves both columns (FR-001/002, SC-001), (b) per-id partial — one id preserved, one accepts a fresh value (FR-004), (c) prior-NULL + fresh-NULL stays NULL, (d) `id`/`entry_id`/`external_document_id` never mutated (FR-006).

## Phase 4: User Story 2 — Re-download supplies fresh values (P2)

**Goal**: A successful in-run download overwrites the prior values.

**Independent test**: Seed old values, build a fresh row with NEW non-NULL values for the same id, run the merge, assert the new values win.

- [X] T005 [P] [US2] Extend `scripts/tests/test_attachment_preserve.py` with: a fresh non-NULL `file_path`/`content_hash` for an id that also has different existing values → the fresh value wins (FR-003, SC-002).

## Phase 5: User Story 3 — First scrape unaffected (P3)

**Goal**: No pre-existing row ⇒ behavior identical to today.

**Independent test**: Empty `existing_by_id` ⇒ rows pass through unchanged.

- [X] T006 [P] [US3] Extend `scripts/tests/test_attachment_preserve.py` with: empty `existing_by_id` leaves NULL fresh values NULL and populated fresh values populated (FR-007, SC-004); a new id not in the map is unaffected (edge case).

## Phase 6: Polish & Cross-Cutting

- [X] T007 Run `python -m unittest discover -s scripts/tests -t scripts` — full suite (including `test_attachment_state.py` as the SC-003 regression guard) must pass.
- [X] T008 Run `pnpm lint` and `pnpm format` from the repo root (constitution Quality Gates) and commit any formatting changes; confirm no Python or TS lint regressions.
- [X] T009 Manual verification against local D1 per `specs/027-preserve-attachment-scrape-cols/quickstart.md`: confirm a seeded attachment's `file_path`/`content_hash` survive a simulated re-scrape merge+upsert and that `attachment_state` is unchanged; record the result for the PR body (SC-001, SC-003).

## Dependencies

- T001 (setup) → T002 (helper) → T003 (wire-up) is the critical path.
- T004/T005/T006 (tests) depend only on T002 (the helper exists) and are mutually parallel `[P]` (same file but additive sections; if done by one agent, append sequentially).
- T007/T008/T009 (polish) depend on T002–T006.

## Implementation Strategy

- **MVP = Phase 1–3 (T001–T004)**: the helper + wire-up + US1 tests already deliver the critical bug fix (the no-download re-scrape no longer clobbers).
- US2/US3 are guard-rail increments proving the helper does not over-reach (fresh values still win; first scrape unchanged).
