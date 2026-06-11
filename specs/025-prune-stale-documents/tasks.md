# Tasks: Prune stale documents and links after re-classification

**Feature**: `025-prune-stale-documents` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

The behavior change is contained in one function (`build_documents`). User Stories 1 and 2 are both
satisfied by making the write authoritative (stale rows pruned, atomic batch) — they share the same
implementation tasks; the unit tests verify both. User Story 3 (pruned-count logging) is an additive
log line on the same function. Tests are included because the spec's User Stories request them and the
constitution allows spec-requested tests under `scripts/tests/`.

## Phase 1: Setup

- [ ] T001 Confirm the existing stdlib `unittest` harness runs from repo root:
  `cd scripts && python -m unittest discover -s tests -t scripts` (baseline green before changes).

## Phase 2: Foundational

_None — no shared infrastructure or schema change. `scripts/common/d1.py` already exposes every seam
(`query`, `build_sql`, `upsert_sql`, `execute_sql`)._

## Phase 3: User Story 1 + 2 — authoritative prune (Priority: P1)

**Goal**: After `build_documents`, the persisted `documents`/`document_entries` equal exactly the
desired sets the current analyses produce — no zombie document/link survives a re-classification, and
no false `document_overpayment` can be raised from one. The prune + upsert run in one atomic batch.

**Independent test**: Build, re-key one analysis, rebuild → old doc/link gone, new present; empty
desired state → all docs/links removed; both emitted as a single `execute_sql` batch.

- [ ] T002 [P] [US1] Add unit-test module `scripts/tests/test_document_prune.py` mirroring
  `scripts/tests/test_alert_writeback_atomic.py`: stub `documents._load_analyses_global` and
  `documents.d1` (`query` for the existing-id pre-read; `execute_sql` recording the batch SQL) and
  assert: (T1) re-key → batch contains `DELETE FROM document_entries WHERE id NOT IN (...)` +
  `DELETE FROM documents WHERE id NOT IN (...)` + `INSERT OR REPLACE INTO "documents"` /
  `"document_entries"` in ONE `execute_sql` call; (T2) empty desired state → one batch with
  unconditional `DELETE FROM document_entries;` + `DELETE FROM documents;` and NO INSERT; (T3) DELETE
  predicate lists the DESIRED ids (not stale); (T4) nothing persisted + nothing desired → no
  `execute_sql`; (T5) pruned-count assertion (see US3).
- [ ] T003 [US1] In `scripts/analysis/documents.py:build_documents`, after computing `docs`/`links`,
  build the desired id sets (`desired_doc_ids = {d["id"] …}`, `desired_link_ids = {l["id"] …}`) and
  compose the prune SQL: when `desired_link_ids` is non-empty →
  `DELETE FROM document_entries WHERE id NOT IN (<escaped ids>);` else
  `DELETE FROM document_entries;`; likewise for `documents`/`desired_doc_ids`. Reuse the same
  single-quote id escaping the module already uses (e.g. the `_load_analyses_global` an-id pattern).
- [ ] T004 [US1] Replace the `d1.upsert_tables(...)` call with a SINGLE atomic batch: assemble
  `prune_sql + d1.upsert_sql({"documents": …, "document_entries": …})` and run it via
  `d1.execute_sql(sql, target=target)`. Order DELETE links → DELETE docs → (PRAGMA + INSERTs). Skip
  the `execute_sql` entirely when there is nothing to prune AND nothing to upsert (combined SQL empty).
  Keep the `(len(docs), len(links))` return value unchanged.

## Phase 4: User Story 3 — visible pruned counts (Priority: P3)

**Goal**: The run log reports pruned counts alongside upserted counts so a shrinking derived set is
visible.

- [ ] T005 [US3] In `build_documents`, before the write, read the persisted id sets
  (`SELECT id FROM documents` / `SELECT id FROM document_entries` via `d1.query`) and compute
  `pruned_docs = existing_doc_ids - desired_doc_ids`, `pruned_links = existing_link_ids -
  desired_link_ids`. Extend the existing `logger.info(...)` line to report both upserted and pruned
  document/link counts (e.g. `"… %d document(s), %d link(s) upserted; pruned %d document(s), %d
  link(s); %d analysis(es) skipped"`). Covered by T2/T5 in the test module.

## Phase 5: Polish & Cross-Cutting

- [ ] T006 Update `CLAUDE.md` — extend the "Documents entity & overpayment (feature 020)" / feature 024
  notes to state that `build_documents` is now an AUTHORITATIVE write (prunes stale documents/links not
  in the current desired state, batched atomically like the alert writeback) — feature 025 / issue #36.
- [ ] T007 Run the full unit suite (`cd scripts && python -m unittest discover -s tests -t scripts`) and
  `pnpm lint && pnpm format` (TS app unchanged — confirms no incidental breakage); confirm all green.
- [ ] T008 Verify against local data per `quickstart.md` (build-documents, re-key an analysis, rebuild,
  confirm the obsolete document/link are gone and no orphan documents remain) and via the
  `/dashboard/documents` UI; record the verification in the PR body.

## Dependencies

- T001 (baseline) → T002 (tests can be written before impl) and T003/T004 (impl).
- T003 → T004 (T004 consumes the prune SQL built in T003).
- T004 → T005 (logging wraps the same write path).
- T002 covers T003/T004/T005 behavior; run it after each.
- T006/T007/T008 after implementation.

## Parallel opportunities

- T002 (test module) can be authored in parallel with T003 (impl) — different files.

## Implementation strategy (MVP)

MVP = Phase 3 (T002–T004): authoritative prune + atomicity. That alone closes the bug (US1 + US2).
Phase 4 (T005) adds the pruned-count log (US3). Phase 5 is docs + verification.
