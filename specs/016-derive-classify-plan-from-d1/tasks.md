# Tasks: Derive the classification plan from D1 (remove the extract-todo.json manifest)

**Feature**: `016-derive-classify-plan-from-d1` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are OPTIONAL (constitution III — no test framework). Verification is manual + a focused
Python smoke check (see Phase 6). Paths are repo-relative.

## Phase 1: Setup

- [ ] T001 Capture a pre-change equivalence baseline for a local period: run `npx wrangler d1 execute DATABASE --command "SELECT * FROM attachment_analyses ORDER BY attachment_id" --json --local > /tmp/before_analyses.json` and the same for `alerts` (`SELECT * FROM alerts ORDER BY id` → `/tmp/before_alerts.json`). Note the period(s) present via `SELECT period FROM accountability_reports`.

## Phase 2: Foundational (blocking prerequisites)

- [ ] T002 Add the shared content-hash helper `scripts/common/hashing.py`: move the pure `content_hash(file_path: str) -> str | None` (and its `_split_paths`, `_CHUNK` constant) verbatim from `scripts/analysis/nf_groups.py`. Stdlib-only (`hashlib`, `pathlib`). Keep behavior byte-identical (chunked md5, `:{size}:` per-page length delimiter, page order; `None` on no/unreadable pages).
- [ ] T003 In `scripts/analysis/nf_groups.py`, re-export the helper: `from common.hashing import content_hash` and remove the now-moved implementation (keep `_split_paths` only if still referenced locally; otherwise import it too). Verify `from .nf_groups import content_hash` still resolves for existing callers (`attachments.py`, checks).
- [ ] T004 Add the Drizzle column in `src/db/fiscal.schema.ts`: `contentHash: text("content_hash")` on the `attachments` table (nullable, after `filePath`). Update the table comment to note `content_hash` is the shared-NF grouping key.
- [ ] T005 Generate + apply the migration: `pnpm db:generate` (fallback `node_modules/.bin/drizzle-kit generate` per project memory) → commit `drizzle/0008_*.sql` (expect `ALTER TABLE attachments ADD COLUMN content_hash text;`). Apply locally with `pnpm db:migrate:dev`. Confirm via `PRAGMA table_info(attachments)`.

**Checkpoint**: helper shared, schema column live locally. US1/US2/US3 can proceed.

## Phase 3: User Story 2 — Persist the grouping key at capture time (Priority: P2)

**Goal**: The scraper writes `attachments.content_hash` from local page bytes at capture time.
**Independent test**: After a `--download-docs` capture (or a unit call of the helper on a known
page set), the attachment row's `content_hash` is populated; byte-identical pages share the value.

> US2 is sequenced first because it is the enabling change (a populated column lets US1 group from
> D1). It is independently testable via the helper even without portal access.

- [ ] T006 [US2] In `scripts/scraper/runner.py`, import `from common.hashing import content_hash`. In `_scrape_periodo`, when a downloaded attachment's pages are uploaded (the `if download_docs and doc_download_tasks:` block), set `doc_record["content_hash"] = content_hash(";".join(paths_by_id[ext_id]))` for each attachment that got pages; leave it absent/`None` for attachments with no downloaded pages.
- [ ] T007 [US2] In `scripts/scraper/runner.py`, ensure the attachment dict built in the entries loop includes a `"content_hash": None` key by default (so the upsert column set is stable whether or not docs are downloaded), and that `run_download_docs` sets `content_hash` on each updated attachment dict from `content_hash(";".join(paths_by_id[ext_id]))` before `upsert_tables({"attachments": updated_docs})`.
- [ ] T008 [US2] Verify the upsert persists the new column: `scripts/common/d1.py:_generate_inserts` derives columns from row keys, so confirm (read-through) that an attachments row carrying `content_hash` produces an `INSERT OR REPLACE ... ("content_hash") VALUES (...)`. No change expected; add `content_hash` continuity only if a column-ordering assumption exists (it does not).

**Checkpoint**: capture-time writes done; column persists through `common/d1.py`.

## Phase 4: User Story 1 — Run the pipeline without a manifest file (Priority: P1) 🎯 MVP

**Goal**: Plan + apply derive groups from D1; no `extract-todo.json` is written or read.
**Independent test**: Run `docs-plan` (prints, no file) → `apply-extractions` → `analyze` →
`mismatches` on a local period; no `*.extract-todo.json` exists; analyses/alerts equivalent to T001.

- [ ] T009 [US1] In `scripts/analysis/nf_groups.py`, make `group_attachments(attachments)` column-aware: key each attachment by `doc.get("content_hash")` when truthy; else fall back to `content_hash(doc.get("file_path"))`; else `doc:{id}`. Preserve the existing singleton-on-unhashable contract and the public signature. Update the docstring.
- [ ] T010 [US1] In `scripts/analysis/extractions.py`, extract a pure `build_plan(periods, refs, *, min_amount, limit, reanalyze, attachment_ids, entry_ids) -> dict` that returns the per-period plan envelope (`{period, cache_dir, generated_for, groups: [...] }`) currently assembled inside `plan_extractions` — same `groups[]`/`pages[]`/`members[]` shape (see data-model.md). It calls `select_work` + builds pages/members exactly as today. No file I/O.
- [ ] T011 [US1] Rewrite `plan_extractions(...)` to: materialize images, call `build_plan(...)`, and **print** the envelope(s) as JSON to stdout (one object per period, or a list) plus the existing human summary line — writing **no** `*.extract-todo.json`. Remove `extract_todo_path`, `_write_json` usage for the manifest, and `_periods_with_manifests`. Keep the "Nothing to extract" message.
- [ ] T012 [US1] Rewrite `apply_extractions(...)` to derive groups from D1 instead of reading the manifest: for each target period (from `periods_filter` or all periods in D1), load periods, materialize images, call `build_plan(...)`, then run the existing per-group roll-up / `_apply_group_amount_match` / sibling fan-out / `_merge_and_write` over `plan["groups"]`. Remove the manifest read (`_read_json(todo_path)`) and the `_periods_with_manifests` discovery. Behavior of the roll-up/fan-out is unchanged.
- [ ] T013 [US1] In `scripts/analysis/extractions.py`, remove `extract_todo_path` and any remaining `extract-todo.json` references; keep `classify_path_for`/`FileExtractionProvider`/`_page_refs_for_doc`/`summarize_mismatches` intact (the `.classify.json` seam is out of scope).
- [ ] T014 [US1] In `scripts/analysis/__main__.py`, update the `docs-plan` subparser help to "print the DB-derived plan to stdout (no manifest file)" and confirm the `apply-extractions` handler still passes `target`/`periods_filter`/`cache_dir`. No flag changes.

**Checkpoint**: MVP — manifest-free plan + apply working on populated-column data.

## Phase 5: User Story 3 — Equivalent results on existing (NULL-hash) data (Priority: P2)

**Goal**: Pre-change rows (NULL `content_hash`) group identically via fallback, and get backfilled.
**Independent test**: On a local period whose `content_hash` is NULL, grouping + reconciliation match
T001; after one run the column is populated.

- [ ] T015 [US3] In `scripts/analysis/images.py`, after rewriting each attachment's `file_path` to local cache paths, compute the content hash for attachments whose `content_hash` is NULL/empty (using `common.hashing.content_hash` over the resolved local paths) and collect `{id, content_hash}` updates. Mutate the in-memory `doc["content_hash"]` so the same run groups from it.
- [ ] T016 [US3] In `scripts/analysis/images.py`, write the collected backfill updates to D1 best-effort: issue an UPDATE of only `content_hash` per attachment (via `d1.execute_sql` with escaped ids, or `upsert_tables`-of-minimal-rows only if it would not clobber other columns — prefer a targeted `UPDATE attachments SET content_hash=... WHERE id=... AND content_hash IS NULL`). Never overwrite a non-NULL value; never touch other columns; log and continue on failure. Add a `materialize_period_images(..., backfill_hash: bool = True)` flag if needed to keep `mismatches`/`docs-plan`/`apply` callers explicit.
- [ ] T017 [US3] Confirm `select_work`/`group_attachments` now see the in-memory backfilled hash so plan and apply group purely from the column once materialized (no second hashing pass within a run).

**Checkpoint**: legacy data equivalent + self-healing.

## Phase 6: Polish & Cross-Cutting (docs, skill/agent, verification)

- [ ] T018 [P] Update `.claude/skills/classify-period/SKILL.md`: the manifest no longer exists — `docs-plan` prints the plan to stdout; the skill parses that JSON (groups[].pages[].read_path) instead of reading `<period>.extract-todo.json`. Update the "Read the manifest" step and the closing report/boundaries.
- [ ] T019 [P] Update `.claude/agents/analyze-docs.md`: reflect that the plan is DB-derived (no manifest); the procedure text mentioning the manifest, if any, is corrected. (Commands are unchanged.)
- [ ] T020 [P] Update `scripts/README.md`: docs-plan now prints the plan (no manifest file); attachments carry a `content_hash` written at scrape time; cache no longer holds `extract-todo.json`.
- [ ] T021 [P] Update `scripts/pipeline-flow.md`: remove the `period.extract-todo.json` node from the architecture + sequence diagrams and the cache bullet; note grouping reads `attachments.content_hash`.
- [ ] T022 [P] Update `CLAUDE.md`: in the "Attachment analysis" and "Shared-NF grouping" bullets, replace the "writes the work manifest `.cache/analysis/<p>.extract-todo.json`" description with "derives the plan from D1 (`attachments.content_hash`)"; keep the rest accurate.
- [ ] T023 Grep gate: `grep -rn "extract-todo" scripts .claude` returns nothing in code/skill/agent (docs may keep only a historical note). Fix any stragglers.
- [ ] T024 Hash-continuity check: `cd scripts && uv run python -c "from common.hashing import content_hash; from analysis.nf_groups import content_hash as c2; print(content_hash is c2 or 'rexport-ok')"` — confirm `nf_groups.content_hash` resolves to the shared helper.
- [ ] T025 Equivalence verification: on the feature branch (migration applied), re-run `cd scripts && uv run python -m analysis apply-extractions --periodo <P>` then `analyze --periodo <P>` for the baseline period(s) from T001; snapshot `attachment_analyses` + `alerts` to `/tmp/after_*.json` and diff against `/tmp/before_*.json`. Groups, `amount_match`/`vendor_match`/`date_match`, and `duplicate_billing` alerts MUST match. Confirm `ls .cache/analysis/*.extract-todo.json` finds nothing.
- [ ] T026 Quality gates: `pnpm lint` and `pnpm format`; confirm `drizzle/0008_*.sql` + `src/db/fiscal.schema.ts` are committed together.

## Dependencies & Execution Order

- **Setup (T001)** → before everything (baseline for equivalence).
- **Foundational (T002–T005)** → blocks all stories (shared helper + schema column).
- **US2 (T006–T008)** → depends on T002 (helper). Independent of US1/US3 logic.
- **US1 (T009–T014)** → depends on T002–T005; T009 (column-aware grouping) precedes T010–T012.
- **US3 (T015–T017)** → depends on US1's `build_plan` (T010) + grouping (T009) and the helper (T002).
- **Polish (T018–T026)** → after the code phases; T018–T022 are mutually parallel `[P]` (different files); T023–T026 verify and must run last.

## Parallel Opportunities

- Docs/skill/agent updates run together: **T018, T019, T020, T021, T022** (distinct files).
- Within Foundational, T002/T003 (Python) and T004/T005 (schema) are largely independent and may overlap, but T005 (generate) must follow T004 (schema edit).

## Implementation Strategy

- **MVP = US1** (Phase 4) on populated-column data, on top of Foundational + US2. Delivers the headline
  outcome: no manifest, plan from D1.
- **US3** makes it safe on existing local/prod data without a re-scrape (the realistic state of this repo).
- Ship US2 + US1 + US3 together since they are small and interdependent for the equivalence acceptance.
