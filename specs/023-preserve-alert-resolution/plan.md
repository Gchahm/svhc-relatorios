# Implementation Plan: Preserve user-set alert resolution state across analysis re-runs

**Branch**: `023-preserve-alert-resolution` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/023-preserve-alert-resolution/spec.md`

## Summary

The analysis pipeline writes alerts to D1 via delete-then-insert (per-period and a global
`document_overpayment` path). Each re-run therefore destroys the user-owned resolution fields
(`resolved`, `resolved_at`, `notes`). Because alert ids are deterministic, a re-emitted finding
maps to the same row id as the one being deleted. The fix: **before each delete, read the
resolution state of the rows about to be replaced, and graft it onto the freshly-built rows by
id** — so a re-emitted alert keeps its human disposition while findings that no longer fire are
still dropped. The hardcoded reset of resolution fields in `Alert.to_dict()` is removed in favor
of an explicit merge at write time.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/`, stdlib only, run via `uv`)
**Primary Dependencies**: `scripts/common/d1.py` (wrangler-CLI wrapper: `query`, `execute_sql`,
`upsert_tables`). No new pip/npm dependencies.
**Storage**: Cloudflare D1 (SQLite), table `alerts` — columns `resolved` (int 0/1), `resolved_at`
(timestamp ms, nullable), `notes` (text, nullable). No schema change.
**Testing**: Repository has no test framework configured (constitution III); verification is
manual via the analysis CLI + alert detail page.
**Target Platform**: Cloudflare Workers runtime (UI) + local/remote D1 via wrangler (pipeline).
**Project Type**: web (Next.js frontend + Python analysis pipeline). This change is **pipeline-only**.
**Performance Goals**: Negligible — one extra `SELECT` per writeback (per-period + once global).
**Constraints**: Writeback must stay idempotent; must not resurrect obsolete findings.
**Scale/Scope**: Tens–hundreds of alerts per period; trivial volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS — no schema change (the `alerts` columns already
  exist); no Drizzle migration needed. Python-side change only.
- **II. Cloudflare-Native Architecture**: PASS — all D1 access stays behind `scripts/common/d1.py`
  (`query` / `execute_sql` / `upsert_tables`); no direct connections.
- **III. Quality Gates Before Commit**: PASS — `pnpm lint` + `pnpm format` run before commit. No
  test framework; the spec does not request one. Manual verification documented in quickstart.
- **IV. Security & Auth by Default**: PASS — no route or auth surface changes; the PATCH endpoint
  is untouched.
- **V. Simplicity & Incremental Delivery**: PASS — the simplest fix (read-then-graft by id) reuses
  the existing delete-then-insert flow; no new abstractions, no new dependencies.

**Result**: All gates pass. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/023-preserve-alert-resolution/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (behavioral contract for the writeback)
│   └── alert-writeback.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── __init__.py      # run_analysis: per-period + global document_overpayment writeback (EDIT)
│   ├── models.py        # Alert.to_dict (EDIT: stop hardcoding resolution reset)
│   └── alerts_io.py     # NEW (optional): preserve_resolution_state helper, if extracted
└── common/
    └── d1.py            # query / execute_sql / upsert_tables (REUSE, no change)

src/                     # Frontend untouched; PATCH /api/alerts/[id] already persists state
```

**Structure Decision**: Single-module pipeline change confined to `scripts/analysis/`. The merge
logic is small enough to live inline in `run_analysis`, but is extracted into one tested-by-hand
helper (`preserve_resolution_state(target, where_clause, rows)` or equivalent) so both writeback
paths (per-period delete and global `document_overpayment` delete) share one implementation and
cannot drift — mirroring the feature-018 "single source of truth" discipline. The frontend and
the PATCH endpoint are already correct and are not modified.

## Complexity Tracking

> No constitution violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none)    | —          | —                                    |
