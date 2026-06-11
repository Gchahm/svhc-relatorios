# Implementation Plan: Preserve scraper-owned attachment columns across re-scrapes

**Branch**: `027-preserve-attachment-scrape-cols` | **Date**: 2026-06-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/027-preserve-attachment-scrape-cols/spec.md`

## Summary

Re-scraping an already-scraped period silently nulls the scraper-owned `attachments.file_path`
(R2 object-key linkage) and `attachments.content_hash` (shared-NF grouping key), because the
scraper emits the row with both NULL and writes it via `INSERT OR REPLACE` (delete-then-insert), so
the columns revert to NULL whenever images are not (re-)downloaded in the same run. Issue #33 already
moved `classified_at` off `attachments` into `attachment_state`, fixing the classification-state half
of BUG-001; this feature fixes the remaining `file_path`/`content_hash` clobbering.

Technical approach (per Clarifications): the fix lives **in the scraper's attachment write path**,
not in the generic SQL upsert. Before upserting a period's attachment rows, `_scrape_periodo` reads
the existing `id → (file_path, content_hash)` map for that period from D1 and merges it into the
freshly-scraped rows: any row whose freshly-scraped value is NULL inherits the existing non-NULL
value; a freshly-produced (download-succeeded) value always wins. The merge is a pure helper
(`_preserve_existing_attachment_cols`) so it is unit-testable without a live D1, mirroring the
existing `scripts/tests/test_attachment_state.py` pattern. The generic `INSERT OR REPLACE` generator
in `scripts/common/d1.py` is left untouched, so no other table's write semantics change.

## Technical Context

**Language/Version**: Python 3.12 (scraper under `scripts/scraper/`, run via `uv`)
**Primary Dependencies**: scraper — `playwright`, `python-dotenv`; D1/R2 access via
`scripts/common/d1.py` (wrangler-CLI wrapper). No new pip/npm dependencies.
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`), table `attachments` (read existing
`file_path`/`content_hash` for the period; write merged rows). R2 (`DOCUMENTS`) unchanged.
**Testing**: Python stdlib `unittest` (`python -m unittest discover -s scripts/tests -t scripts`).
**Target Platform**: Cloudflare Workers runtime for the app; the scraper/analysis CLIs run under
local Python via `uv` against D1/R2 through `wrangler` (local Miniflare or `--remote`).
**Project Type**: single (Python CLI pipeline; the Next.js frontend is untouched).
**Performance Goals**: One extra `SELECT id, file_path, content_hash FROM attachments` scoped to the
period being scraped, per period — negligible relative to the portal scrape itself.
**Constraints**: No schema migration (the columns already exist and stay on `attachments`). The
`attachments` table must remain an exact portal mirror plus its scraper-owned linkage columns
(mirror-table invariant). The shared `INSERT OR REPLACE` generator must not change behavior for any
other table.
**Scale/Scope**: ~tens of attachments per period; one helper function + one D1 read in the scraper.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. No schema change (columns already exist; they stay
  scraper-owned on `attachments`). No Drizzle/auth-schema edits. Python type hints maintained.
- **II. Cloudflare-Native Architecture**: PASS. D1 access stays behind `scripts/common/d1.py`
  (`query`/`upsert_tables`) — the sanctioned wrangler path; no direct connections. The frontend's
  `getDb()` path is untouched.
- **III. Quality Gates Before Commit**: PASS. `pnpm lint` + `pnpm format` run before commit
  (TS untouched, but gates still run). Tests are added (stdlib `unittest`) because this is a
  silent-data-loss bug where a regression guard is warranted, and the repo already has a
  `scripts/tests/` suite — consistent with the sibling #33 fix.
- **IV. Security & Auth by Default**: PASS. No routes, no auth surface, no secrets touched.
- **V. Simplicity & Incremental Delivery**: PASS. The simplest fix that satisfies the requirement:
  one pure merge helper + one scoped D1 read in the existing write path; no new abstraction, no
  schema change, no change to the shared SQL generator. YAGNI honored.

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/027-preserve-attachment-scrape-cols/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (function contract for the merge helper)
└── checklists/
    └── requirements.md  # Spec quality checklist (from specify)
```

### Source Code (repository root)

```text
scripts/
├── scraper/
│   └── runner.py                 # MODIFIED: _scrape_periodo reads existing attachment cols from
│                                  #   D1 and merges via the new pure helper before upsert; add
│                                  #   _preserve_existing_attachment_cols(...) helper.
├── common/
│   └── d1.py                     # UNCHANGED (generic INSERT OR REPLACE left intact)
└── tests/
    └── test_attachment_preserve.py  # NEW: unit tests for _preserve_existing_attachment_cols
```

**Structure Decision**: Single Python CLI project. The change is confined to
`scripts/scraper/runner.py` (the buggy write path) plus a new stdlib `unittest` module under
`scripts/tests/`. `scripts/common/d1.py`, the schema, the migrations, and the frontend are untouched.

## Complexity Tracking

> No constitution violations. Table intentionally empty.
