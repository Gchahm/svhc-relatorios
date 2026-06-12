# Implementation Plan: Reconcile Portal Deletions on Period Re-scrape

**Branch**: `028-reconcile-portal-deletions` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-reconcile-portal-deletions/spec.md`

## Summary

Make a period re-scrape authoritative: after a period's rows are upserted into D1, compute the
mirror rows that exist in D1 for the period but were NOT in the just-scraped set (per `entries`,
`attachments`, `category_subtotals`, `approvers`), hard-delete them, cascade-clean their
analysis-owned dependents (`attachment_state`, `attachment_analyses`, `attachment_analysis_records`,
`page_classifications`, `document_entries`), and raise one idempotent `critical`
`portal_row_vanished` alert per period carrying the deleted rows' frozen values as evidence. All
deletes + the alert write go in one atomic D1 batch. The mirror tables stay pure portal mirrors (no
soft-delete column); the evidence lives in the analysis-owned `alerts` table.

## Technical Context

**Language/Version**: Python 3.12 (analysis/scraper CLIs under `scripts/`, run via `uv`)
**Primary Dependencies**: Python **stdlib only** for the reconciliation logic; D1 access via the
existing `scripts/common/d1.py` wrangler-CLI wrapper (`query` / `execute_sql` / `upsert_sql`). The
scraper side already imports `playwright`; the new reconciliation merge module is kept
playwright-free so it is unit-testable directly (mirrors `scripts/scraper/preserve.py`).
**Storage**: Cloudflare D1 (SQLite). Tables written: `entries`, `attachments`,
`category_subtotals`, `approvers` (DELETE), the five analysis-owned dependents (DELETE), `alerts`
(DELETE + INSERT). All reads via `d1.query`. **No Drizzle migration** — `alerts.metadata` (JSON
text) and all dependent tables already exist.
**Testing**: stdlib `unittest` under `scripts/tests/` (run `python -m unittest discover -s
scripts/tests -t scripts`), matching the existing `test_attachment_preserve.py` /
`test_*_writeback_atomic.py` convention. Tests are explicitly requested by this spec (FR-010).
**Target Platform**: Local dev D1 (Miniflare) by default; `--remote` for production — same `target`
seam the scrape already threads.
**Project Type**: Single project (Python pipeline + Next.js frontend; this feature touches only the
Python scrape path — no frontend change, the alert renders through the existing alerts UI).
**Performance Goals**: Negligible — one extra `d1.query` per reconciled table per period + one
batched `execute_sql`. Re-scrape is an offline, low-frequency operation.
**Constraints**: No new pip/npm dependency. The reconcile delete + alert write must be ONE D1 batch
(atomicity, FR-009). Reconciliation must run only on a successful period scrape (FR-008). Must not
touch analysis state of surviving rows or other periods (FR-005).
**Scale/Scope**: A period has up to a few thousand entries (2026-01 has ~2.7k); set-diff and
batched DELETEs are trivial at that scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No schema change — no Drizzle migration needed
  (`alerts.metadata` and the dependent tables already exist). The mirror-table invariant is
  *strengthened* (re-scrape now makes the mirror exact). PASS.
- **II. Cloudflare-Native Architecture**: All D1 access goes through the existing
  `scripts/common/d1.py` wrangler wrapper with an explicit `target`; no new binding, no direct
  connection. PASS.
- **III. Quality Gates Before Commit**: Python pipeline; `pnpm lint`/`pnpm format` cover the TS side
  (untouched). New stdlib `unittest` tests added per FR-010 and must pass. PASS.
- **IV. Security & Auth by Default**: No new route or exposed endpoint; the alert flows through the
  existing auth-gated alerts API/UI. PASS.
- **V. Simplicity & Incremental Delivery**: One pure merge module + one wiring call in the scrape
  runner; reuses the established atomic delete-then-insert seam (`upsert_sql` + `execute_sql`) and
  the `alerts` table. No new abstraction. PASS.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/028-reconcile-portal-deletions/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── reconcile.md     # Phase 1: the pure-function + alert-payload contract
├── checklists/
│   └── requirements.md  # spec quality checklist (from specify)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── scraper/
│   ├── runner.py         # MODIFIED: after a period's upsert succeeds, read existing ids,
│   │                     #   diff vs scraped ids, build + execute the reconcile batch
│   └── reconcile.py      # NEW: pure, playwright-free module — build_reconciliation(...) →
│                         #   (sql_batch, alert_payload | None). Mirrors preserve.py.
├── common/
│   └── d1.py             # REUSED: query / execute_sql / upsert_sql (no change expected)
└── tests/
    └── test_reconcile.py # NEW: stdlib unittest for build_reconciliation (FR-010): no-op,
                          #   stale diff, cascade SQL, atomic single-batch, alert payload,
                          #   idempotent delete-then-insert, surviving-rows-untouched.
```

**Structure Decision**: Single project, Python scrape-path only. The reconciliation logic is a new
pure module `scripts/scraper/reconcile.py` (no playwright import, stdlib only) so it is unit-testable
exactly like `scripts/scraper/preserve.py`; `runner.py` does the impure parts (read existing ids from
D1, execute the batch). No frontend files change — the new `portal_row_vanished` alert is rendered by
the existing `/api/alerts` + `AlertsClient` path (its `metadata.entry_ids` deep-link convention
already exists, feature 018).

## Complexity Tracking

No constitution violations — section intentionally empty.
