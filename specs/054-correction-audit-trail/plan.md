# Implementation Plan: Data-correction audit trail + reversibility (autonomous-correction safety net)

**Branch**: `054-correction-audit-trail` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/054-correction-audit-trail/spec.md`

## Summary

Add the autonomous-correction safety net the triage agent (TRIAGE-004) will depend on: a durable,
queryable, analysis-owned `data_corrections` store, a composite **apply-correction** operation that
records each field change (`{attachment_id, page, field, from, to, evidence, agent, timestamp}`),
gates the write on **verify-after** (the targeted finding cleared AND no new finding appeared for the
affected scope, else roll back / flag), and a human-runnable **list** + **undo** of any applied
correction. The correction primitive reuses the existing `record-classification` staging write +
staging-driven `apply-extractions` (feature 050) propagation; this feature wraps that primitive with
the audit + verify-after + restore machinery. No new dependency; one new D1 table + migration.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/analysis/`, run via `uv`) for the
store + correction operations; TypeScript 5 / Drizzle ORM for the schema + migration only.
**Primary Dependencies**: Existing only — `scripts/common/d1.py` (the `wrangler`-CLI wrapper:
`query` / `execute_sql` / `upsert_sql` / `upsert_tables`), `scripts/common` (`det_id`, `now_ms`), the
existing `record_classification` / `D1ExtractionProvider` staging seam, `apply_extractions` (feature
050 staging-driven), `summarize_mismatches` (the single-source finding detector), `build_documents`,
`run_analysis`. Drizzle ORM (`drizzle-kit`) for the migration. **No new npm or pip dependency.**
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). **New table `data_corrections`** (analysis-
owned, like `attachment_state` / `page_classifications`). Reads `page_classifications`,
`attachment_analyses`, `attachment_analysis_records`, `attachments`, `alerts`, `entries` (existing).
One Drizzle migration. No mirror-table write.
**Testing**: Python stdlib `unittest`. Pure-seam unit tests under `scripts/tests/` (the store SQL
builders, the verify-after diff, the field-change/`from`-snapshot computation, status-transition
guards). Real-D1 idempotence/roundtrip in `scripts/integration_tests/` (apply → verify pass/fail →
rollback → list → undo against seeded local Miniflare D1).
**Target Platform**: CLI on the dev container / CI; D1 local Miniflare by default, `--remote` opt-in.
**Project Type**: single (Python analysis package + a Drizzle schema/migration; no frontend).
**Performance Goals**: N/A (a correction touches one attachment + its NF siblings; verify-after is
one scoped `summarize_mismatches` read). Not latency-sensitive.
**Constraints**: `scripts/analysis/` stays **stdlib-only** (no new pip dep). The correction store is
analysis-owned — it NEVER writes the mirror tables (`entries`/`attachments`/`accountability_reports`).
Writebacks that delete-then-insert MUST be one atomic `execute_sql` batch (feature 024 convention).
`--remote` is explicit, never implicit (FR-011).
**Scale/Scope**: Small — one new table, ~3 CLI subcommands (`apply-correction`, `list-corrections`,
`undo-correction`; the store + verify-after are library functions reused by the future agent).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. The one schema change (new `data_corrections` table)
  flows through `pnpm db:generate` + a committed Drizzle migration; no hand-edited SQL migration, no
  ad-hoc DDL. The Python side reads/writes via the existing typed `d1.py` wrapper.
- **II. Cloudflare-Native Architecture** — PASS. All D1 access goes through `scripts/common/d1.py`
  (the established `wrangler` wrapper); no direct connections. No new binding needed.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` before commit; this spec
  explicitly requests tests (US1–US3 independent tests), added as stdlib `unittest` (unit) +
  integration suites, consistent with the project's existing Python test layout.
- **IV. Security & Auth by Default** — PASS. No new route, no new public surface. CLI-only; the
  `--remote` opt-in keeps production writes explicit. No secrets introduced.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the existing staging/apply/finding-detector
  seams rather than inventing a parallel correction path; one table, a handful of pure functions, no
  new abstraction beyond the store. Delivered as independently testable slices (store → apply+verify
  → list/undo).

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/054-correction-audit-trail/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contracts)
│   └── corrections-cli.md
├── checklists/
│   └── requirements.md  # spec quality checklist (from specify)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/db/
└── fiscal.schema.ts             # + data_corrections table (Drizzle)
drizzle/
└── 0014_*.sql                   # generated migration creating data_corrections

scripts/analysis/
├── corrections.py               # NEW: the store (record/list/load) + apply-correction
│                                #   (snapshot → stage → propagate → verify-after → commit/rollback)
│                                #   + undo-correction. Pure-where-possible; D1 via common.d1.
├── extractions.py               # (reused: record_classification path, apply_extractions, summarize_mismatches)
├── page_classifications.py      # (reused: staging read/write seam)
└── __main__.py                  # + apply-correction / list-corrections / undo-correction subcommands

scripts/tests/
└── test_corrections.py          # NEW unit: SQL builders, from-snapshot diff, verify-after diff,
                                 #   status-transition guards, no-op + fail-closed paths
scripts/integration_tests/
└── test_corrections_d1.py       # NEW integration: apply(pass)→list→undo, apply(fail)→rollback,
                                 #   cache-wipe survives, undo-guards — against seeded local D1
```

**Structure Decision**: Single-project layout. The store + operations live in a new
`scripts/analysis/corrections.py` (mirrors how `verdicts.py`, `documents.py`, `page_classifications.py`
each own one concern), wired into the analysis CLI. The only TS/Drizzle change is the new table +
migration (Principle I). Verify-after, the finding detector, and propagation are all reused — no new
analysis path.

## Complexity Tracking

> No constitution violations — section intentionally empty.
