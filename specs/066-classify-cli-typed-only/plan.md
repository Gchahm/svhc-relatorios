# Implementation Plan: All-CLI typed document transcription — `classify` command, retire classify skills, typed-only

**Branch**: `066-classify-cli-typed-only` | **Date**: 2026-06-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/066-classify-cli-typed-only/spec.md`

## Summary

Collapse the two document-transcription producers (the in-context `classify-*` skills emitting flat
records; the dormant headless typed `doc_transcribe`) into ONE headless, typed-only CLI path. Add a
`classify` subcommand to the analysis CLI that builds the existing pending plan, runs
`doc_transcribe` **as a subprocess** per pending page, and records the typed `fields` to
`page_classifications`; delete the `classify-doc-page` / `classify-period` skills and the
`analyze-docs` agent; rewire `improve-classification` to run the CLI steps directly; tighten the
`record-classification` gate to typed-only and delete the dead flat code (gate branch + constants,
mapper tolerance, UI dual-render). No `tools/doc_transcribe` change, no D1 schema change, no
migration.

## Technical Context

**Language/Version**: Python 3 (stdlib only for the analysis pipeline; `tools/doc_transcribe` reached
only as a subprocess) + TypeScript/React (UI dual-render removal).
**Primary Dependencies**: existing `scripts/analysis` pipeline (`build_plan`, `select_work`,
`record_classification`, `D1ExtractionProvider`, `materialize_period_images`), `scripts/common`
(`d1`, `det_id`), `tools/doc_transcribe` (subprocess only), `typed_gate.validate_typed` (existing
import seam). No new dependency.
**Storage**: Cloudflare D1 — `page_classifications` (TEXT `response` already stores typed JSON). No
schema change, no migration.
**Testing**: stdlib `unittest` under `scripts/tests/` (`pnpm test:py`); `node --test` for the UI
`.test.mjs`. New tests inject a fake transcriber callable into the `classify` loop (no real model,
no subprocess) and exercise the tightened gate directly.
**Target Platform**: Cloudflare Workers (UI) + local Python CLI / CI (pipeline).
**Project Type**: web (Next.js app) + Python tooling under `scripts/` and `tools/`.
**Performance Goals**: pages processed serially — cost-predictable, not throughput-bound.
**Constraints**: analysis library MUST stay import-clean of `tools/` except the `typed_gate` seam;
the `classify` loop reaches `doc_transcribe` ONLY via subprocess (never import). Lint + format gates
(Prettier over markdown/ts; `pnpm test:py` + `pnpm test:py:cov` fail_under=78).
**Scale/Scope**: a handful of source files touched: `scripts/analysis/{__main__.py,classify.py(new),
page_classifications.py,type_mappers.py,corrections.py}`, UI
`src/app/dashboard/entries/{AttachmentAnalysisDetailDialog.tsx,typed-transcription.ts}`, deletions
under `.claude/skills` + `.claude/agents`, docs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No D1 schema change, no migration, no auth schema
  change. TypeScript change is a deletion of a dead branch (the dialog keeps type-checking; flat
  shape no longer exists). Removing `isTyped` keeps the typed flatten path which is the only live one.
- **II. Cloudflare-Native Architecture** — PASS. No DB-access change; pipeline keeps writing through
  `common.d1`. No new binding.
- **III. Quality Gates Before Commit** — PASS. The spec explicitly requests unit tests (FR-015), so
  tests are added and MUST pass. `pnpm lint`/`pnpm format` run before PR; markdown/ts covered by
  Prettier (memory: prettier docs CI gate).
- **IV. Security & Auth by Default** — PASS. No route/auth change; `classify` is a local/remote CLI
  step like the others.
- **V. Simplicity & Incremental Delivery** — PASS. This REMOVES surface area (one transcriber, one
  contract, fewer skills/agents). The new `classify` command reuses `build_plan` /
  `record_classification` wholesale and adds no abstraction beyond a thin per-page subprocess loop
  with an injectable transcriber seam for testing.

No violations → Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/066-classify-cli-typed-only/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── classify-cli.md  # the classify subcommand contract
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/analysis/
├── classify.py                 # NEW: classify_period loop + transcriber subprocess seam
├── __main__.py                 # +classify subparser & dispatch
├── page_classifications.py     # tighten validate_page_fields to typed-only; delete flat constants
├── type_mappers.py             # delete legacy-flat pass-through tolerance
└── corrections.py              # inject typed_gate.validate_typed into reclassify/apply_correction gate calls

scripts/tests/
└── test_classify.py            # NEW: classify loop (fake transcriber) + tightened gate cases

src/app/dashboard/entries/
├── AttachmentAnalysisDetailDialog.tsx  # remove isTyped dual-render (typed-only flatten)
├── typed-transcription.ts              # (unchanged logic; remains the single renderer)
└── typed-transcription.test.mjs        # unchanged / adjust if it asserted flat

.claude/skills/classify-doc-page/   # DELETED (incl. scripts/validate_image.py)
.claude/skills/classify-period/     # DELETED
.claude/agents/analyze-docs.md      # DELETED
.claude/skills/improve-classification/SKILL.md  # rewired to CLI steps
.claude/agents/fix-mismatch.md      # update references
.claude/agents/review-mismatch.md   # update references

docs/pipeline.md, scripts/pipeline-flow.md, scripts/README.md,
docs/runbooks/fix-document-vision-mismatch.md, CLAUDE.md  # updated to all-CLI typed flow
```

**Structure Decision**: Reuse the existing `scripts/analysis` package layout. The new `classify`
command lives in its own module `scripts/analysis/classify.py` (parallel to `extractions.py`),
keeping the per-page subprocess loop and its injectable transcriber seam isolated and unit-testable
without touching the deterministic plan/apply code.

## Phase 0: research — see research.md

Key decisions resolved (all from the spec's Assumptions, validated against the code):

- Subprocess launch mechanism + `tools/` resolution.
- Per-page failure detection signal (`parse_errors`) and error-row reason synthesis.
- Config-error propagation (non-zero exit) → stop the run.
- Injectable transcriber seam for testing (no real subprocess in unit tests).
- Gate-injection for corrections to satisfy FR-010.

## Phase 1: design — see data-model.md, contracts/classify-cli.md, quickstart.md

## Re-evaluation (post-design)

No new constitution concerns surfaced during design. The design adds one new module + one subparser,
removes more code than it adds, and introduces no schema/dependency/route change. Gate: PASS.
