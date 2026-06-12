# Implementation Plan: Deterministic Entry IDs for Duplicate Natural Keys

**Branch**: `034-deterministic-entry-id` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/034-deterministic-entry-id/spec.md`

## Summary

Make scraped ledger-entry ids deterministic regardless of portal row order when two or more
entries share an identical natural key. Today the disambiguating component of an entry id is an
order-dependent occurrence index; if the portal reorders duplicate rows between scrapes the
entries swap ids and every id-keyed dependent silently re-points to the sibling (issue #40 /
IMP-003).

Technical approach: extract the entry-id assignment into a **pure, stdlib-only, unit-tested**
module (`scripts/scraper/entry_ids.py`, mirroring `preserve.py`/`reconcile.py`/`consistency.py`).
For a natural-key group of size > 1 it derives the disambiguating component from an
**order-independent portal-native discriminator** built from the entry's `documento_ids` set
(sorted/deduped). Within a discriminator group that still collides (duplicates sharing the same
doc set, or no docs at all) it falls back to a 1-based occurrence index and records a fallback
note. A natural key that occurs **exactly once** in the period keeps the existing discriminator
`"1"` so its id is byte-identical to today's (no churn — FR-004). A second pure helper detects
**id drift** on re-scrape (a freshly minted id for a natural key that already exists in D1 under a
different id) and the runner surfaces it through the existing per-period scrape-notes channel
(the IMP-002 `consistency_notes` accumulator), consistent with the reconciliation philosophy.

## Technical Context

**Language/Version**: Python 3.12 (scraper under `scripts/scraper/`, run via `uv`)
**Primary Dependencies**: Scraper — `playwright`, `python-dotenv`. The new id logic is **stdlib
only** (`collections`, `hashlib` not even needed — string join via `common.det_id`), so it imports
without `playwright` and is directly unit-testable, exactly like `preserve.py`/`reconcile.py`.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`), mirror table `entries` (read-only here for
the pre-upsert natural-key read used by drift detection; no schema change, no migration). The
drift finding is surfaced through the run's `scrape_runs.errors`/notes text (existing), not a new
table.
**Testing**: `python -m unittest discover -s scripts/tests -t scripts` (stdlib `unittest`),
matching the existing pure-module tests (`test_reconcile.py`, `test_attachment_preserve.py`,
`test_scrape_consistency.py`, `test_parse_brl.py`).
**Target Platform**: Linux (scraper CLI via `uv`); the analysis/UI side is unaffected.
**Project Type**: Single project (Python scraper subsystem + Next.js app; only the scraper changes).
**Performance Goals**: Negligible — per period it adds one in-memory two-pass assignment over the
already-extracted lancamentos plus one read-only `SELECT id,date,description,amount,subcategory_id`
for the period (drift detection), bounded by the period's entry count (low thousands).
**Constraints**: No new pip/npm dependency, no D1 schema/migration change, no mirror-table write
beyond the existing `entries` upsert (the mirror invariant: only the scraper writes `entries`, and
this keeps that true). Ids stay deterministic + unique within a period (FR-007).
**Scale/Scope**: Duplicate natural keys are rare (4 groups in the current ~2780-entry dataset);
the change is bounded to those groups' ids — unique entries' ids are preserved.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No DB schema change, so no Drizzle migration is
  required (Principle I governs persisted-data schema changes; none here). The Python module uses
  type hints consistent with the existing pure modules.
- **II. Cloudflare-Native Architecture** — PASS. All D1 access continues through the
  `scripts/common/d1.py` wrangler wrapper (`query`/`upsert_tables`/`execute_sql`); no direct
  connections, no new binding.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint`/`pnpm format` run before commit (no TS
  changed, but the gate is still honored). Automated tests ARE added because the spec explicitly
  requests them (SC-005) — stdlib `unittest`, the repo's established pure-module test pattern.
- **IV. Security & Auth by Default** — PASS. No route/auth surface touched.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the existing deterministic-id helper,
  the existing notes channel, and the established pure-module-+-runner-glue seam; adds no new
  table, dependency, or abstraction. The change is a single, bounded refactor of one code path.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/034-deterministic-entry-id/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (pure-function contracts)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── scraper/
│   ├── entry_ids.py        # NEW — pure, stdlib-only, unit-tested: discriminator + id assignment + drift detection
│   └── runner.py           # MODIFIED — entry build calls assign_entry_ids; drift read + note in the success path
├── tests/
│   └── test_entry_ids.py   # NEW — unit tests for entry_ids.py (order-independence, fallback, drift, no-churn)
```

**Structure Decision**: Single-project layout. The work lives entirely in the Python scraper
subsystem. The id-derivation logic moves into a new pure module `scripts/scraper/entry_ids.py`
(the established pattern for testable, playwright-free scraper logic: `preserve.py`,
`reconcile.py`, `consistency.py`). `runner.py` keeps the impure pieces: it calls the pure
`assign_entry_ids` during the entry build, performs the pre-upsert read-only D1 query for drift
detection, and threads the fallback + drift notes through the existing `consistency_notes`
channel. No frontend, no schema, no migration.

## Complexity Tracking

> No constitution violations — section intentionally empty.
