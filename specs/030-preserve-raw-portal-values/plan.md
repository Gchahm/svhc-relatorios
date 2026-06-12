# Implementation Plan: Preserve Raw Portal Values on Mirror Rows

**Branch**: `030-preserve-raw-portal-values` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/030-preserve-raw-portal-values/spec.md`

## Summary

Preserve the verbatim portal cell text for each ledger entry's amount and description on the
scraper-owned mirror `entries` rows (two new nullable TEXT columns), and harden the BRL currency
parser so an unparseable/NaN/inf cell fails **that row** (logged + skipped + recorded as a non-fatal
run note) instead of raising and aborting the whole period. Derived values (parsed `amount`,
normalized `description`, deterministic ids) are unchanged. No analysis/UI write paths touch the new
columns (mirror-table invariant).

## Technical Context

**Language/Version**: Python 3.12 (scraper under `scripts/scraper/`, run via `uv`); TypeScript 5 /
Drizzle ORM for the schema + migration.
**Primary Dependencies**: scraper — `playwright`, `python-dotenv`; D1/R2 access via the
`scripts/common/d1.py` wrangler-CLI wrapper; `drizzle-kit` for migration generation. **No new npm or
pip dependencies.**
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`), mirror table `entries` (two new nullable
columns `raw_amount`, `raw_description`). All other tables unchanged.
**Testing**: Python stdlib `unittest` under `scripts/tests/` (run `python -m unittest discover -s
scripts/tests -t scripts`). Pure parser/merge logic is unit-testable without playwright.
**Target Platform**: Cloudflare Workers (Next.js frontend, unchanged here) + local/remote D1 via
wrangler. Scraper runs in Node/Python toolchain locally.
**Project Type**: web (Next.js frontend + Python pipeline) — this feature touches the Python scraper
and the Drizzle schema/migration only; no frontend change.
**Performance Goals**: N/A — two TEXT columns and a try/except add negligible cost per row.
**Constraints**: Mirror-table invariant (feature 026) — only the scraper writes `entries`; analysis
issues zero writes to it. Preserve feature-027 (linkage-column preservation) and feature-028
(authoritative reconciliation) semantics unchanged. No new dependencies (constitution V).
**Scale/Scope**: Condominium ledger — hundreds of entries per period; dozens of periods.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. The two new columns are added to the Drizzle schema
  (`src/db/fiscal.schema.ts`) and a generated migration in `drizzle/`, never ad-hoc SQL. (Note: the
  generation uses the `node_modules/.bin/drizzle-kit` direct-binary workaround per MEMORY — `pnpm
  db:generate` fails in the sandbox on ignored builds.)
- **II. Cloudflare-Native Architecture** — PASS. No new bindings; D1 access stays through the existing
  `scripts/common/d1.py` wrapper (Python) and `getDb()` (TS, untouched).
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` before commit; new Python
  unit tests added under `scripts/tests/` for the pure parser logic (spec explicitly wants
  fail-the-row-not-the-period behavior verified).
- **IV. Security & Auth by Default** — PASS. No new routes or data exposure; raw text is already-visible
  portal data stored alongside its parse.
- **V. Simplicity & Incremental Delivery** — PASS. Two nullable columns + a tolerant parser; no new
  abstraction, dependency, or table. JSON-blob and integer-centavos alternatives explicitly rejected in
  the spec Assumptions (YAGNI / scope).

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/030-preserve-raw-portal-values/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (data contracts, not HTTP)
├── checklists/
│   └── requirements.md  # from specify
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
src/db/
└── fiscal.schema.ts                      # + entries.rawAmount, entries.rawDescription (nullable text)

drizzle/
└── 0013_<generated>.sql                  # ALTER TABLE entries ADD COLUMN raw_amount/raw_description
└── meta/                                  # drizzle-kit snapshot + journal (regenerated)

scripts/scraper/
├── extractors/
│   ├── demonstrativo.py                   # parse_brl → tolerant (returns float | None; reject NaN/inf);
│   │                                       #   demonstrativo caller treats None as fatal (report needs it)
│   └── lancamentos.py                     # keep raw "valor" text on each lancamento; parse via tolerant
│                                           #   parse_brl; carry valor_raw + descricao_raw through
└── runner.py                              # build entries with raw_amount/raw_description; skip rows whose
                                            #   amount fails to parse (warn + collect non-fatal note);
                                            #   surface notes on scrape_run.errors (IMP-002 channel)

scripts/tests/
└── test_parse_brl.py                      # NEW: tolerant parser unit tests (valid, NaN/inf, empty, junk)
```

**Structure Decision**: Web project; this feature is confined to the Python scraper
(`scripts/scraper/`) and the Drizzle schema + one migration. No frontend, API, or analysis-pipeline
code changes (the new columns are read-only/absent for analysis — mirror invariant). Tests live in the
existing `scripts/tests/` stdlib-unittest suite.

## Complexity Tracking

> No constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| (none)    | —          | —                                    |
