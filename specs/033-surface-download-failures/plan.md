# Implementation Plan: Surface partial attachment-download failures

**Branch**: `033-surface-download-failures` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/033-surface-download-failures/spec.md`

## Summary

Make partial attachment-download failures visible at three levels. (1) During a download-enabled
scrape, track per period the attachments that were attempted but produced no pages (still
`file_path IS NULL` after the in-run download + the existing column-preservation merge), record a
human/grep-queryable note on the run record via the existing non-fatal notes channel, emit a final
run-log summary, and set the run status to `partial` when any failed and no fatal error occurred.
(2) On the analysis side, add a new `attachment_not_downloaded` (`warning`) alert — one per
attachment whose mirror row references pages it cannot show (`file_path IS NULL`/empty) — produced in
`run_advanced`, so it rides the existing per-period delete-then-insert alert writeback that makes it
idempotent and self-clearing once the pages are fetched.

No schema migration, no new dependency, no mirror-table write.

## Technical Context

**Language/Version**: Python 3.12 (scraper `scripts/scraper/`, analysis `scripts/analysis/`, run via
`uv`). The pure helpers are stdlib-only so they import without `playwright`.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (wrangler-CLI wrapper) for the
alerts write (analysis side, already wired); scraper uses `playwright` (unchanged). No new pip/npm
deps.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). Reads the mirror `attachments` (existing).
Writes the analysis-owned `alerts` table (existing path) and the `scrape_runs.errors` free-form
field (existing). No new column, no migration.
**Testing**: stdlib `unittest` under `scripts/tests/` (`python -m unittest discover -s scripts/tests
-t scripts`). New pure helpers are unit-tested; the run-orchestration and the analysis check that
reuse them are validated end-to-end against local D1.
**Target Platform**: CLI pipeline (scraper + analysis) over Cloudflare D1/R2; Next.js dashboard
renders the alert generically (no UI change).
**Project Type**: Single repo, Python pipeline + TS frontend. This feature touches only the Python
pipeline.
**Performance Goals**: N/A (negligible — failure tracking is a set membership over a period's
attachments already in memory; the alert is one extra pass over `period.attachments`).
**Constraints**: Must preserve the mirror invariant (scraper-only writes to `attachments`; the alert
is analysis-owned). Must not flip status to `error` for a non-fatal partial download. The pure logic
must be importable without `playwright`.
**Scale/Scope**: A period has at most a few hundred attachments; a run a handful of periods.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No schema change (notes channel + existing `alerts`
  table). No Drizzle migration needed. PASS.
- **II. Cloudflare-Native Architecture**: All D1 access stays through `scripts/common/d1.py`; the
  alert writeback reuses the existing `run_analysis` per-period batch. PASS.
- **III. Quality Gates Before Commit**: New stdlib `unittest` cases for the pure helpers; `pnpm lint`
  + `pnpm format` are no-ops for Python but run anyway (no TS changes). PASS.
- **IV. Security & Auth by Default**: No new surface, no new endpoint. The alert rides the existing
  auth-gated `/api/alerts` + dashboard. PASS.
- **V. Simplicity & Incremental Delivery**: Two small, independent slices (run-level signal; alert),
  each reusing an established convention (consistency-notes channel; per-(attachment,kind) alert with
  deterministic id). No new table, no new CLI command. PASS.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/033-surface-download-failures/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the alert "contract" + run-note format)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── scraper/
│   ├── runner.py                 # MODIFIED: _scrape_periodo tracks per-period failed attachment
│   │                             #   ids; run_scrape aggregates them into a note + the `partial`
│   │                             #   status; run_download_docs already updates D1 (unchanged).
│   └── download_failures.py      # NEW (pure, stdlib-only): compute failed-attachment id set for a
│                                 #   period + format the run-level summary note. Importable without
│                                 #   playwright; unit-tested.
├── analysis/
│   └── checks/
│       └── attachments.py        # MODIFIED: add check_attachment_not_downloaded(period) emitting
│                                 #   one `attachment_not_downloaded` alert per file_path-less
│                                 #   attachment; wired into run_advanced (advanced.py).
│   └── checks/advanced.py        # MODIFIED: call the new check in run_advanced.
└── tests/
    ├── test_download_failures.py # NEW: pure-helper unit tests (id set + note formatting + status).
    └── test_attachment_not_downloaded.py  # NEW: the analysis check (one alert per missing,
                                            #   idempotent id, clears when file_path present).
```

**Structure Decision**: Single repo, Python pipeline. The scraper-side logic that decides "which
attachments failed this run" and "what status/note results" is factored into a pure, playwright-free
module (`scripts/scraper/download_failures.py`) mirroring the established `preserve.py` /
`reconcile.py` / `consistency.py` pattern, so it is unit-testable without a browser. The analysis
alert is a new function in the existing `checks/attachments.py` (where the sibling per-attachment
alerts live) wired into `run_advanced`, so it inherits the existing per-period idempotent
delete-then-insert writeback with zero new writeback code.

## Complexity Tracking

> No constitution violations — section intentionally empty.
