# Tasks: Analysis-owned attachment state table

**Feature**: 026-attachment-state-table | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Issue**: Closes #33 (BUG-002)

Tests requested: YES (the plan adds `scripts/tests/test_attachment_state.py` for the new
read/write seam; the repo's existing `unittest` suite must keep passing). No JS test framework.

## Phase 1: Setup

- [x] T001 Confirm baseline: run `python -m unittest discover -s scripts/tests -t scripts` and `pnpm lint` from repo root, recording that they pass before changes (so regressions are attributable).

## Phase 2: Foundational (BLOCKS all user stories)

The schema change + migration must land first: dropping `attachments.classified_at` breaks
every read until the loader/CLIs are repointed, so the migration and the code that reads it
are co-dependent. Do the schema + migration here, then the user-story code repoints the reads/writes.

- [x] T002 Add the `attachmentState` table to `src/db/fiscal.schema.ts` (`attachment_state`: `attachment_id` TEXT PK → `attachments.id`, `classified_at` integer timestamp_ms) and REMOVE the `classifiedAt` column from the `attachments` table definition, per `data-model.md`.
- [x] T003 Generate the Drizzle migration (`node_modules/.bin/drizzle-kit generate`; use the `.bin` path directly if the `pnpm db:generate` shim fails in the sandbox) producing `drizzle/0012_*.sql`.
- [x] T004 Hand-augment `drizzle/0012_*.sql` so it (1) creates `attachment_state`, (2) `INSERT INTO attachment_state (attachment_id, classified_at) SELECT id, classified_at FROM attachments WHERE classified_at IS NOT NULL;` BEFORE (3) the column-drop/table-rebuild — ordering per `research.md` Decision 6 / `data-model.md` "Migration data flow". Keep all other `attachments` columns (incl. `content_hash`) intact.
- [x] T005 Apply the migration to local D1 (`pnpm db:migrate:dev`) and confirm: `attachment_state` exists, previously-`classified_at` rows were copied, and `attachments` no longer has `classified_at` but still has `content_hash`.

**Checkpoint**: Schema + migrated local D1 ready. The pipeline is temporarily broken (reads a dropped column) until US1/US2 repoint it — proceed immediately.

## Phase 3: User Story 1 — Mirror table is verifiable against a fresh scrape (P1)

**Goal**: The analysis pipeline issues ZERO writes to `attachments`. Includes repointing the
classified-stamp write to `attachment_state` and removing the `content_hash` backfill.

**Independent test**: Snapshot `attachments` (row hashes) for a period, run classify → apply →
analyze, diff — zero pipeline-attributable changes (SC-001, contract C5).

- [x] T006 [P] [US1] In `scripts/analysis/attachments.py:_merge_and_write`, replace the `UPDATE attachments SET classified_at = … WHERE id = …` statement with an upsert into `attachment_state` (`INSERT INTO attachment_state(attachment_id, classified_at) VALUES('<id>', <now_ms>) ON CONFLICT(attachment_id) DO UPDATE SET classified_at = excluded.classified_at;`) inside the SAME `execute_sql` batch (preserve atomicity per contract C3 / FR-004). Update the docstring to say `attachment_state`, not `attachments`.
- [x] T007 [P] [US1] In `scripts/analysis/images.py`, REMOVE `_backfill_content_hashes` and its call site, and remove the now-dead `attachments_needing_hash_backfill` write path / `backfill_hash` D1-write branch — KEEP the in-memory `doc["content_hash"] = content_hash(...)` assignment used for this run's grouping (contract C6 / FR-006). Update the module docstring (no longer "the only write-back to D1 is the content_hash backfill").
- [x] T008 [US1] Grep the analysis pipeline (`scripts/analysis/`) for any remaining `attachments`-targeting write (`UPDATE attachments`, `INSERT … attachments`, `DELETE … attachments`) and confirm none remain (FR-002). Record the grep result.

**Checkpoint**: No analysis write touches `attachments`; classified stamp lands in `attachment_state`.

## Phase 4: User Story 2 — Work selection still drives classification (P1)

**Goal**: `docs-plan` pending set, the classified stamp (already repointed in US1), and
`mark-pending` all read/write `attachment_state` and behave identically to today.

**Independent test**: fresh period ⇒ all pending; after apply ⇒ none pending; mark-pending a
subset ⇒ exactly that subset pending next plan (SC-002, contracts C1/C2/C4).

- [x] T009 [US2] In `scripts/analysis/loader.py`, change the attachment query to LEFT JOIN `attachment_state` and alias its `classified_at`, so each attachment dict still carries `classified_at` (NULL when no state row) — e.g. `SELECT d.*, s.classified_at AS classified_at FROM attachments d JOIN entries e ON d.entry_id = e.id LEFT JOIN attachment_state s ON s.attachment_id = d.id WHERE e.report_id = …` (contract C1).
- [x] T010 [US2] In `scripts/analysis/extractions.py:mark_pending`, replace `UPDATE attachments SET classified_at = NULL WHERE <where>` with a write to `attachment_state` only: clear `classified_at` for the resolved attachment ids (`UPDATE attachment_state SET classified_at = NULL WHERE attachment_id IN (<ids>)`; when the existing `<where>` selects by entry id, resolve to attachment ids via a read-only `attachments` lookup or a join). MUST NOT touch `attachments` (contract C4 / FR-005). Update the docstring.
- [x] T011 [US2] Verify `scripts/analysis/attachments.py:select_work` still reads `doc.get("classified_at")` unchanged (no edit expected) and update its docstring's "UPDATE attachments SET classified_at = NULL via mark-pending" wording to reference `attachment_state` (contract C2).

**Checkpoint**: The plan → apply → mark-pending loop runs entirely off `attachment_state`.

## Phase 5: User Story 3 — Only the scraper owns content_hash (P2)

**Goal**: Confirm the scraper remains the sole `content_hash` writer and grouping is unchanged.
(The analysis-side removal happened in US1/T007; this story validates the scraper-owned path.)

**Independent test**: run analysis on a period with a NULL-`content_hash` legacy attachment ⇒
zero `attachments` writes, grouping still correct via the in-memory fallback; the scraper's
image-download path still populates `content_hash` (SC-004, contract C6 / FR-007).

- [x] T012 [US3] Confirm `scripts/scraper/runner.py` still writes `content_hash` on both the scrape (`_scrape_periodo`) and image-download (`run_download_docs`) paths (no change expected) and that this is now the ONLY `content_hash` writer in the repo (grep `content_hash =`/`SET content_hash`). Record the finding.
- [x] T013 [US3] Confirm `scripts/analysis/nf_groups.py:group_attachments` still reads `content_hash` with its in-memory compute-from-cache fallback for NULL rows (no edit expected); note it in the verification.

**Checkpoint**: `content_hash` is scraper-owned end-to-end; grouping unaffected.

## Phase 6: Tests

- [x] T014 [P] Add `scripts/tests/test_attachment_state.py`: (a) `select_work` treats `classified_at is None` as pending and non-None as classified (fixtures, contract C2); (b) `_merge_and_write` produces ONE batch whose SQL upserts `attachment_state` and contains NO `attachments` write (string assertions, contract C3); (c) `mark_pending` emits an `attachment_state` UPDATE and no `attachments` write (contract C4). Use the existing `scripts/tests/` style (stdlib `unittest`, monkeypatch `d1.execute_sql`).
- [x] T015 Run `python -m unittest discover -s scripts/tests -t scripts` — all tests (new + existing) pass.

## Phase 7: Polish & Cross-Cutting

- [x] T016 [P] Update `CLAUDE.md`: amend the BUG-002-relevant pipeline notes (the "atomic delete-then-insert writebacks" / `_merge_and_write` / `mark-pending` / "content_hash backfill" / mirror-tables bullets) to say the classified stamp lives in `attachment_state` and the analysis pipeline performs zero `attachments` writes; mention the new table.
- [x] T017 Run `pnpm lint` and `pnpm format` from repo root; confirm clean. Confirm the migration + regenerated `fiscal.schema.ts` are staged (Constitution I/III).
- [x] T018 Verification (for the PR body): apply the migration to local D1, snapshot `attachments` row hashes, run a full classify → apply → analyze over a real local period, re-snapshot and diff (expect zero pipeline-attributable changes); run `docs-plan` + `mark-pending` + `docs-plan` to show the pending-set round-trips; log into the app (`ui-login`) and confirm `/dashboard/documents` + `/dashboard/entries` still render. Record results.

## Dependencies & order

- Phase 1 (T001) → Phase 2 (T002→T003→T004→T005, strictly serial) → then US1/US2 can interleave.
- US1 T006 and T007 are `[P]` (different files: `attachments.py`, `images.py`). T008 after both.
- US2 T009 (loader), T010 (extractions), T011 (attachments docstring) — T009/T010 different files, can be parallel; T011 touches `attachments.py` (same file as T006) so order it after T006.
- US3 (T012, T013) is validation-only; depends on US1's T007 removal being done.
- Phase 6 tests depend on US1+US2 code. Phase 7 last.

## Parallel execution examples

- After T005: run T006 (`attachments.py`) and T007 (`images.py`) in parallel.
- In US2: run T009 (`loader.py`) and T010 (`extractions.py`) in parallel.
- T014 (new test file) and T016 (CLAUDE.md) are independent of each other.

## Implementation strategy

MVP = Phase 2 + US1 + US2 (the invariant is fixed and the loop works). US3 is validation that
the removal in US1 is sufficient and the scraper covers `content_hash`. Tests + polish finalize.
