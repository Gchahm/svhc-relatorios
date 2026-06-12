# Tasks: Deterministic Entry IDs for Duplicate Natural Keys

**Feature**: `034-deterministic-entry-id` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are requested by the spec (SC-005), so test tasks are included.

## Phase 1: Setup

- [X] T001 Confirm the scraper test harness runs: `python -m unittest discover -s scripts/tests -t scripts` (baseline green) from repo root.

## Phase 2: Foundational (blocking prerequisites)

- [X] T002 Create the pure module skeleton `scripts/scraper/entry_ids.py` (stdlib-only, `from __future__ import annotations`, import `det_id` from `common`): define dataclasses `EntryKeyInput(date_str, description, amount, subcategory_id, documento_ids)`, `AssignedEntryId(entry_id, discriminator, used_fallback)`, `AssignResult(assigned, fallback_notes)`, and a module docstring mirroring `reconcile.py`/`consistency.py` (PURE, no I/O, playwright-free).

## Phase 3: User Story 1 — Stable ids for distinct-doc duplicates (P1)

**Goal**: Duplicate natural keys with distinct portal doc ids get order-independent ids; singletons keep their legacy id.

**Independent test**: Assign ids for distinct-doc duplicate rows in two orders → per-doc id equal; a singleton's id equals `det_id(...,'1')`.

- [X] T003 [US1] Implement `entry_discriminator(documento_ids) -> str | None` in `scripts/scraper/entry_ids.py` per `contracts/entry_ids.md` (sorted+deduped `"doc:<ids>"`, `None` when empty).
- [X] T004 [US1] Implement `assign_entry_ids(period, rows) -> AssignResult` in `scripts/scraper/entry_ids.py`: group by natural key; singleton → discriminator `"1"`; duplicate group → bucket by sorted-deduped doc set, distinct doc set → `"doc:<ids>"`, shared/empty doc set → `base + "#<n>"` (n stable within bucket) with `used_fallback=True` and one fallback note per group; build each id via `det_id("entry", period, date, desc, str(amount), subcat, discriminator)`; preserve input order in `assigned`. (FR-001..FR-005, FR-007)
- [X] T005 [P] [US1] Add `scripts/tests/test_entry_ids.py` with tests for US1: (a) distinct-doc duplicates produce identical per-doc ids when the input is reversed (order-independence, SC-001/SC-005); (b) a singleton's id is byte-equal to the legacy `det_id("entry", period, date, desc, str(amount), subcat, "1")` (no churn, SC-002); (c) `entry_discriminator` order-independence/dedup.
- [X] T006 [US1] Wire `assign_entry_ids` into `scripts/scraper/runner.py` `_scrape_periodo`: build `EntryKeyInput`s in the lancamento loop (after subcategory/date resolution, using `documento_ids`), call `assign_entry_ids` once, and zip the resulting `entry_id` back onto each entry/attachment row — removing the inline `entry_key_counts`/`natural_key`/`_entry_id(...)` occurrence-index logic. Keep `_attachment_id(entry_id, ext)` unchanged. (FR-001, FR-008)

## Phase 4: User Story 2 — Fallback cases logged (P2)

**Goal**: No-doc / shared-doc duplicate groups record an enumerable fallback note; doc-distinguished groups do not.

**Independent test**: A no-doc duplicate group yields one fallback note (period + natural key + count); a distinct-doc group yields none.

- [X] T007 [US2] In `scripts/scraper/runner.py` `_scrape_periodo`, collect `AssignResult.fallback_notes` and surface them through the existing non-fatal notes channel (append to the `parse_notes`/`_parse_notes` list so they flow into `consistency_notes` via `run_scrape`), with a `logger.warning` per note. (FR-005)
- [X] T008 [P] [US2] Extend `scripts/tests/test_entry_ids.py`: assert a no-doc duplicate group sets `used_fallback=True` and emits exactly one note naming period/natural key/count (SC-003); a distinct-doc duplicate group emits zero notes; a shared-single-doc duplicate group (real split) falls back with a note and stays unique within the group (edge case + FR-007).

## Phase 5: User Story 3 — Drift detection on re-scrape (P3)

**Goal**: A re-scrape that moves a natural key's id surfaces a per-period drift note; a faithful re-scrape surfaces none.

**Independent test**: With seeded existing rows, a moved id yields one drift note; reproduced ids yield none; empty existing yields none.

- [X] T009 [US3] Implement `detect_id_drift(period, scraped, existing) -> list[str]` in `scripts/scraper/entry_ids.py` per `contracts/entry_ids.md` (a scraped id absent from the existing id set whose natural key already existed under a different id → one note; empty `existing` → `[]`). (FR-006)
- [X] T010 [US3] In `scripts/scraper/runner.py` `run_scrape` success path, BEFORE `upsert_tables`, read the period's existing entries (`SELECT e.id, e.date, e.description, e.amount, e.subcategory_id FROM entries e JOIN accountability_reports r ON e.report_id = r.id WHERE r.period = ...`, mirroring `_reconcile_period`'s read), call `detect_id_drift` against the freshly-built entry rows, and append any notes to `consistency_notes` with a `logger.warning`. Read-only — no mirror write. (FR-006, FR-008)
- [X] T011 [P] [US3] Extend `scripts/tests/test_entry_ids.py`: drift detected when an id moves for an existing natural key (SC-004); no drift when ids reproduced; no drift on empty `existing` (first scrape).

## Phase 6: Polish & Cross-Cutting

- [X] T012 Run `python -m unittest discover -s scripts/tests -t scripts` — all tests green.
- [X] T013 Run `pnpm lint` and `pnpm format` (Constitution III gate); confirm no unintended diff.
- [X] T014 Update `CLAUDE.md` "Important Patterns" with a one-paragraph note on the entry-id derivation (portal-native discriminator + occurrence fallback + drift note), in the style of the feature 026–030 notes; cite issue #40 / IMP-003 and `scripts/scraper/entry_ids.py`.
- [X] T015 Verify against local data per `quickstart.md` (the ENERGIA ELÉTRICA 2026-01 group), and per the speckit pr phase verify in the running app (entries still load + deep-link works) before opening the PR.

## Dependencies & order

- T001 → T002 → (US1: T003 → T004 → T005/T006) → (US2: T007/T008) → (US3: T009 → T010/T011) → Polish.
- `assign_entry_ids` (T004) blocks the runner wiring (T006) and the US2 fallback wiring (T007).
- `detect_id_drift` (T009) blocks its runner wiring (T010).
- `[P]` test tasks (T005, T008, T011) touch only `scripts/tests/test_entry_ids.py` and can be written alongside their story's implementation.

## Implementation strategy

MVP = Phase 1–3 (US1): the core order-independence fix + no-churn guarantee, independently
testable. US2 (logging) and US3 (drift detection) are additive monitoring layers that build on the
same pure module.
