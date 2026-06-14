# Tasks: All-CLI typed document transcription — `classify` command, retire classify skills, typed-only

**Feature**: `066-classify-cli-typed-only` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

All paths absolute from repo root `/home/agent/workspace/svhc-relatorios`.

## Phase 1: Setup

- [x] T001 Confirm baseline green: run `pnpm test:py` and note the passing count (431) so regressions are visible.

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Tighten the gate to typed-only in `scripts/analysis/page_classifications.py`: rewrite `validate_page_fields` so after the `{"error": ...}` branch it REQUIRES a typed payload (dict carrying a valid `doc_type`, schema-validated via the injected `typed_validator`) and REJECTS anything else with a clear message; delete the flat branch and the `REQUIRED_KEYS`/`PAPEL_VALUES`/`STRING_OR_NULL`/`AMOUNT_KEYS` constants and the now-unused `is_typed` predicate. Update the module docstring/`record_classification` docstring (remove "flat" wording). Keep `record_classification`'s `is_error = "error" in payload` logic.
- [x] T003 Delete the legacy-flat read tolerance in `scripts/analysis/type_mappers.py`: remove `_passthrough_flat` and the `"doc_type" not in response` branch from `to_reconciliation_fields`; keep the never-raise `_empty()` fallback for `None`/non-dict and route any dict through a per-type mapper (unknown `doc_type` → `_map_outro`). Update the module docstring (drop the flat-coexistence / idempotent-on-flat paragraph).

## Phase 3: User Story 1 — Headless typed classification (P1)

**Goal**: `python -m analysis classify --periodo <p>` records a typed `page_classifications` row per pending non-`recorded` page via `doc_transcribe` subprocess. **Independent test**: with a fake transcriber, a seeded pending plan yields one typed row per page.

- [x] T004 [US1] Create `scripts/analysis/classify.py`: define `ClassifyConfigError(Exception)`; a real subprocess runner `_run_doc_transcribe(read_path, *, backend, model) -> dict` that launches `[sys.executable, "-m", "doc_transcribe", "--image", read_path, "--type", "auto", "--backend", backend, *("--model", model if model)]` with `cwd=<repo>/tools` (resolved like `typed_gate`'s `parents[2]/"tools"`) and `PYTHONPATH` including it, captures stdout/stderr, raises `ClassifyConfigError(stderr)` on non-zero exit, else returns the parsed JSON envelope; and `classify_period(target, periods_filter, *, cache_dir, min_amount, limit, backend="cli", model=None, transcribe_page=None, typed_validator=None)` that loads periods, materializes images, builds the plan via `build_plan`, and serially transcribes each `recorded == False` page (skip recorded), recording typed `fields` or an `{"error": ...}` row (per-page failure = non-empty `parse_errors` / no usable `fields`), stopping the run on `ClassifyConfigError`. Default `transcribe_page` wraps `_run_doc_transcribe` and extracts `fields`/`parse_errors`; default `typed_validator` is `typed_gate.validate_typed` (lazy import). Vision only — no apply/analyze.
- [x] T005 [US1] Wire the `classify` subcommand in `scripts/analysis/__main__.py`: add the subparser (`--periodo`, `--remote`, `--min-amount`, `--limit`, `--backend cli|api` default cli, `--model`, `--cache-dir`) and dispatch to `classify_period`, surfacing a `ClassifyConfigError` as a stderr message + non-zero exit. Update the module docstring command list to include `classify`.

## Phase 4: User Story 2 — Bad page continues, config error stops (P1)

**Goal**: per-page failure → error row + continue; config error → stop. (Implemented in T004; this phase is the dedicated tests.)

- [x] T006 [US2] In `scripts/tests/test_classify.py` (new), add tests with an injected fake transcriber: (a) per-page transcription failure (fake returns/ signals `parse_errors`) records one `{"error": ...}` row and the remaining pages are still recorded; (b) `ClassifyConfigError` from the fake stops the run (raises out of `classify_period`) and records nothing past the failure point.

## Phase 5: User Story 3 — One typed contract end to end (P1)

**Goal**: gate accepts typed/error, rejects flat; corrections pass the gate with typed payloads.

- [x] T007 [US3] In `scripts/tests/test_classify.py`, add gate tests: a legacy flat fields object is rejected (`validate_page_fields` returns an error message); a valid typed payload (with a fake `typed_validator` returning `[]`) is accepted; an `{"error": "..."}` object is accepted; a typed payload failing the validator (fake returns errors) is rejected.
- [x] T008 [US3] Inject the typed validator into the correction primitives in `scripts/analysis/corrections.py`: in `reclassify` and `apply_correction`, pass `typed_validator=validate_typed` (lazy import of `analysis.typed_gate.validate_typed`) to both the `validate_page_fields(...)` pre-checks and the `record_classification(...)` calls, so corrected pages are schema-validated through the same gate. Update the affected docstrings (drop "structurally but not against the EXTRACT-001 schema" wording).
- [x] T009 [US3] Verify the existing correction unit tests still pass (`scripts/tests/test_corrections.py`, `scripts/tests/test_reclassify.py`); update any test that fed a flat payload so it now feeds a typed payload (or injects a fake validator), preserving the test's intent.

## Phase 6: User Story 4 — Skills/agent deleted; dependents rewired (P2)

**Goal**: classify skills + analyze-docs agent gone; improve-classification + fix/review-mismatch + docs updated.

- [x] T010 [P] [US4] Delete `.claude/skills/classify-doc-page/` (entire dir, incl. `scripts/validate_image.py`) and `.claude/skills/classify-period/` (entire dir).
- [x] T011 [P] [US4] Delete `.claude/agents/analyze-docs.md`.
- [x] T012 [US4] Rewire `.claude/skills/improve-classification/SKILL.md` to run the CLI steps directly (`classify → apply-extractions → analyze → mismatches` as plain bash) instead of delegating to the `analyze-docs` agent.
- [x] T013 [P] [US4] Update `.claude/agents/fix-mismatch.md` and `.claude/agents/review-mismatch.md`: replace descriptive references to `analyze-docs` / the classify skills with the all-CLI `classify` flow; fix-mismatch's "reading"/root-cause target becomes the `doc_transcribe` prompt/schemas.
- [x] T014 [US4] Remove the `analyze-docs` agent entry and the "Attachment analysis (Claude vision skills)" wording from `CLAUDE.md`, replacing it with the all-CLI typed `classify` flow (keep the staging/apply/analyze invariants); also update its `## Agents` list.

## Phase 7: Polish & Cross-Cutting

- [x] T015 [P] Update the UI in `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx`: remove the `isTyped` dual-render (and the `isTyped` helper); always render via the typed flatten (`typed-transcription` builder); keep the defensive try/catch degradation. Adjust `src/app/dashboard/entries/typed-transcription.test.mjs` only if it asserted the flat path.
- [x] T016 [P] Update docs to the all-CLI typed flow: `docs/pipeline.md`, `scripts/pipeline-flow.md`, `scripts/README.md`, `docs/runbooks/fix-document-vision-mismatch.md`, and the descriptive `classify-period` reference in `docs/features/false-positive-triage-agent.md` (adjust the line only — do not redesign the review skills).
- [x] T017 Run `pnpm test:py` and `pnpm test:py:cov` (coverage ≥ 78); run `node --test src/app/dashboard/entries/typed-transcription.test.mjs`; run `node_modules/.bin/eslint`-equiv `pnpm lint` and `pnpm format` (Prettier over markdown/ts — memory: prettier docs CI gate). Fix any failures.
- [x] T018 Sanity-grep the repo for `classify-doc-page`, `classify-period`, `analyze-docs` and confirm no live-path reference remains (only historical spec/changelog mentions allowed); confirm the analysis library imports with `tools/` off `sys.path` beyond the `typed_gate` seam.

## Dependencies & order

- Phase 1 → Phase 2 (gate/mapper tightening) → Phase 3 (classify command) → Phases 4–5 (tests + corrections) → Phase 6 (skills/agents/docs) → Phase 7 (UI/docs/verify).
- T002 must precede T006/T007 (tests assert the tightened gate). T004 must precede T005/T006. T008 must precede T009.
- [P] tasks within a phase touch distinct files and may run in any order.

## MVP

User Story 1 (T004–T005) is the MVP: the working `classify` command. The rest hardens (US2/US3) and cleans up (US4 + polish).
