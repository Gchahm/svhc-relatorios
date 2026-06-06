---
description: "Task list for 006-analyze-docs-agent"
---

# Tasks: Claude Vision Agent for Document Analysis (retire the VLM flow)

**Input**: Design documents from `/specs/006-analyze-docs-agent/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No test framework is configured (constitution Principle III). Verification is a manual
synthetic-extraction harness (US2), not automated test files.

**Organization**: Tasks grouped by user story. US1 + US2 are the MVP (extraction works and is
behavior-preserving); US3 retires the old VLM path.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

Single project. Python pipeline under `scripts/scraper/analise/`; agent under `.claude/agents/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Locate the pieces this feature touches; no behavior change yet.

- [x] T001 Locate the Python dependency manifest under `scripts/` that declares `mlx_vlm` (e.g. `scripts/pyproject.toml` and/or `scripts/requirements*.txt`) and record every reference to `mlx`/`mlx_vlm` and to `_load_model`/`_analyze_page`/`EXTRACT_PROMPT` in `scripts/scraper/analise/documentos.py` (catalog only — removal happens in US3).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Factor out the shared selection logic and introduce the extraction-provider seam that
both `docs-plan` and `apply-extractions` build on.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [x] T002 Create `scripts/scraper/analise/extractions.py` with the file-IO + provider scaffolding: `extract_todo_path(data_dir, period)` and `extractions_path(data_dir, period)` helpers, JSON read/write helpers, and the `ExtractionProvider` protocol + `FileExtractionProvider(extractions: dict)` returning `(fields, None)` / `(None, reason)` / `(None, "no extraction for page")` per `data-model.md` and `contracts/extractions.schema.md`.
- [x] T003 Refactor the document-selection logic out of `run_document_analysis` in `scripts/scraper/analise/documentos.py` into a reusable `select_work(periods, refs, *, min_amount, limit, reanalyze, document_ids, entry_ids)` returning the work list with per-group `group_key`, `sibling_sum`, `group_size`, and representative flag — behavior identical to today (content-hash grouping via `group_documents`, filters, skip-already-analyzed unless targeted). Keep `run_document_analysis` working on top of it for now (removed in US3).
- [x] T004 Add the provider seam in `scripts/scraper/analise/documentos.py`: refactor `analyze_single_document` into `build_document_analysis(file_path, entry_amount, vendor_name, period, document_id, entry_id, provider)` that calls `provider(path)` per page (instead of `_load_model`/`_analyze_page`) and otherwise reuses the existing per-page record creation, `_map_artifact_role`, `_rollup_document_fields`, and entry validation unchanged. Rename the JSON-from-text parser `_parse_vlm_response` → `_parse_json_blob` (kept for tolerant agent output).

**Checkpoint**: Selection + provider seam exist; deterministic helpers untouched in behavior.

---

## Phase 3: User Story 1 - Run document extraction without a local vision model (Priority: P1) 🎯 MVP

**Goal**: Produce the plan→agent→apply flow so a maintainer can analyze a period's documents with no
`mlx_vlm`, writing `document_analyses` of the same shape as before.

**Independent Test**: On a machine with no `mlx_vlm`, run `docs-plan` for a period with images,
invoke the agent to produce an extractions file, run `apply-extractions`, and confirm
`document_analyses`/`document_analysis_records` are written and import cleanly.

### Implementation for User Story 1

- [x] T005 [US1] Implement `plan_extractions(data_dir, periods_filter, *, min_amount, limit, reanalyze, document_ids, entry_ids)` in `scripts/scraper/analise/extractions.py`: load periods (`load_all_periods`), call `select_work`, pick one representative document per group, resolve `vendor_name` via refs and an absolute `read_path` per page, and write `<period>.extract-todo.json` per `contracts/extract-todo.schema.md`.
- [x] T006 [US1] Implement `apply_extractions(data_dir, periods_filter)` in `scripts/scraper/analise/extractions.py`: read the manifest + `<period>.extractions.json`, build a `FileExtractionProvider`, call `build_document_analysis` for each representative, run `_apply_group_amount_match`/`reconcile_group` for groups, fan out to siblings via `_fanout_result`, run entry validation, persist with `_merge_and_write`, and print the same summary the old run produced.
- [x] T007 [US1] Update `scripts/scraper/__main__.py`: replace the `analyze-docs` subparser/handler with `docs-plan` (calls `plan_extractions`, args `--periodo/--data-dir/--min-amount/--limit/--reanalyze/--document-id/--entry-id`) and `apply-extractions` (calls `apply_extractions`, args `--periodo/--data-dir`); replace the interactive "Analyze documents (VLM)" menu branch with a "Plan document extraction" + "Apply document extractions" flow. Remove the `run_document_analysis` import once unused.
- [x] T008 [US1] Create `.claude/agents/analyze-docs.md` (frontmatter `name: analyze-docs`, `tools: Read, Glob, Bash, Write`, `model: inherit`) implementing `contracts/agent-interface.md`: ensure/read the manifest, view each page `read_path` with Read, emit the frozen field set from `contracts/page-extraction-fields.md` (no fabrication), write `<period>.extractions.json` keyed by `path`, and report the `apply-extractions` command. Register it in `CLAUDE.md`'s Agents section.

**Checkpoint**: The plan→agent→apply flow runs end-to-end with no local model.

---

## Phase 4: User Story 2 - Preserve grouping, reconciliation, and fraud checks (Priority: P1)

**Goal**: Prove the extraction swap is behavior-preserving: identical extracted values yield
identical roll-up, reconciliation, validation, and `duplicate_billing` outcomes (SC-002).

**Independent Test**: Feed a hand-authored extractions file through `apply-extractions` + `analyze`
and assert outputs match expectations — no model needed.

### Implementation for User Story 2

- [x] T009 [US2] Author a synthetic fixture under `specs/006-analyze-docs-agent/fixtures/`: a small manifest + `extractions.json` covering (a) a single-entry document, (b) a shared-NF group that reconciles, (c) a shared-NF group that over-claims, (d) a heterogeneous document (invoice + boleto + payment_proof pages), and (e) a per-page `{"error": ...}` plus a document with no usable page. Include a short `expected.md` stating the expected `amount_match`/reconciliation/alerts for each.
- [x] T010 [US2] Run `apply-extractions` against the fixture, then `analyze`; verify the resulting `document_analyses`/`document_analysis_records` import via `node scripts/import-to-d1.mjs` against a scratch D1/SQLite (SC-003), the reconciliation classifications and match flags match `expected.md` (SC-002), and the over-claim group produces a `critical` `duplicate_billing` alert (FR-008). Record the run in `quickstart.md` if any step differs.

**Checkpoint**: Behavior preservation demonstrated end-to-end without a VLM.

---

## Phase 5: User Story 3 - Retire the local VLM flow (Priority: P2)

**Goal**: Remove the local-model code and dependency and update docs so there is one obvious flow.

**Independent Test**: `grep -rn "mlx_vlm\|_load_model\|_analyze_page\|EXTRACT_PROMPT" scripts/` and the
dependency manifest return no hits; docs describe the new flow.

### Implementation for User Story 3

- [x] T011 [US3] In `scripts/scraper/analise/documentos.py`, remove `_load_model`, `_analyze_page`, the `_model`/`_processor` module globals, all `mlx_vlm` imports, `EXTRACT_PROMPT`, and the now-dead `run_document_analysis` (its selection moved to `select_work`). Keep every deterministic helper (`PageAnalysisRecord`, `DocAnalysisResult`, `_parse_brl_value`, `_check_date_in_period`, `_normalize_name`, `_page_label_from_path`, `_ROLE_ALIASES`, `_map_artifact_role`, `_rollup_document_fields`, `nf_total_for_reconciliation`, `_apply_group_amount_match`, `_fanout_result`, `_merge_and_write`, `_parse_json_blob`, `build_document_analysis`).
- [x] T012 [US3] Remove `mlx_vlm` (and any mlx-only transitive entries) from the Python dependency manifest under `scripts/` identified in T001, and update the lockfile if one is committed.
- [x] T013 [US3] Update `CLAUDE.md`: rewrite the document-analysis (VLM) bullet to describe the `docs-plan` → `analyze-docs` agent → `apply-extractions` flow and the extractions/manifest artifacts; remove instructions referencing the local model. Confirm the SC-006 greps are clean.

**Checkpoint**: VLM fully retired; deterministic pipeline intact.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T014 Run the full `quickstart.md` verification (plan→agent→apply on a real period if images are present, else the synthetic fixture) and the SC-006 cleanliness greps.
- [x] T015 Run `pnpm lint` and `pnpm format` (formats the touched Markdown/agent files); confirm no unintended diffs and that `specs/006-analyze-docs-agent/` docs are internally consistent.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: after Setup. BLOCKS all user stories. T002 ∥ (T003 → T004) — T003 and
  T004 touch `documentos.py` so run sequentially; T002 is a separate new file.
- **US1 (Phase 3)**: after Foundational. T005 and T006 both live in `extractions.py` (T006 depends on
  T005's manifest shape + T004 provider); T007 depends on T005/T006; T008 [P] (new agent file) can be
  written in parallel with T005–T007.
- **US2 (Phase 4)**: after US1 (needs `apply-extractions`). T010 depends on T009.
- **US3 (Phase 5)**: after US1 proven by US2 (don't delete the old path until the new one is verified).
  T011 → T012 → T013 (T013 grep depends on T011/T012 removals).
- **Polish (Phase 6)**: after US3.

### Within / parallel opportunities

- T002 [P] vs T003 (different files).
- T008 [US1] [P] (agent markdown) independent of the Python work in T005–T007.
- Most other tasks are sequential due to shared files (`documentos.py`, `extractions.py`,
  `__main__.py`).

---

## Implementation Strategy

### MVP (US1 + US2)

1. Phase 1 Setup → Phase 2 Foundational (select_work + provider seam).
2. Phase 3 US1: plan/apply commands + agent → flow runs with no model.
3. Phase 4 US2: synthetic-extraction verification proves behavior preservation.
4. **STOP and VALIDATE** before deleting anything.

### Then retire (US3)

5. Phase 5: remove the VLM code + dependency, update docs.
6. Phase 6: quickstart verification + lint/format.

---

## Notes

- The agent (T008) is the only non-deterministic component; everything else is pure Python reused
  from the current pipeline.
- Do NOT change `nf_groups.py`, `loader.py`, `checks/advanced.py`, or `scripts/import-to-d1.mjs` —
  compatibility with them is the core invariant (SC-002, SC-003, FR-008).
- Commit after each phase; keep the old path runnable until US2 passes.
