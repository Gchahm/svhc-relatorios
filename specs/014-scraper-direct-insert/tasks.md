---
description: "Task list for 014-scraper-direct-insert"
---

# Tasks: Scraper and analysis operate directly on the database

**Input**: Design documents from `/specs/014-scraper-direct-insert/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: None requested. The repo has no test framework (constitution: tests OPTIONAL), so this plan uses **manual verification** tasks (local D1/R2 round-trips + a parity check) instead of automated test tasks.

**Organization**: Tasks are grouped by user story. US1 and US2 are both P1; US1 is the MVP. US3 (P1) re-points analysis at the new structure and is the largest slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- All Python CLIs run from `scripts/` via `uv`; `scripts/common/d1.py` invokes `npx wrangler` from the repo root.

## Path Conventions

Single repo. Work is concentrated in `scripts/` (Python). The Next.js app and `src/lib/r2.ts` are intentionally untouched (they already read D1 + R2).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding for the new direct-write path

- [X] T001 [P] Add the ephemeral analysis cache convention: append `.cache/analysis/` to `/home/agent/workspace/svhc-relatorios/.gitignore` (materialized images + per-run scratch live here, never committed).
- [X] T002 Scaffold `/home/agent/workspace/svhc-relatorios/scripts/common/d1.py` — module skeleton with the `Target` literal (`"local"|"remote"`), function stubs + docstrings for `execute_sql`, `upsert_tables`, `query`, `put_object`, `get_object` per `contracts/python-d1-r2-access.md`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared `wrangler`-backed D1/R2 access + SQL-generation layer that every user story builds on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Implement the wrangler-invocation core in `scripts/common/d1.py`: resolve `Target` → `--local`/`--remote`, run `npx wrangler …` from the repo root (locate root via git), raise on non-zero exit. Used by every other function.
- [X] T004 Port the SQL generation from `scripts/import-to-d1.mjs` into `scripts/common/d1.py`: `_escape_sql(value)` (None→NULL, int/float→str, bool→1|0, dict/list→`'<json>'`, str→`'<escaped>'`), `TABLE_ORDER`, per-row `INSERT OR REPLACE INTO "<table>" (<cols>) VALUES (<vals>)` with columns derived from the row dict, dedup by `id`, flatten `document_analyses[].analysis_records` into `document_analysis_records`, prepend `PRAGMA defer_foreign_keys = ON;`. (depends on T002)
- [X] T005 Implement `execute_sql(sql, *, target)` and `upsert_tables(data, *, target) -> dict[str,int]` in `scripts/common/d1.py` (write batched SQL to a temp file, execute once, return per-table written counts). (depends on T003, T004)
- [X] T006 [P] Implement `query(sql, *, target) -> list[dict]` in `scripts/common/d1.py` using `wrangler d1 execute DATABASE --command "<sql>" --json`, parsing the `[{"results":[…]}]` envelope. (depends on T003)
- [X] T007 [P] Implement `put_object(key, file_path, content_type, *, target)` and `get_object(key, dest_path, *, target) -> bool` in `scripts/common/d1.py` via `wrangler r2 object put/get "fiscal-documents/<key>" …` (get returns False when the key is absent). (depends on T003)
- [X] T008 Manual smoke check (no code): against local, `upsert_tables` a single throwaway row, `query` it back, `put_object`/`get_object` a small file — confirm the round-trip before building on the layer. (depends on T005, T006, T007)

**Checkpoint**: Python can read/write D1 and R2 (local + remote) through one module. User stories can begin.

---

## Phase 3: User Story 1 - Scrape a period straight into the database (Priority: P1) 🎯 MVP

**Goal**: One `scrape` command lands a period's structured ledger rows in D1 and its page images in R2 — no period JSON, no persistent image folder.

**Independent Test**: Against an empty **local** DB, run `uv run python -m scraper scrape --periodo <P> --download-docs`; confirm the ten ledger tables hold the period's rows (via `wrangler d1 execute … --command "SELECT count(*) …"`), images are in local R2, no `data/scrape/<P>.json` exists, and a second run produces identical row counts.

- [X] T009 [US1] In `scripts/scraper/runner.py` `run_scrape`, replace the `period_file.write_text(...)` JSON write with `d1.upsert_tables(period_data, target=...)`; keep `_build_period_data` and all deterministic IDs unchanged. (depends on T005)
- [X] T010 [US1] In `scripts/scraper/runner.py`, print the per-table row summary returned by `upsert_tables` after each period (FR-005).
- [X] T011 [US1] In `scripts/scraper/documentos.py`, after downloading each page, upload it to R2 via `d1.put_object("<period>/<basename>", tmp_path, content_type, target=...)` and set the document's `file_path` to the `;`-joined `<period>/<basename>` R2-key tokens (Contract A in `data-model.md`); do not leave images under `data/scrape/`. (depends on T007, T009)
- [X] T012 [US1] Confirm `run_scrape` writes only the ten ledger tables and leaves `document_analyses`/`document_analysis_records`/`alerts` untouched for the period (FR-009) — `period_data` already carries empty `document_analyses`/`alerts`; ensure `upsert_tables` skips empty lists so existing analyses are never clobbered. (depends on T009)
- [X] T013 [US1] Verify idempotency **and partial-failure heal**: (a) re-run the scrape for the same period and confirm `INSERT OR REPLACE` yields stable row counts with no duplicates (FR-006, SC-004); (b) interrupt a scrape mid-write (or simulate a failed `execute_sql`) and confirm the failure is reported, then a clean re-run restores a fully consistent period with no duplicate/orphan rows (FR-007, SC-006). (depends on T009, T011)

**Checkpoint**: A fresh `scrape --download-docs` fully populates local D1 + R2 from one command. MVP is demonstrable.

---

## Phase 4: User Story 2 - Choose local or remote database per run (Priority: P1)

**Goal**: The operator selects the target per run; default is local; the resolved target is announced before any write.

**Independent Test**: Run the scrape once with no flag and once with `--remote`; confirm each run's rows land only in the intended DB and the output states `local` vs `REMOTE` before writing.

**Depends on**: US1 (there must be a scrape-write to target).

- [X] T014 [US2] In `scripts/scraper/__main__.py`, add `--remote` (store_true → `Target`, default `local`) and `--cache-dir` (default `.cache/analysis`) to the `scrape` and `download-docs` subparsers; remove the now-dead `--output-dir`/`--data-dir` JSON-location flags. (depends on T009)
- [X] T015 [US2] Thread the resolved `target` from `__main__.py` into `run_scrape`/download paths and print the resolved target (`local` vs `REMOTE`) **before** any D1/R2 write (FR-003, FR-004, FR-005, SC-003). (depends on T014)
- [X] T016 [US2] Update the `download-docs` command in `scripts/scraper/__main__.py` + `scripts/scraper/runner.py` to find documents missing R2 images by querying D1 (`d1.query`), upload via `put_object`, and update `documents.file_path` in D1 via `upsert_tables` — carrying `target`. (depends on T014, T011)

**Checkpoint**: Scrape writes to the chosen DB/bucket, defaults to local, and never hits production silently.

---

## Phase 5: User Story 3 - Analysis and classification operate on the database (Priority: P1)

**Goal**: The analysis/classification pipeline reads records from D1, materializes page images from R2 for vision + hashing, and writes `document_analyses`/`document_analysis_records`/`alerts` back to D1 — with no `data/scrape/` dependency.

**Independent Test**: For a period in D1, run `docs-plan` → classify → `apply-extractions` → `analyze` → `mismatches`; confirm it reads from D1, materializes images into `.cache/analysis/<P>/`, writes analyses + alerts to D1, and the app renders them. Plus the parity check (T031).

**Depends on**: Foundational + US1 (data in D1). Target-threading composes with US2.

- [X] T017 [US3] Rewrite `scripts/analysis/loader.py:load_all_periods` to query D1 (replace the `data_dir` param with `target`) and assemble the **identical** `PeriodData`/`raw` shape, re-nesting `document_analysis_records` under `document_analyses[].analysis_records` and parsing JSON columns back to objects (Contract in `contracts/period-loader-and-writeback.md`). Preserve `RefIndex.vendor_first_seen` computed across all periods. (depends on T006)
- [X] T018 [US3] Update every `load_all_periods` caller to pass `target` instead of `data_dir`: `scripts/analysis/extractions.py` (`plan_extractions`, `summarize_mismatches`), `scripts/analysis/__init__.py` (`run_analysis`), `scripts/analysis/verdicts.py` (`loop_state`). (depends on T017)
- [X] T019 [US3] Add `scripts/analysis/images.py` — `materialize_images(period|document_ids, cache_dir, target)`: query `documents.file_path` from D1, `d1.get_object` each `<period>/<basename>` token into `<cache_dir>/<period>/<basename>`, return a map token→local path (skip/flag missing keys). (depends on T006, T007)
- [X] T020 [US3] In `scripts/analysis/extractions.py` `plan_extractions`: materialize the scope's images first, write `<period>.extract-todo.json` to the **cache dir**, and set each page `read_path`/`path` to the materialized cache image; in `scripts/analysis/nf_groups.py` ensure `content_hash` reads the materialized cache paths. (depends on T017, T019)
- [X] T021 [US3] In `scripts/analysis/extractions.py` `_merge_and_write` (apply-extractions): replace the `<period>.json` rewrite with a D1 writeback for the one document — first `d1.execute_sql` a scoped `DELETE FROM document_analysis_records WHERE document_analysis_id = '<doc_analysis_id>'` and `DELETE FROM document_analyses WHERE document_id = '<document_id>'`, then `d1.upsert_tables({"document_analyses":[result.to_dict()]}, target=...)` (which flattens to `document_analysis_records`). The delete-then-insert reproduces the old "drop existing for this document_id, append" semantics — plain `INSERT OR REPLACE` alone would orphan stale per-page records when a re-analysis yields fewer pages or a different NF grouping. (depends on T005, T017)
- [X] T022 [US3] In `scripts/analysis/__init__.py` `run_analysis` (analyze): replace the alerts JSON write with a period-scoped delete-then-insert — `d1.execute_sql` a `DELETE FROM alerts WHERE <period-scope>` then `d1.upsert_tables({"alerts":[…]}, target=...)` — so no stale alert from a prior run survives (a plain upsert would leave alerts the new run no longer emits). (depends on T005, T017)
- [X] T023 [US3] In `scripts/analysis/extractions.py` `_page_refs_for_doc` (summarize_mismatches): emit `read_path` pointing at the materialized cache image for each page so `review-mismatch` can Read it. (depends on T019, T020)
- [X] T024 [US3] In `scripts/analysis/__main__.py`, add `--remote` (Target, default local) and `--cache-dir` to every command (`docs-plan`, `apply-extractions`, `analyze`, `mismatches`, `record-verdict`, `loop-state`); thread `target` + `cache_dir` into the loader, writeback, and image materialization; print the resolved target. (depends on T017, T018, T021, T022)
- [X] T025 [US3] In `scripts/analysis/verdicts.py`, point `verdicts_path` at the cache dir and thread `target` into the `summarize_mismatches`/`loop_state` calls so `record-verdict`/`loop-state` operate against D1 + cache scratch. (depends on T018, T024)
- [X] T026 [P] [US3] Update `.claude/skills/classify-period/SKILL.md`: note `docs-plan` now materializes images into the cache and the manifest `read_path`s resolve there; carry the `--remote`/scope args through. (depends on T020)
- [X] T027 [P] [US3] Update `.claude/agents/analyze-docs.md`: pipeline (classify-period → apply-extractions → analyze → mismatches) carries the target flag; inputs come from D1/R2, not `data/scrape`. (depends on T024)
- [X] T028 [P] [US3] Update `.claude/agents/review-mismatch.md`: `page_refs[].read_path` is a materialized cache image; the ledger entry is read via D1-backed `mismatches --document-id`. (depends on T023, T024)
- [X] T029 [P] [US3] Update `.claude/agents/fix-mismatch.md`: scoped verify commands (`docs-plan`/`apply-extractions`/`analyze`/`mismatches`) carry the target flag. (depends on T024)
- [X] T030 [P] [US3] Update `.claude/skills/improve-classification/SKILL.md`: thread `--remote` through analyze/review/fix and the `loop-state`/`record-verdict` calls. (depends on T024)
- [X] T031 [US3] Parity verification (no code): for an existing period in D1, run the new loader and confirm the assembled `raw` matches the legacy JSON shape (counts + key values for entries/documents/analyses/alerts), proving SC-002/SC-005 before the old path is removed. (depends on T017)

**Checkpoint**: Full scrape → classify → analyze → view works end-to-end with the data folder absent.

---

## Phase 6: Polish & Cross-Cutting Concerns (FR-014 + cleanup)

**Purpose**: Remove the retired file-based path and reconcile docs. Do this **only after US3 + the parity check pass**.

- [X] T032 [P] Remove `scripts/import-to-d1.mjs` (logic now in `scripts/common/d1.py`). (depends on T031)
- [X] T033 [P] Remove `scripts/upload-images-to-r2.mjs` (folded into the scrape run). (depends on T031)
- [X] T034 Remove the dead period-JSON write paths and `--output-dir`/`--data-dir` remnants in `scripts/scraper/runner.py` (incl. `run_download_docs`'s JSON in-place rewrite) and `scripts/scraper/__main__.py`. (depends on T016, T031)
- [X] T035 [P] Update `/home/agent/workspace/svhc-relatorios/CLAUDE.md` pipeline bullets: scrape writes directly to D1 (no period JSON), images upload to R2 during scrape, analysis reads D1/R2, `import-to-d1.mjs`/`upload-images-to-r2.mjs` removed; check `package.json` for any dead references to those scripts. (depends on T031)
- [X] T036 [P] Review `docs/` and the R2 spec note (`specs/012-r2-document-images/data-model.md`) for references to the removed upload script / `data/scrape` source-of-truth and update the canonical-mapping note to point at the scraper as the writer. (depends on T031)
- [X] T037 Run `pnpm lint` && `pnpm format`; then execute `quickstart.md` local end-to-end as the final acceptance (scrape → classify → analyze → view, data folder absent; SC-001/005/007). (depends on T032-T036)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: needs Setup; **blocks all user stories**.
- **US1 (Phase 3)**: needs Foundational. MVP.
- **US2 (Phase 4)**: needs US1 (a scrape-write to target).
- **US3 (Phase 5)**: needs Foundational + US1 (data in D1); composes with US2's target flag but is testable local-only.
- **Polish (Phase 6)**: needs US3 + the T031 parity check to pass before deleting the old path.

### Within US3

- Loader (T017) before its callers (T018) and before writebacks/materialization that assume the D1 shape.
- Image materialization (T019) before manifest/page-ref/grouping tasks (T020, T023) and before vision can run.
- CLI target-threading (T024) before verdicts/loop (T025) and before agent/skill doc updates (T027-T030) that describe the flag.

### Parallel Opportunities

- T001 ∥ start; within Foundational, T006 ∥ T007 (both after T003).
- US3 doc updates T026/T027/T028/T029/T030 are all [P] (separate Markdown files) once their code dependency lands.
- Polish removals T032/T033 and doc updates T035/T036 are [P].

---

## Parallel Example: Foundational

```bash
# After T003 lands, these two are independent:
Task: "Implement query() in scripts/common/d1.py"          # T006
Task: "Implement put_object/get_object in scripts/common/d1.py"  # T007
```

## Parallel Example: US3 doc updates

```bash
Task: "Update classify-period SKILL.md"          # T026
Task: "Update analyze-docs agent.md"             # T027
Task: "Update review-mismatch agent.md"          # T028
Task: "Update fix-mismatch agent.md"             # T029
Task: "Update improve-classification SKILL.md"   # T030
```

---

## Implementation Strategy

### MVP First (US1)

1. Phase 1 Setup → 2. Phase 2 Foundational (the access layer — critical) → 3. Phase 3 US1.
4. **STOP & VALIDATE**: scrape a fresh period into local D1 + R2, confirm rows/images and no JSON. Demo.

### Incremental Delivery

1. Foundational ready → 2. US1 (scrape→D1+R2, MVP) → 3. US2 (local/remote selection) → 4. US3 (analysis on D1/R2) → 5. Polish (remove old path).
Each story is demonstrable before the next; the old file path is removed only after the parity check confirms no regression.

---

## Notes

- [P] = different files, no incomplete-task dependency.
- No automated tests (none requested / no framework); verification is the manual round-trips in T008, T013, T031, T037.
- The D1 schema, deterministic IDs, and what analysis computes are unchanged — only data location and the read/write seams move.
- Keep `documents.file_path` ↔ `src/lib/r2.ts:objectKeyFromFilePath` in agreement (Contract A); the app is otherwise untouched.
- Commit per task or logical group; run `pnpm lint`/`pnpm format` before any commit that touches TS.
