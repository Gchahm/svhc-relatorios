# Implementation Plan: Prune stale documents and links after re-classification

**Branch**: `025-prune-stale-documents` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/025-prune-stale-documents/spec.md`

## Summary

`build_documents` (`scripts/analysis/documents.py`) is upsert-only: it INSERT-OR-REPLACEs the
documents/links it derives from the current `attachment_analyses` but never removes rows that the
current analyses no longer produce. A re-classification that changes an analysis's `(number, CNPJ)`
key therefore leaves a zombie document + entry link, distorting `/dashboard/documents` and possibly
firing a false `document_overpayment` alert. Fix: make the write **authoritative**. The build
already computes the complete desired global state, so prune any document/link whose deterministic id
is not in this run's desired sets, and fold the prune + the upsert into a **single atomic D1 batch**
(one `execute_sql`), mirroring the alert/attachment writebacks (feature 024). Also report pruned
counts in the run log.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/`, stdlib only, run via `uv`)
**Primary Dependencies**: `scripts/common/d1.py` (wrangler-CLI wrapper: `query`, `execute_sql`,
`upsert_sql`, `build_sql`); `scripts/common.det_id` / `now_ms`. No new pip/npm deps.
**Storage**: Cloudflare D1 (SQLite) — tables `documents`, `document_entries` (written), plus
`attachment_analyses`/`attachments`/`entries` read. No schema change (no migration).
**Testing**: stdlib `unittest` in `scripts/tests/` (`python -m unittest discover -s scripts/tests -t scripts`)
**Target Platform**: Cloudflare Workers runtime (data); the CLI runs in Node/uv locally + CI
**Project Type**: single (Python analysis pipeline alongside the Next.js app)
**Performance Goals**: N/A — small derived sets (tens–hundreds of documents); one extra D1 read + a
batched write per build.
**Constraints**: the prune + upsert MUST be one atomic batch (FR-005); the prune MUST be global (FR-006).
**Scale/Scope**: One function changed (`build_documents`) + one new unit test module; documents/links
counts are small.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No schema change — the write logic changes only. `documents`
  and `document_entries` remain exactly as the Drizzle schema defines them; no ad-hoc column added.
  PASS.
- **II. Cloudflare-Native Architecture**: All D1 access stays behind `scripts/common/d1.py` (the
  wrangler wrapper); no direct connection. PASS.
- **III. Quality Gates Before Commit**: Python-only change; `pnpm lint`/`pnpm format` cover the TS app
  (unchanged) and are run before commit. The spec requests unit tests; they are added under
  `scripts/tests/` and MUST pass. PASS.
- **IV. Security & Auth by Default**: No new route or data exposure; the documents page/API are
  unchanged. PASS.
- **V. Simplicity & Incremental Delivery**: The change reuses the existing `upsert_sql` + `execute_sql`
  seam and the established delete-then-insert atomic-batch idiom; no new abstraction. PASS.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/025-prune-stale-documents/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the build_documents internal contract)
├── checklists/
│   └── requirements.md  # spec quality checklist (from specify)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   └── documents.py          # CHANGED: build_documents now prunes stale rows + batches atomically
├── common/
│   └── d1.py                 # reused unchanged (query / execute_sql / upsert_sql / build_sql)
└── tests/
    ├── test_document_prune.py   # NEW: prune/atomicity unit tests (mirrors test_alert_writeback_atomic.py)
    └── ...                       # existing tests unchanged
```

**Structure Decision**: Single Python analysis module. The entire behavior change is contained in
`scripts/analysis/documents.py:build_documents`; `scripts/common/d1.py` already exposes every seam
needed (`query` to read existing ids, `build_sql`/`upsert_sql` to generate the INSERTs, `execute_sql`
to run a combined batch). A new stdlib `unittest` module verifies the prune + atomic-batch behavior.

## Complexity Tracking

> No constitution violations — section intentionally empty.
