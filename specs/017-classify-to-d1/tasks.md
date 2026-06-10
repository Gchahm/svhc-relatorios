---
description: "Task list for feature 017-classify-to-d1"
---

# Tasks: Remove `.classify.json` — classify-doc-page writes per-page extractions to D1

**Input**: Design documents from `/specs/017-classify-to-d1/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: No automated test framework is configured (constitution III) and the spec does not request
tests; verification is the manual end-to-end `quickstart.md` plus `pnpm lint`/`pnpm format`/`tsc`.

**Organization**: Grouped by user story. Foundational phase is the schema/data layer that blocks all
stories (the per-page writer breaks if the migration and the emitting code disagree, so the
dead-column removal lives here too).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task).
- **[Story]**: US1 / US2 / US3 (Setup & Foundational tasks have no story label).

---

## Phase 1: Setup

**Purpose**: Confirm the working state before changing the schema.

- [x] T001 Confirm clean tree on branch `017-classify-to-d1` and that local D1 migrations are current: `pnpm db:migrate:dev` (no pending diff), so the Phase 2 migration is the only new one.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema + data layer every story builds on. The new staging table, the dropped dead
columns, and the Python/UI code that must agree with the column set. **Blocks US1, US2, US3.**

⚠️ The dropped-column removal (FR-009) is here, not in a later phase: `AttachmentAnalysisResult.to_dict`
emits `raw_response` and `PageAnalysisRecord.to_dict` emits `raw_text`; once the columns are dropped,
the merge's `INSERT OR REPLACE` would fail and `tsc` would break on the UI select unless these are
removed together with the migration.

- [x] T002 Edit `src/db/fiscal.schema.ts`: add the `pageClassifications` table (`page_classifications`) — columns `id` (PK), `attachmentId` (NOT NULL, FK → `attachments.id`), `pageLabel` (text 20, NOT NULL), `pageIndex` (integer, nullable), `response` (text, nullable — JSON), `error` (text, nullable), `recordedAt` (timestamp_ms, NOT NULL, default now) — plus index `page_classifications_attachment_id_idx` on `attachmentId`, and a relation back to `attachments`. Match the table's column ordering/style to the existing tables.
- [x] T003 In the SAME edit to `src/db/fiscal.schema.ts`: remove `rawResponse: text("raw_response")` from `attachmentAnalyses` and `rawText: text("raw_text")` from `attachmentAnalysisRecords`.
- [x] T004 Generate the migration: run `pnpm db:generate` (use the `node_modules/.bin/drizzle-kit` workaround if `pnpm <script>` fails in the sandbox). Verify the generated `drizzle/0010_*.sql` creates `page_classifications` and drops both columns; commit it. Then `pnpm db:migrate:dev` to apply locally.
- [x] T005 Add `"page_classifications"` to `TABLE_ORDER` in `scripts/common/d1.py` (after `attachments`, before `attachment_analyses` — it FKs `attachments`) so `upsert_tables` can write the staging rows.
- [x] T006 [P] Remove the dead `raw_response` field from `scripts/analysis/attachments.py`: drop the `raw_response` attribute on `AttachmentAnalysisResult`, its `"raw_response"` key in `to_dict`, and any assignment in `_fanout_result`.
- [x] T007 [P] Remove the dead `raw_text` field from `scripts/analysis/attachments.py`: drop the `raw_text` attribute on `PageAnalysisRecord`, its `"raw_text"` key in `to_dict`, and the `raw_text=r.raw_text` copy in `_fanout_result`.
- [x] T008 [P] Remove the UI references to the dropped column: in `src/app/api/attachment-analyses/[id]/route.ts` drop `rawText: attachmentAnalysisRecords.rawText` from the select; in `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx` drop the `rawText` field from the record type, the `record.rawText` fallback in the values resolver, and the `record.rawText` render block.
- [x] T009 Create `scripts/analysis/page_classifications.py` with: the table name constant; `validate_page_fields(obj) -> str | None` (port the frozen-contract checks from `.claude/skills/classify-doc-page/scripts/validate_classify.py` — REQUIRED_KEYS, PAPEL_VALUES, STRING_OR_NULL, AMOUNT_KEYS, and the single-key `{"error": ...}` alternative — returning an error message or `None`); `page_classification_id(attachment_id, page_label)` via `det_id`; `record_classification(attachment_id, page_label, page_index, payload, *, target)` that validates then `d1.upsert_tables({"page_classifications": [row]})`; and the `D1ExtractionProvider` class per `contracts/extraction-provider.md`.

**Checkpoint**: schema migrated, dead columns gone, app + Python still consistent (`tsc`, `pnpm lint` clean), staging module exists with validation + provider.

---

## Phase 3: User Story 1 — Vision output survives a cleared cache (Priority: P1)

**Goal**: The merge reads per-page extractions from D1, so completed vision work is not lost when the
scratch cache is cleared.

**Independent Test**: Record per-page extractions (via the new CLI), delete the scratch dir, run
`apply-extractions`, and confirm the `attachment_analyses` + records are produced from D1 (quickstart §2).

- [x] T010 [US1] In `scripts/analysis/loader.py` (`_load_period_raw`): query `page_classifications` for the period's attachments (join attachments→entries→report), decode each row's `response` JSON back to an object (mirroring the `attachment_analysis_records.response` decode), and add `raw["page_classifications"]` to the returned dict.
- [x] T011 [US1] In `scripts/analysis/attachments.py` (`build_attachment_analysis`): change the provider call from `provider(path)` to `provider(attachment_id, page_label)` (both already available in the loop); update the `ExtractionProvider` seam docstring/type comment to the new signature.
- [x] T012 [US1] In `scripts/analysis/extractions.py` (`apply_extractions`): build a `D1ExtractionProvider` from `pd.raw.get("page_classifications", [])` per period (import from `page_classifications.py`) and use it instead of `FileExtractionProvider`. Keep the rest of the driver (group reconcile, sibling fan-out, `_merge_and_write`, summary) unchanged.
- [x] T013 [US1] Add the `record-classification` subcommand to `scripts/analysis/__main__.py` per `contracts/record-classification-cli.md`: args `--attachment-id` (req), `--page` (req), `--page-index`, `--json` (inline or `-`/omitted → read stdin), `--remote`; parse JSON, call `page_classifications.record_classification(...)`, exit non-zero with a clear stderr message on invalid JSON or contract violation, print a one-line confirmation on success.
- [x] T014 [US1] Verify quickstart §2 + §4 + §5 locally: record a page, clear `../.cache/analysis/<period>`, run `apply-extractions`, confirm analyses build from D1; re-record a page and confirm exactly one staging row (idempotent); confirm a contract-violating payload is rejected non-zero.

**Checkpoint**: the merge is DB-backed; clearing scratch no longer loses vision work.

---

## Phase 4: User Story 2 — End-to-end classification unchanged in outcome (Priority: P1)

**Goal**: The real classify flow (skills/agent) records per-page extractions to D1, and the full
`classify → apply → analyze → mismatches` outcome is equivalent to the file-based flow.

**Independent Test**: Run the end-to-end sequence for a period and compare analyses/alerts/mismatches
to a pre-change baseline (quickstart §1, §3).

- [x] T015 [US2] Update `.claude/skills/classify-doc-page/SKILL.md`: input now also carries `attachment_id` and `page_label` (passed by the orchestrator); change `allowed-tools` to `Read, Bash` (drop `Edit, Write, Glob`); remove the `PostToolUse: Write|Edit` hook block (keep the `PreToolUse: Read` image guard and `Stop` hook); rewrite step 4 + the "Output contract" section so the result is recorded via `cd scripts && uv run python -m analysis record-classification --attachment-id <id> --page <label> [--page-index <n>] [--remote]` piping the JSON on a `<<'JSON' … JSON` heredoc on stdin (the fields object OR `{"error": "<reason>"}`), and note the CLI validates + rejects on a contract violation so a non-zero exit means "fix the JSON and re-run".
- [x] T016 [US2] Remove `.claude/skills/classify-doc-page/scripts/validate_classify.py` (validation now lives in the CLI; the hook that ran it is removed in T015). Leave `validate_image.py` intact.
- [x] T017 [US2] In `scripts/analysis/extractions.py` (`build_plan`): annotate each plan page object with `recorded: bool` — true when a `page_classifications` row exists for `(representative_attachment_id, page_label)`. Source the recorded set from the loaded period data (pass `periods`/`refs` already available to `build_plan`); this is a pure read so `docs-plan` stdout stays pure JSON.
- [x] T018 [US2] Update `.claude/skills/classify-period/SKILL.md`: step 3 — pass each page's `attachment_id` (the group's `representative_attachment_id`) and `page_label` to `classify-doc-page` along with `read_path`; step 4 (completeness) — re-run `docs-plan` and re-dispatch any page whose `recorded` is `false` (replace the `Glob` for sibling `.classify.json`); update the purpose/boundary lines that mention writing `.classify.json` to describe DB recording; update the skill `description` frontmatter accordingly.
- [x] T019 [US2] Update `.claude/agents/analyze-docs.md`: replace the `.classify.json` mentions (steps 1 + boundaries) with the DB-recorded flow (classify-period records per-page extractions to D1; apply reads from D1); no behavioral change to the command sequence.
- [x] T020 [US2] Verify quickstart §1 + §3: `docs-plan` shows `recorded:false` initially and `recorded:true` after recording; the end-to-end sequence yields analyses/alerts/mismatches equivalent to the file-based baseline.

**Checkpoint**: the real skill/agent flow records to D1; end-to-end behavior is preserved.

---

## Phase 5: User Story 3 — Cache holds only reproducible image scratch (Priority: P2)

**Goal**: The file seam is fully gone — no code writes/reads `*.classify.json`, the file-backed
provider is deleted, and the docs describe the DB-backed flow.

**Independent Test**: After a full run, no `*.classify.json` exists and a codebase search finds no
references to it or the file-backed provider (quickstart §6).

- [x] T021 [US3] In `scripts/analysis/extractions.py`: delete `FileExtractionProvider`, `classify_path_for`, and `CLASSIFY_SUFFIX`; drop the now-unused `_parse_json_blob` import if nothing else uses it (and remove `_parse_json_blob` from `attachments.py` only if no remaining caller); update the module docstring + the `docs-plan`/`apply` docstrings/log lines that mention `.classify.json` to describe the D1 staging table.
- [x] T022 [US3] Update `scripts/analysis/__main__.py` help text: the `apply-extractions` help string (and the module docstring's command list) drop the `<image>.classify.json` phrasing in favor of "per-page classifications (D1)"; add `record-classification` to the command list comment.
- [x] T023 [P] [US3] Update `CLAUDE.md`: in the "Attachment analysis (Claude vision skills)" pattern and any related bullet, replace the `<image>.classify.json` staging description with the `page_classifications` table + `record-classification` CLI flow; note the dropped `raw_response`/`raw_text` columns and the new table under the schema/terminology notes.
- [x] T024 [P] [US3] Update `scripts/README.md`: replace the `.classify.json` descriptions (the cache note, the classify-doc-page section, the apply section, and the example command flow) with the DB-recorded flow + the `record-classification` command.
- [x] T025 [P] [US3] Update `scripts/pipeline-flow.md`: the "what runs where" table row + the cache note + both Mermaid diagrams (the `cj["image.classify.json"]` node and the `classifyD → cj → apply` edges, and the sequence diagram's `write image.classify.json` / `read classify.json` steps) to show `classify-doc-page` recording to D1 and `apply` reading `page_classifications` from D1.
- [x] T026 [P] [US3] Update `.claude/agents/review-mismatch.md`: correct the boundary note that lists `.classify.json` (it should no longer reference a writable classify file; the review agent still never writes code/schema/D1).
- [x] T027 [US3] Run quickstart §6: `grep` finds no functional `classify.json` / `FileExtractionProvider` / `raw_response` / `rawText` references (only the migration's column drop + spec prose), and `find` shows no `*.classify.json` in the cache after a run.

---

## Phase 6: Polish & Cross-Cutting

- [x] T028 Run `pnpm lint` and `pnpm format` (and `npx tsc --noEmit`) from the repo root; fix any issues. Confirm `drizzle/0010_*.sql` and the regenerated schema are committed.
- [x] T029 Re-read the spec's Success Criteria (SC-001…SC-006) and confirm each is demonstrably met by the quickstart steps run in T014/T020/T027; note any gap.

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** must complete before any user story.
- **US1 (Phase 3)** depends on Foundational (table, `TABLE_ORDER`, staging module). It is the data-path
  MVP — once done, the cleared-cache guarantee holds even before the skills are rewired.
- **US2 (Phase 4)** depends on US1 (the CLI + provider must exist before the skill calls them and the
  plan annotates `recorded`).
- **US3 (Phase 5)** depends on US1+US2 (the file provider can only be deleted once nothing uses it and
  the skills no longer write files). Doc tasks T023–T026 are mutually parallel `[P]`.
- **Polish (Phase 6)** last.

## Parallel Opportunities

- Within Foundational: T006, T007, T008 touch different files and can run in parallel after T002–T004.
- Within US3: T023, T024, T025, T026 are independent doc files → run in parallel.

## Implementation Strategy

- **MVP = Phase 2 + Phase 3 (US1)**: the migration, staging module, D1 provider, loader, and
  `record-classification` CLI — this alone delivers the core "vision work survives a cleared cache"
  value and is independently testable.
- Then **US2** rewires the real skill/agent flow for end-to-end equivalence, and **US3** removes the
  dead file path + updates docs for the clean end state.
