# Implementation Plan: Skip R2 image materialization in apply-extractions when no content_hash backfill is needed

**Branch**: `019-skip-apply-materialize` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-skip-apply-materialize/spec.md`

## Summary

`apply_extractions` (`scripts/analysis/extractions.py`) unconditionally calls
`materialize_period_images(periods, cache_dir, target)` on every run, which downloads the whole
period's page images from R2 and lazily backfills `attachments.content_hash`. Since feature 021
the apply step reads **no image bytes** itself — per-page extractions come from D1
(`D1ExtractionProvider`), page labels come from string-parsing `file_path` tokens
(`_page_label_from_path`), and NF grouping (`nf_groups.group_attachments`) prefers the persisted
`attachments.content_hash` column. The materialize call's *only* remaining job in the apply path
is hashing the small set of legacy/edge rows whose `content_hash` is NULL.

**Technical approach**: Add a tiny, testable predicate to `scripts/analysis/images.py` —
`attachments_needing_hash_backfill(periods, attachment_ids=None)` — that returns the in-scope
attachment ids that are page-bearing (`file_path` non-empty) **and** lack a `content_hash`. In
`apply_extractions`, compute that set first; only call `materialize_period_images` (scoped to those
ids, `backfill_hash=True`) when it is non-empty, otherwise skip the R2 round-trip entirely and log
the skip. `materialize_period_images` itself is **unchanged**, so the `docs-plan`/classify and
`mismatches`/review callsites keep materializing exactly as today. Grouping reads the
`content_hash` column for the already-keyed attachments. Behavior parity is preserved because the
guard only removes work that produced no output.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/`, stdlib only, run via `uv`)
**Primary Dependencies**: Python stdlib only; D1/R2 access via `scripts/common/d1.py` (wrangler-CLI wrapper). No new pip/npm deps.
**Storage**: Cloudflare D1 (`attachments`, `attachment_analyses`, `page_classifications`) + R2 (`DOCUMENTS` → `fiscal-documents`). Read-only schema (no migration).
**Testing**: No test framework configured (constitution III — tests OPTIONAL). Verification is a parity run of `apply-extractions` against a real local period.
**Target Platform**: Local dev (Miniflare-emulated D1/R2) and production (`--remote`) via wrangler.
**Project Type**: single (Python analysis pipeline within the Next.js repo)
**Performance Goals**: Steady-state `apply-extractions` performs **0** R2 image downloads when all page-bearing attachments are keyed (down from "all in-scope page images").
**Constraints**: Output parity with prior always-materialize behavior (persisted analyses + match flags byte-identical for the same input). Change confined to the apply path; classify/review materialization untouched.
**Scale/Scope**: ~100–200 attachments per period; the change is a guard around one function call plus one helper.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: No schema change — `attachments.content_hash` already
  exists; no Drizzle migration. Python type hints on the new helper match the module's style. ✅
- **II. Cloudflare-Native Architecture**: All D1/R2 access stays behind `scripts/common/d1.py`; the
  change *reduces* R2 access rather than adding a new path. ✅
- **III. Quality Gates Before Commit**: Run `pnpm lint` + `pnpm format` before commit. No test
  framework; verification is a manual parity run (documented in quickstart). ✅
- **IV. Security & Auth by Default**: No routes, no auth surface, no secrets touched. ✅
- **V. Simplicity & Incremental Delivery**: Smallest change that satisfies the requirement — one
  predicate + a guard; reuses the existing `materialize_period_images` (scoped) without changing its
  contract. The optional `backfill-content-hash` maintenance command is explicitly out of scope. ✅

**Result**: PASS. No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/019-skip-apply-materialize/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (function contract)
├── checklists/
│   └── requirements.md  # spec quality checklist (specify phase)
└── tasks.md             # Phase 2 output (speckit tasks — NOT created here)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── extractions.py   # apply_extractions — ADD the guard around materialize
│   ├── images.py        # ADD attachments_needing_hash_backfill() predicate; materialize_period_images UNCHANGED
│   └── nf_groups.py      # reference only — grouping already prefers the content_hash column
├── README.md             # docs update (apply step no longer always materializes)
└── pipeline-flow.md      # docs update (apply step R2 access is conditional)

CLAUDE.md                  # docs update if it describes the apply step's materialization
src/db/fiscal.schema.ts    # read-only reference (attachments.content_hash already exists)
```

**Structure Decision**: Single Python analysis package (`scripts/analysis/`). The change touches
exactly two source files — the guard in `extractions.py` and the predicate in `images.py` — plus
docs. The shared `materialize_period_images` keeps its current behavior so the other two callsites
(`plan_extractions`/`build_plan` and `summarize_mismatches`) are untouched.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
