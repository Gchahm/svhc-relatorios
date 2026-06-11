# Implementation Plan: Analysis-owned attachment state table

**Branch**: `026-attachment-state-table` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/026-attachment-state-table/spec.md`

## Summary

The analysis pipeline currently mutates the mirror table `attachments` in three places
(stamping `classified_at`, clearing it for re-queue, and backfilling `content_hash`),
which breaks the "exact copy of brcondos" invariant and lets the scraper's full-row
replace race with analysis state. This feature moves the classification state to a new
analysis-owned table `attachment_state(attachment_id PK, classified_at)`, rewrites the
three pipeline writes (the `classified_at` stamp in `apply-extractions`, the `mark-pending`
clear, and the pending-set read in `select_work`) to use it, and **removes** the
analysis-side `content_hash` backfill — leaving `content_hash` as a scraper-owned column on
`attachments` (backfilled only by the scraper's image-download path, which already does so).
A Drizzle migration creates the table, copies existing `classified_at` values over, and drops
the `attachments.classified_at` column. Net effect: **only the scraper writes `attachments`**.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/`, stdlib only, run via `uv`); TypeScript 5 / Drizzle ORM for the schema + migration. No frontend change.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (wrangler-CLI wrapper: `query`/`execute_sql`/`upsert_sql`/`upsert_tables`); Drizzle ORM (`drizzle-kit` for migration generation). **No new npm or pip dependencies.**
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). New table `attachment_state`. Existing tables `attachments` (mirror — becomes write-once by scraper), `attachment_analyses`, `entries`, `accountability_reports` read here.
**Testing**: stdlib `unittest` under `scripts/tests/` (run `python -m unittest discover -s scripts/tests -t scripts`). The repo has no JS test framework; verification of the migration + pipeline is via the local D1 and the running app (Constitution III).
**Target Platform**: Cloudflare Workers runtime (frontend, unaffected); Python analysis CLI on Linux/macOS via `uv`.
**Project Type**: web (Next.js frontend + Python analysis/scraper pipeline) — only the pipeline + schema/migration are touched.
**Performance Goals**: No regression. The pending-set selection adds one LEFT JOIN to `attachment_state`; per-period attachment counts are small (tens–hundreds), so this is negligible.
**Constraints**: Migration must preserve existing `classified_at` values (no spurious re-classification, SC-003) and existing `content_hash` values (SC-004). The classified stamp must remain atomic with the analysis-rows insert (FR-004). D1 statements go through `scripts/common/d1.py` (no direct connections).
**Scale/Scope**: ~3 Python files (`attachments.py`, `extractions.py`, `images.py`) + loader query, one Drizzle schema edit, one generated migration, plus doc/CLAUDE.md updates. No UI/API surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. The schema change flows through the
  Drizzle schema (`src/db/fiscal.schema.ts`) + `pnpm db:generate` (a committed migration in
  `drizzle/`), never hand-edited SQL. `auth.schema.ts` is untouched. The Python side uses the
  same generated table; no ad-hoc DDL outside the migration.
- **II. Cloudflare-Native Architecture** — PASS. All D1 access stays behind
  `scripts/common/d1.py` (the pipeline's equivalent of `getDb()` for the wrangler CLI). No new
  binding; `attachment_state` lives in the existing `DATABASE` D1. No frontend/runtime binding
  change.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` run before commit;
  the migration + regenerated schema are committed. Python `unittest` added for the new
  state-table read/write seam (existing tests must keep passing). Manual verification against
  local D1 + the running app is recorded in the PR body (the change is not user-facing, so the
  verification confirms the pipeline still classifies/marks-pending and the UI still renders).
- **IV. Security & Auth by Default** — PASS. No new route or data exposure; `attachment_state`
  is analysis-internal and not read by any API route or client.
- **V. Simplicity & Incremental Delivery** — PASS. The simplest table that satisfies the
  invariant (one PK + one timestamp column); `content_hash` is *not* moved (avoids churn and
  keeps grouping reads on the same column), per the spec's documented assumption. The three
  user stories are independently testable and ordered P1, P1, P2.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/026-attachment-state-table/
├── plan.md              # This file
├── spec.md              # Feature spec (complete)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── attachment-state.md   # The internal "contract": table shape + CLI/loader behavior
├── checklists/
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (speckit tasks — NOT created here)
```

### Source Code (repository root)

```text
src/db/
└── fiscal.schema.ts            # ADD `attachmentState` table; REMOVE `classifiedAt` from `attachments`

drizzle/
└── 0012_*.sql                  # GENERATED migration: create attachment_state, copy classified_at, drop column

scripts/analysis/
├── attachments.py              # _merge_and_write: stamp attachment_state (atomic batch); select_work: LEFT JOIN attachment_state
├── extractions.py              # mark_pending: write attachment_state instead of UPDATE attachments
├── images.py                   # REMOVE _backfill_content_hashes + its call; keep in-memory hash for grouping
└── loader.py                   # attachment dicts carry classified_at from attachment_state (LEFT JOIN)

scripts/tests/
└── test_attachment_state.py    # NEW: pending-set semantics, atomic stamp, mark-pending, no attachments write

CLAUDE.md / AGENTS.md           # Update the invariant + pipeline-write notes to reference attachment_state
```

**Structure Decision**: Reuse the existing pipeline layout. The state lives in a new D1
table defined in `src/db/fiscal.schema.ts` (schema is the source of truth, Constitution I) and
created by a generated Drizzle migration. The Python pipeline reads/writes it exclusively
through `scripts/common/d1.py`. No new directories.

## Complexity Tracking

> No Constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
