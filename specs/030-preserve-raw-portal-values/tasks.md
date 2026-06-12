# Tasks: Preserve Raw Portal Values on Mirror Rows

**Feature**: `030-preserve-raw-portal-values` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are included for the pure parser logic because the spec (US2) explicitly requires
fail-the-row-not-the-period behavior to be verifiable.

## Phase 1: Setup

- [x] T001 Confirm working tree on branch `030-preserve-raw-portal-values`; note next migration number
  is `0013` (latest is `drizzle/0012_clever_sir_ram.sql`).

## Phase 2: Foundational (schema + migration — blocks the scraper write)

- [x] T002 Add two nullable columns to the `entries` table block in `src/db/fiscal.schema.ts`:
  `rawAmount: text("raw_amount")` and `rawDescription: text("raw_description")` (with brief provenance
  comments). Do not add indexes/FKs. Keep all existing columns unchanged.
- [x] T003 Generate the Drizzle migration via `node_modules/.bin/drizzle-kit generate` (the
  `pnpm db:generate` workaround per MEMORY). Verify it produces `drizzle/0013_*.sql` with two
  `ALTER TABLE \`entries\` ADD COLUMN ...` statements and updates `drizzle/meta/`. Commit the snapshot.
- [x] T004 Apply the migration locally: `pnpm db:migrate:dev` (or
  `node_modules/.bin/wrangler d1 migrations apply fiscal-db --local`). Confirm the columns exist via a
  `wrangler d1 execute ... PRAGMA table_info(entries)`.

## Phase 3: User Story 2 — Harden parse_brl, fail the row not the period (Priority: P1)

**Goal**: A malformed amount cell fails its row (warn + skip + non-fatal note), never the period.
NaN/inf rejected. (FR-004, FR-005, FR-006; SC-002, SC-004)

**Independent Test**: Unit tests over the tolerant parser; manual: a row with an unparseable amount is
skipped and the period still completes with a run note.

- [x] T005 [P] [US2] Make `parse_brl` tolerant in `scripts/scraper/extractors/demonstrativo.py`:
  signature `parse_brl(text: str) -> float | None`; wrap cleaning + `float()` in try/except; reject
  empty/whitespace and non-finite (`math.isfinite`) → return `None`; keep it a pure function (no
  logging/I/O). Add `import math`.
- [x] T006 [P] [US2] Add `scripts/tests/test_parse_brl.py` (stdlib `unittest`): valid BRL strings →
  expected floats; empty/whitespace/junk → `None`; NaN/inf-source strings → `None`; zero and large
  values exact. Run `python -m unittest discover -s scripts/tests -t scripts`.
- [x] T007 [US2] In `extract_demonstrativo` (`extractors/demonstrativo.py`), treat a `None` parse of a
  summary value as fatal: raise a clear `RuntimeError` naming the title + offending raw text (the 5
  summary values are required — preserves today's abort semantics for a broken summary).
- [x] T008 [US2] In `extract_lancamentos_from_tab` (`scripts/scraper/extractors/lancamentos.py`): for
  subtotal rows, parse with the tolerant `parse_brl`; if `None`, `logger.warning` quoting the raw text
  and **skip** the subtotal (do not append). For entry rows, keep the raw amount text and the
  (possibly-`None`) parse on the lancamento dict (`"valor_raw": valor_text`, `"valor": parse_brl(...)`)
  — do NOT skip here; the runner decides (so it can record the note + raw description).
- [x] T009 [US2] In `_scrape_periodo` (`scripts/scraper/runner.py`) entry-build loop (~L538-586):
  collect a per-period `parse_notes: list[str]`. When `lanc["valor"] is None`, append a note
  (period + quoted `valor_raw` + truncated description) via `logger.warning` + the list, then `continue`
  (skip the entry AND its attachment build). Return the notes alongside the period data (e.g. attach to
  the returned dict under a non-table key `_parse_notes`, ignored by `upsert_tables`).
- [x] T010 [US2] In `run_scrape` (`scripts/scraper/runner.py`), after a successful
  `_scrape_periodo`/upsert, extend `consistency_notes` with `period_data.pop("_parse_notes", [])` so
  the skips surface on `scrape_run.errors` without flipping `status` to `error` (IMP-002 channel).
  Ensure `_parse_notes` is removed before `upsert_tables`/`_reconcile_period` see the dict (or is a key
  those functions ignore — `upsert_tables` iterates `TABLE_ORDER`, so it is ignored; still pop it to be
  safe and avoid it leaking into reconciliation id sets).

## Phase 4: User Story 1 — Persist raw provenance on entry rows (Priority: P1)

**Goal**: Every stored entry carries `raw_amount` and `raw_description` verbatim. (FR-001, FR-002,
FR-003, FR-007, FR-008, FR-009; SC-001, SC-003)

**Independent Test**: Re-scrape a period; query D1 and confirm each row has non-null `raw_amount`
(whose parse equals `amount`) and non-null `raw_description`.

- [x] T011 [US1] Capture the raw description in `extractors/lancamentos.py`: on the entry-row dict add
  `"descricao_raw": descricao` (the `.strip()`-ed cell text, before any normalization). (`descricao`
  is already the pre-normalization cell text at extraction time.)
- [x] T012 [US1] Guard the normalize loop in `_scrape_periodo` (`runner.py` ~L505-508) so it does NOT
  clobber the raw value: normalization continues to overwrite `lanc["descricao"]`, but the raw is read
  from `lanc["descricao_raw"]` (set in T011) — confirm the loop never overwrites `descricao_raw`.
- [x] T013 [US1] In the entry-row build (`runner.py` ~L556-570) add the two scraper-owned columns to
  the entry dict: `"raw_amount": lanc.get("valor_raw")` and `"raw_description": lanc.get("descricao_raw")`.
  Keep `amount`/`description` derivation unchanged (FR-009). `upsert_sql` picks up the new keys
  automatically once the columns exist (T002-T004).
- [x] T014 [US1] Sanity-check that the analysis pipeline and reconciliation are untouched: grep that no
  `scripts/analysis/**` code writes `raw_amount`/`raw_description`, and that `scripts/scraper/preserve.py`
  / `reconcile.py` do not reference them (mirror invariant — FR-003).

## Phase 5: Polish & Verification

- [x] T015 Run `pnpm lint` and `pnpm format` (constitution III); fix any findings.
- [x] T016 Run `python -m unittest discover -s scripts/tests -t scripts` — all green.
- [x] T017 End-to-end local verify against prod-like local D1: apply migration, query a sample of
  `entries` rows confirming `raw_amount`/`raw_description` populated for re-scraped rows (or, if a live
  re-scrape is not feasible in the sandbox, write a sample row through the same code path / inspect the
  generated INSERT SQL to confirm the columns are included). Record findings for the PR body
  (SC-001/SC-003). Use the `verify` / `ui-login` skills as applicable.
- [x] T018 Update `CLAUDE.md` Important Patterns with a one-line note on the new scraper-owned
  `entries.raw_amount`/`raw_description` provenance columns and the fail-the-row parser policy
  (feature 030 / issue #38), consistent with the existing feature notes.

## Dependencies & Execution Order

- **Phase 2 (T002-T004)** blocks Phase 4 (the columns must exist before the scraper writes them).
  Phase 3 (parser hardening) is independent of the schema and can land first.
- Within Phase 3: T005 before T006/T007/T008/T009/T010 (they use the new signature). T009 before T010.
- Within Phase 4: T011 before T012/T013.
- **MVP**: Phase 3 (US2, robustness) is independently shippable. US1 (Phase 4) needs Phase 2.

## Parallel Opportunities

- T005 and T006 are `[P]` (parser change + its tests, different files — write the test against the
  target contract).
- Documentation/verify tasks (T017, T018) can proceed once code is in place.
