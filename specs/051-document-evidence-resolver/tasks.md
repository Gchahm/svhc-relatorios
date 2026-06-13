# Tasks: Document→attachment(s) evidence resolver for the triage agent

**Feature**: `051-document-evidence-resolver` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Single user story (P1). All tasks are small and mostly sequential (one module + one subparser + one test).

## Phase 1: Setup

- [x] T001 Confirm branch `051-document-evidence-resolver` is checked out and the analysis CLI runs
  (`cd scripts && uv run python -m analysis --help`). No new dependency.

## Phase 2: Foundational — resolver core (blocks the CLI wiring)

- [x] T002 In `scripts/analysis/documents.py`, add a pure helper
  `resolve_document_attachment_ids(document_id, target)` that (a) verifies the document exists
  (`SELECT id FROM documents WHERE id = ?`), raising a clear error (e.g. `KeyError`/`ValueError`) when
  it does not (FR-005), and (b) returns the **sorted, distinct, non-NULL** set of
  `source_attachment_id` from `document_entries WHERE document_id = ?` (FR-002). Read-only.
  Properly escape the id for the `wrangler`-CLI SQL (mirror the escaping used elsewhere in the file).

- [x] T003 In `scripts/analysis/documents.py`, add `document_evidence(document_id, target, cache_dir)`
  that calls `resolve_document_attachment_ids`, then `summarize_mismatches(target,
  attachment_ids=<resolved>, cache_dir=cache_dir)` (imported lazily/at top to avoid a cycle — note
  `extractions.py` does not import `documents.py`), and returns
  `{"document_id", "attachment_ids", "findings"}` (FR-003, FR-006, FR-008). When the resolved set is
  empty, pass an empty list and return empty findings rather than scoping to "all".

## Phase 3: User Story 1 — CLI entry point (P1)

**Goal**: `python -m analysis document-evidence --id <id>` prints the JSON evidence object.
**Independent test**: run against a seeded over-claim document → findings with `page_refs`; run with
an unknown id → non-zero exit + message.

- [x] T004 In `scripts/analysis/__main__.py`, add the `document-evidence` subparser: `--id` (required),
  `--remote` (flag), `--cache-dir` (default `CACHE_DIR`). It is GLOBAL (no `--periodo`; a document is
  not period-scoped). Update the module docstring's command list.

- [x] T005 In `scripts/analysis/__main__.py` dispatch, handle `command == "document-evidence"`: call
  `document_evidence(...)`, `print(json.dumps(result, ensure_ascii=False, indent=2))` on success;
  on the not-found error, `print("error: document not found: <id>", file=sys.stderr)` + `sys.exit(1)`
  (matches the `record-classification` error pattern). Import `document_evidence` from `.documents`.

## Phase 4: Tests & polish

- [x] T006 Add `scripts/tests/test_document_evidence.py` (stdlib `unittest`, no mocks framework):
  drive `resolve_document_attachment_ids` + `document_evidence` with an injected fake `query`
  (via `unittest.mock.patch` on `documents.d1.query`) and a patched `summarize_mismatches`, asserting
  (1) distinct/sorted/non-NULL resolution, (2) unknown id raises, (3) empty source set ⇒ empty
  findings, (4) findings are passed through unchanged. Run `cd scripts && python -m unittest
  discover -s tests -t .`.

- [x] T007 Run `pnpm lint`, `pnpm format` (and `pnpm test:py`); fix any issues. Run `prettier --write`
  over the touched markdown (CI gates `prettier --check .` over docs).

- [x] T008 Manual verify per quickstart.md against local D1: unknown id → exit 1; a seeded document
  with findings → JSON with `attachment_ids` + `findings[].page_refs[].read_path`. Confirm zero D1
  writes (diff row counts before/after).

## Dependencies

- T002 → T003 → (T004, T005) → T006/T008. T007 after implementation.

## MVP

T002–T005 deliver the working command; T006–T008 harden + verify.
