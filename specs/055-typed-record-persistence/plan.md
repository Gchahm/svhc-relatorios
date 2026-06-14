# Implementation Plan: Persist typed transcriptions + flat-row coexistence

**Branch**: `055-typed-record-persistence` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/055-typed-record-persistence/spec.md`

## Summary

Wire the merged typed-transcription contract (EXTRACT-001 schemas, EXTRACT-002 transcriber,
EXTRACT-003 mappers) into the live classification pipeline, gradually and non-breakingly:

1. `record-classification` becomes dual-path at the contract gate — a payload carrying a `doc_type`
   discriminator is validated against the EXTRACT-001 schema (via `doc_transcribe.validate_transcription`,
   reached through a thin gate that adds `tools/` to `sys.path` at the CLI layer); a payload without
   `doc_type` keeps using the existing flat-field contract; the `{"error": ...}` alternative is
   unchanged.
2. The rich typed JSON is **persisted verbatim** in `page_classifications.response` and, after
   roll-up, in `attachment_analysis_records.response` (no migration — both are TEXT). The
   reconciliation roll-up reads its values through the EXTRACT-003 mapper instead of pre-collapsing
   the record to the flat dict, so the typed JSON survives into the records table while the roll-up
   still derives the correct total/issuer/date for typed AND legacy flat rows.
3. The analysis detail dialog renders both shapes: a typed record shows the reconciliation fields
   (derived) plus the rich transcription; a legacy flat record renders exactly as before.

## Technical Context

**Language/Version**: Python 3 (stdlib-only analysis pipeline; `uv` for tests) + TypeScript/React 19
(Next.js 15 App Router) for the UI.
**Primary Dependencies**: existing — `tools/doc_transcribe` (EXTRACT-001 registry + validator),
`scripts/analysis/type_mappers.py` (EXTRACT-003), `scripts/common/d1.py`. No new third-party
dependency (design T1).
**Storage**: Cloudflare D1 (SQLite). Reuses existing TEXT columns `page_classifications.response`
and `attachment_analysis_records.response` — **no migration** (FR-005).
**Testing**: stdlib `unittest` under `scripts/tests` (pure seams) + `scripts/integration_tests`
(real local D1); `tools/doc_transcribe/tests` for the validator. UI verified manually via the
running app (no JS test framework — constitution III).
**Target Platform**: Cloudflare Workers (UI/API) + local Python CLI (pipeline).
**Project Type**: web (Next.js frontend + Python analysis backend).
**Performance Goals**: N/A — per-page validation + a pure mapper; negligible.
**Constraints**: analysis *library* code (roll-up, mappers, staging) must NOT import `tools/`
(design §11.6); only the executable contract gate may. Stdlib-only in the analysis library.
**Scale/Scope**: per-page payloads (KBs); the existing corpus is legacy flat and must not regress.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No DB schema change (reuses TEXT columns), so no
  Drizzle migration. TS UI change stays typed; no `any` without justification.
- **II. Cloudflare-Native Architecture** — PASS. All D1 access stays via `scripts/common/d1.py`
  (Python) and `getDb()` (UI). No new bindings.
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` before commit; Python
  unit + integration tests added (spec explicitly drives them); UI verified in the running app.
- **IV. Security & Auth by Default** — PASS. No new routes; the detail dialog stays behind the
  existing auth-gated `/api/attachment-analyses` routes.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the existing mapper + validator + d1 seam;
  adds one thin gate module and one shared `is_typed` predicate. Gradual rollout (T2), no
  re-classification campaign.

No violations → Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/055-typed-record-persistence/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── record-classification-cli.md
└── tasks.md            # speckit tasks output (next phase)
```

### Source Code (repository root)

```text
scripts/
├── analysis/
│   ├── typed_gate.py            # NEW — the executable contract gate: adds tools/ to sys.path and
│   │                            #   validates a typed payload via doc_transcribe.validate_transcription.
│   │                            #   This is the ONE place analysis touches tools/, and only at runtime.
│   ├── page_classifications.py  # EDIT — validate_page_fields() accepts a typed payload (doc_type
│   │                            #   present) via the gate; record_classification stores it verbatim.
│   │                            #   The is_typed(response) predicate lives here (shared, stdlib-only).
│   ├── attachments.py           # EDIT — stop collapsing record.response to the flat dict; STORE the
│   │                            #   raw (typed or flat) response, derive reconciliation fields for the
│   │                            #   roll-up via to_reconciliation_fields at each read site.
│   ├── type_mappers.py          # (used as-is — EXTRACT-003; already idempotent on flat)
│   └── __main__.py              # EDIT — record-classification CLI calls the dual-path validation.
├── tests/
│   ├── test_typed_record_persistence.py   # NEW — pure: dual-path validate, roll-up over typed/flat.
│   └── (existing suites unchanged)
└── integration_tests/
    └── test_typed_record_d1.py            # NEW — real D1: record typed -> apply -> records carry
                                           #   typed JSON; legacy flat still rolls up; invalid rejected.

src/app/dashboard/entries/
└── AttachmentAnalysisDetailDialog.tsx     # EDIT — dual-path render: typed record shows derived
                                           #   reconciliation fields + rich transcription; flat unchanged.
```

**Structure Decision**: Web project. The pipeline change is localized to `scripts/analysis` (one new
thin gate module + edits to the staging gate, the roll-up read sites, and the CLI). The UI change is
one component. No schema/migration. The EXTRACT-003 mapper and the d1 seam are reused unchanged.

## Phase 0 — Research

See [research.md](./research.md). Key decisions resolved there:

- **R1 — Where typed validation lives** (the design's "analysis must not import `tools/`" vs. the
  issue's "validate against the EXTRACT-001 schema"): a thin **`scripts/analysis/typed_gate.py`** that
  adds the repo `tools/` dir to `sys.path` at call time and delegates to
  `doc_transcribe.validate_transcription`. The gate is the only runtime importer; the analysis
  *library* (roll-up/mappers/staging) stays import-clean.
- **R2 — How the typed JSON survives to the records table**: stop the `record.response =
  to_reconciliation_fields(parsed)` collapse in `build_attachment_analysis`; store the raw response
  and derive reconciliation fields at each roll-up read site via the mapper (already done for
  `nf_total_for_reconciliation`).
- **R3 — Typed-vs-flat predicate**: `is_typed(resp)` = `isinstance(resp, dict) and "doc_type" in
  resp`, owned in one place (`page_classifications.is_typed`) and mirrored in the UI.
- **R4 — schema_version tagging**: the typed `fields` object already carries `schema_version`
  (stamped by the transcriber); the gate enforces it is present/valid via the schema. No extra column.

## Phase 1 — Design & Contracts

- [data-model.md](./data-model.md): the typed vs. flat stored response shapes, the reconciliation
  fields, and the dual-path read rule.
- [contracts/record-classification-cli.md](./contracts/record-classification-cli.md): the updated CLI
  contract (dual-path validation, exit codes, what is stored).
- [quickstart.md](./quickstart.md): end-to-end verification against local D1.

### Post-Design Constitution Re-Check

No change to the gate evaluation above. Still PASS on all five principles; Complexity Tracking empty.

## Complexity Tracking

No constitution violations — no entries.
