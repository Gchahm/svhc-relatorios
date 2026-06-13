# Implementation Plan: Deterministic per-type mappers (typed JSON → reconciliation fields)

**Branch**: `053-deterministic-type-mappers` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/053-deterministic-type-mappers/spec.md`

## Summary

Add pure, per-document-type mappers that derive the analysis reconciliation fields (`valor_total`,
`valor_liquido`, `valor_pago`, `cnpj_emitente`, `numero_documento`, …) deterministically from the
typed transcription JSON, and wire them into the analysis interpretation seam
(`_rollup_attachment_fields` / `nf_total_for_reconciliation`). This replaces the model's
interpretation guesswork and the order-dependent "first-record-of-role-wins" selection, fixing the
documented `757dedb0` case (yields 320, not 800) and the `rollup-amount-false-positives.md` Problem A
false positives — while passing legacy flat records through unchanged (no regression, no migration).

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI under `scripts/analysis/`, run via `uv`)  
**Primary Dependencies**: Existing only — Python **stdlib only** for the mappers; the analysis package
does not import `tools/doc_transcribe`. No new pip/npm dependency.  
**Storage**: None written. Reads in-memory per-page `response` dicts already loaded by the roll-up.
**No DB schema change, no migration.**  
**Testing**: Python stdlib `unittest` (`pnpm test:py`), pure-seam unit tests.  
**Target Platform**: Cloudflare Workers app's Python analysis pipeline (local + `--remote`).  
**Project Type**: single (Python analysis package within the Next.js repo).  
**Performance Goals**: N/A — pure dict transforms over already-loaded records.  
**Constraints**: stdlib-only; never raises on any input; tolerance contract untouched.  
**Scale/Scope**: One new module (`scripts/analysis/type_mappers.py`), a localized edit to two
functions in `scripts/analysis/attachments.py`, and unit tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No DB schema change, no migration, no auth change.
  Python stays type-annotated; mappers return a stable dict shape.
- **II. Cloudflare-Native Architecture** — PASS / N/A. No DB access; the change is pure in-memory
  interpretation. The existing `getDb()`/D1 access paths are untouched.
- **III. Quality Gates Before Commit** — PASS. The spec explicitly requests unit tests (FR-010);
  they are added and must pass. `pnpm lint`/`pnpm format` run before commit; Prettier covers the
  touched docs.
- **IV. Security & Auth by Default** — PASS / N/A. No routes, no data exposure, no secrets.
- **V. Simplicity & Incremental Delivery** — PASS. Smallest viable surface: one pure module + a
  localized two-function wiring; no new abstraction beyond the mapper the issue asks for; app-side
  per design T6; reuses `_parse_brl_value` and the existing role/selection logic unchanged.

No violations — Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/053-deterministic-type-mappers/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (output shape, dispatch, home, mapping rules, wiring)
├── data-model.md        # Phase 1 — input/output dict shapes (no persisted model)
├── quickstart.md        # Phase 1 — verify commands + 757dedb0 spot-check
├── contracts/
│   └── type_mappers.md  # Phase 1 — module + wiring contract
├── checklists/
│   └── requirements.md  # Spec quality checklist (from specify)
└── tasks.md             # Phase 2 — created by `speckit tasks`
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── type_mappers.py        # NEW — pure per-type mappers + dispatch (stdlib only)
│   └── attachments.py         # EDIT — wire to_reconciliation_fields into
│                              #   _rollup_attachment_fields + nf_total_for_reconciliation
└── tests/
    ├── test_type_mappers.py   # NEW — mapper + dispatch unit tests (incl. 757dedb0, false-positive cases)
    └── test_attachment_*.py   # EDIT/ADD — roll-up over typed records + legacy flat pass-through regression
```

**Structure Decision**: Single Python analysis package. The mappers are a new self-contained
stdlib-only module in `scripts/analysis/`; the wiring is a localized normalization boundary inside
the two existing interpretation functions in `attachments.py`. No frontend, schema, or migration work.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
