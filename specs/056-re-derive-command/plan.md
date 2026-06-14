# Implementation Plan: Re-derive command (run mappers over stored transcriptions; no vision)

**Branch**: `056-re-derive-command` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/056-re-derive-command/spec.md`

## Summary

Add a `re-derive` subcommand to the `python -m analysis` CLI that re-runs the EXTRACT-003 deterministic per-type mappers over the **stored** typed transcriptions (persisted in `attachment_analysis_records.response`) to rebuild the authoritative `attachment_analyses` roll-ups, then rebuilds the global documents entity and refreshes alerts — all **image-free** (zero vision, zero R2 image reads). Scoped by period and/or attachment id, or global; idempotent; honors `--remote`.

**Technical approach**: Reuse the existing propagation primitive rather than invent a parallel roll-up path. For each in-scope attachment, reconstruct its stored per-page transcription into `page_classifications` staging rows (the same shape `record-classification` writes, sourced from `attachment_analysis_records.response` exactly as `corrections._snapshot_staging` does), clear its `attachment_state.classified_at` stamp, then run the feature-050 staging-driven `apply_extractions` (which rolls up only the groups whose representative has staging rows — so re-derive touches exactly the in-scope groups and inherits the no-empty-overwrite safety guard) followed by `run_analysis` (which rebuilds `documents` and refreshes alerts atomically per period). Because the roll-up runs through the unchanged apply path, re-derive is byte-for-byte consistent with normal apply and idempotent under unchanged mappers.

## Technical Context

**Language/Version**: Python 3 (stdlib-only `analysis` package, per CLAUDE.md); the CLI is `python -m analysis`.
**Primary Dependencies**: None new. Reuses `scripts/analysis/{extractions,attachments,corrections,page_classifications,loader,documents}.py`, `scripts/analysis/__init__.py` (`run_analysis`), and `scripts/common/d1.py` (the `wrangler`-CLI D1/R2 wrapper). No `tools/` import (the mappers `type_mappers.to_reconciliation_fields` are app-side, stdlib-only).
**Storage**: Cloudflare D1 (local Miniflare or `--remote` prod). Reads `attachment_analysis_records`; writes analysis-owned tables only (`page_classifications`, `attachment_analyses`, `attachment_analysis_records`, `attachment_state`, `documents`, `document_entries`, `alerts`). No schema change, no migration.
**Testing**: stdlib `unittest`. Pure-seam unit tests in `scripts/tests/` (run via `pnpm test:py`, coverage-gated `pnpm test:py:cov`); real-D1 integration tests in `scripts/integration_tests/` (run via `pnpm test:py:integration`, Miniflare-backed). No new JS dep.
**Target Platform**: CLI / server-side Python invoked by engineers and the triage agent.
**Project Type**: Single project — Python analysis pipeline under `scripts/`, decoupled from the Next.js app and the Playwright scraper.
**Performance Goals**: Image-free, so dominated by D1 round-trips; one `apply_extractions` + one `run_analysis` per affected period set. No latency target beyond "no R2 image reads".
**Constraints**: Stdlib-only `analysis` package; mirror-table invariant (zero writes to `entries`/`attachments`/`accountability_reports`); atomic delete-then-insert writebacks (feature 024); idempotent; `--remote` explicit (never implicit prod write).
**Scale/Scope**: One new CLI command + one new module function (`re_derive`) + a small reusable staging-reconstruction helper; ~1 file of new logic, CLI wiring, unit + integration tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No schema change, no migration, no Drizzle/auth edits. Python type hints used as in sibling modules.
- **II. Cloudflare-Native Architecture** — PASS. All D1/R2 access flows through `scripts/common/d1.py` (the established `wrangler` wrapper); no direct connections. `--remote` selects the target.
- **III. Quality Gates Before Commit** — PASS. Will run `pnpm lint` + `pnpm format` (Prettier covers markdown/specs too — project memory). Tests ARE requested by this spec (idempotency/safety/scope are testable), so unit + integration tests are added and must pass; `pnpm test:py` / `pnpm test:py:integration` exercised locally.
- **IV. Security & Auth by Default** — PASS. No new route, no auth surface; CLI-only, operates on already-authenticated D1 bindings.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the existing staging-driven apply + `corrections` propagation primitive instead of a new roll-up path; the only new surface is the command and a thin orchestration function. No new abstraction or dependency.

**Result**: No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/056-re-derive-command/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (CLI contract)
│   └── re-derive-cli.md
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── __main__.py            # + `re-derive` subparser + dispatch
│   ├── extractions.py         # + `re_derive(...)` orchestration function (alongside apply_extractions)
│   ├── corrections.py         # `_snapshot_staging` reused (or its core extracted to a shared helper)
│   ├── page_classifications.py# `page_classification_id` / staging row shape (reused)
│   ├── attachments.py         # `_clear/_propagate` semantics referenced; no change expected
│   └── __init__.py            # `run_analysis` reused
├── tests/
│   └── test_re_derive.py      # pure-seam unit tests (staging reconstruction, scope resolution, skip-when-empty)
└── integration_tests/
    └── test_re_derive_d1.py   # real-D1: re-derive reproduces analysis; idempotent; scoped; no mirror write
```

**Structure Decision**: Single-project Python pipeline. The new command lives in `scripts/analysis/__main__.py`; the orchestration function `re_derive` lives in `scripts/analysis/extractions.py` next to `apply_extractions` (its sibling propagation path). The staging-from-stored-records reconstruction reuses the logic already in `corrections._snapshot_staging`; to avoid duplication and a cross-module dependency on a private name, that reconstruction is factored into a small shared helper (in `page_classifications.py` or a new tiny seam) that both `corrections` and `re_derive` call. Tests follow the repo's split: pure `unittest` in `scripts/tests/`, real-D1 in `scripts/integration_tests/`.

## Complexity Tracking

> No Constitution Check violations — table intentionally empty.
