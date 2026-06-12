# Implementation Plan: Prune consumed and stale `page_classifications` staging rows

**Branch**: `035-prune-staging-rows` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/035-prune-staging-rows/spec.md`

## Summary

The `page_classifications` staging table never deletes rows, so it grows unbounded and can hold
stale rows that a future `apply-extractions` could re-apply. The fix adds two cleanup hooks, both
using the analysis-owned tables only (no mirror writes, no schema change):

1. **Apply consumes** — `apply-extractions`, after an attachment's authoritative
   `attachment_analyses` write lands, deletes that attachment's staging rows. This is folded into
   the existing atomic `_merge_and_write` batch (the delete commits with the insert, never before),
   so a failed write leaves the staging rows intact and the attachment pending.
2. **`mark-pending` invalidates** — when an attachment is re-queued, its staging rows are deleted
   alongside clearing `attachment_state.classified_at`, so reclassification starts clean.

The deletion SQL is a small pure helper (`_prune_page_classifications_sql(attachment_ids)`) added to
`page_classifications.py`, composed into the callers' single `execute_sql` batch — consistent with
the project's atomic delete-then-insert idiom.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/analysis/`, run via `uv`); the
pruning helper is stdlib-only.  
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (the `wrangler`-CLI wrapper:
`execute_sql` / `upsert_sql`), `scripts/common` (`det_id`, `now_ms`). No new pip/npm deps.  
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). Writes (DELETEs) the analysis-owned
`page_classifications` table; the existing `attachment_analyses` + `attachment_state` writes are
unchanged. No mirror-table write. No new table/column/migration.  
**Testing**: stdlib `unittest` under `scripts/tests/` (run `python -m unittest discover -s scripts/tests -t scripts`). The SQL-generating helper and the batch composition are unit-testable without a live D1.  
**Target Platform**: Cloudflare Workers runtime for the app (unchanged); the pipeline runs locally/CI via `uv` + `wrangler`.  
**Project Type**: single (Python analysis pipeline under `scripts/`; no frontend change).  
**Performance Goals**: N/A — DELETEs are scoped by `attachment_id` and folded into batches already issued; no added round trip on the apply path.  
**Constraints**: Mirror invariant (only the scraper writes `entries`/`attachments`/`accountability_reports`); atomic delete-then-insert writebacks (one `execute_sql` batch, never two calls).  
**Scale/Scope**: Two functions touched (`apply_extractions` via `_merge_and_write`, `mark_pending`) + one new pure helper; staging table is small today (hundreds of rows).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No schema change → no Drizzle migration. The helper has typed signatures. PASS.
- **II. Cloudflare-Native Architecture**: All D1 access stays through `scripts/common/d1.py` (the established `wrangler` wrapper); no direct connections. PASS.
- **III. Quality Gates Before Commit**: `pnpm lint`/`pnpm format` apply to TS only (none changed); Python is untouched by those gates. Tests are OPTIONAL but this spec explicitly adds unit tests (atomicity + scoping are correctness-critical), which MUST pass before merge. PASS.
- **IV. Security & Auth by Default**: No route/auth surface touched. PASS.
- **V. Simplicity & Incremental Delivery**: Smallest change that satisfies the requirement — one pure SQL helper reused by both hooks, no new command, no orphan-sweep abstraction. Two independently testable stories. PASS.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/035-prune-staging-rows/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── prune_staging.md
├── checklists/
│   └── requirements.md  # from specify
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── page_classifications.py   # ADD: _prune_page_classifications_sql(attachment_ids) -> str (pure)
│   ├── attachments.py            # EDIT: _merge_and_write folds the staging-prune DELETE into its atomic batch
│   └── extractions.py            # EDIT: mark_pending also prunes staging rows for the re-queued attachments
├── common/
│   └── d1.py                     # unchanged (reused: execute_sql, _escape_sql conventions)
└── tests/
    └── test_prune_staging.py     # ADD: unit tests for the helper + batch composition
```

**Structure Decision**: Single Python project under `scripts/`. The new logic lives next to the
table it owns (`page_classifications.py`), and the two callers compose its SQL into batches they
already issue. No frontend, schema, or migration change.

## Complexity Tracking

> No constitution violations — table intentionally empty.
