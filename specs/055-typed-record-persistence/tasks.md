# Tasks: Persist typed transcriptions + flat-row coexistence

**Feature**: `055-typed-record-persistence` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are explicitly requested by the spec (Independent Tests / SC-001..004 + constitution III: when
present they must pass). So test tasks are included.

## Phase 1: Setup

- [x] T001 Confirm prerequisites: `tools/doc_transcribe` (validator + 6 schemas), `scripts/analysis/type_mappers.py` (EXTRACT-003), and the `page_classifications` staging seam are present; run `cd scripts && uv run python -m unittest discover -s tests -t .` once to capture the green baseline.

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Create `scripts/analysis/typed_gate.py`: a thin runtime gate that resolves the repo `tools/` dir (`Path(__file__).resolve().parents[2] / "tools"`), inserts it on `sys.path` if absent, imports `doc_transcribe`, and exposes `validate_typed(payload: dict, doc_type: str | None) -> list[str]` delegating to `doc_transcribe.validate_transcription`. Lazy import inside the function (no `tools/` import at module import). Docstring states this is the ONLY analysis→tools runtime boundary.
- [x] T003 Add the shared predicate `is_typed(resp) -> bool` (`isinstance(resp, dict) and "doc_type" in resp`) to `scripts/analysis/page_classifications.py` (stdlib-only, no `tools/` import).

## Phase 3: User Story 1 — New typed classifications persist and reconcile (P1)

**Goal**: A typed payload is stored verbatim with its `schema_version`, and the roll-up derives the
correct reconciliation values via the EXTRACT-003 mapper.

**Independent test**: record a typed NFS-e/DANFE payload → apply → records carry the typed JSON;
roll-up total = mapper-derived (nfse net, danfe `valor_total_nota`).

- [x] T004 [US1] In `scripts/analysis/attachments.py` `build_attachment_analysis`, stop collapsing `record.response = to_reconciliation_fields(parsed)`. Store the raw response (`record.response = parsed`) and compute a derived reconciliation view once via `to_reconciliation_fields(parsed)`; set `record.artifact_role = _map_artifact_role(<derived>)`.
- [x] T005 [US1] Add a non-persisted `recon` field to `PageAnalysisRecord` (the derived reconciliation dict) and point the roll-up read sites at it: `_rollup_attachment_fields` (`first_field`, `pick`), `_pick_issuer_name`, `_pick_attachment_date`, `_pick_payment_amount`, `_sum_distinct_invoices`, `_attachment_in_period`, `_issuer_names_of` — read `r.recon` for reconciliation values while `r.response` stays the raw stored JSON. Ensure `recon` defaults safely (empty dict) for parse-error / fan-out records.
- [x] T006 [US1] In `_fanout_result`, carry `recon` (and the raw `response`) from the representative's records to the siblings unchanged, so a sibling rolls up and persists identically (FR-009).
- [x] T007 [US1] Verify `nf_total_for_reconciliation` and `_apply_group_amount_match` still derive correctly now that `r.response` is raw (they already map via `to_reconciliation_fields` at read time — confirm no double-collapse and that they read `r.response`).
- [x] T008 [P] [US1] Unit tests in `scripts/tests/test_typed_record_persistence.py`: a typed NFS-e record rolls up to net 320 (not gross); a typed DANFE rolls up to `valor_total_nota` with issuer from `emitente`; `record.response` after build equals the raw typed JSON (typed JSON survives); fan-out sibling carries the same response/recon.

## Phase 4: User Story 2 — Legacy flat rows still read and reconcile (P1)

**Goal**: Zero regression on the existing flat corpus.

**Independent test**: a flat record rolls up byte-identically to pre-feature behavior.

- [x] T009 [US2] Confirm `to_reconciliation_fields(flat)` identity pass-through keeps `_rollup_attachment_fields` output unchanged for a flat record (the mapper is already idempotent on flat); add a regression unit test in `scripts/tests/test_typed_record_persistence.py` asserting a flat record's rolled-up fields match the pre-feature values, and that `record.response` for a flat record stays the flat dict.
- [x] T010 [US2] Run the full existing Python unit suite (`cd scripts && uv run python -m unittest discover -s tests -t .`) and confirm no existing test regressed by the read-site change.

## Phase 5: User Story 3 — Invalid typed payloads rejected at the gate (P2)

**Goal**: `record-classification` validates typed payloads against the EXTRACT-001 schema; invalid → rejected, nothing written.

**Independent test**: a typed payload missing a required field → exit 1, located error, no staging row.

- [x] T011 [US3] In `scripts/analysis/page_classifications.py`, extend `validate_page_fields(obj, *, typed_validator=None)`: if `obj` is a dict with `doc_type` (and not an error object), call `typed_validator(obj, obj["doc_type"])` and return the first joined error (or None); otherwise keep the existing flat / error branches. Default `typed_validator=None` means "no typed validation available" — but `record_classification` must pass the real gate so typed payloads are always validated.
- [x] T012 [US3] Wire `record_classification` (and/or the CLI in `scripts/analysis/__main__.py`) to pass `typed_gate.validate_typed` as the `typed_validator` so the real EXTRACT-001 schema gate runs; keep `ValueError` → exit 1 + `error: classification rejected: <detail>` behavior. Storage stays unchanged (typed JSON verbatim in `response`).
- [x] T013 [P] [US3] Unit tests (inject a fake typed validator into `validate_page_fields`): valid typed → None; typed missing required field → error message; typed with unexpected key → error; `{"error": "..."}` still accepted; flat still validates as before; non-dict rejected.

## Phase 6: User Story 4 — Reviewer sees the full typed transcription (P3)

**Goal**: the analysis detail dialog renders typed records richly and flat records unchanged, no error for either.

**Independent test**: open the dialog for a typed record (rich render) and a flat record (unchanged).

- [x] T014 [US4] In `src/app/dashboard/entries/AttachmentAnalysisDetailDialog.tsx`, detect a typed record (`"doc_type" in parsed`). For a typed record, render the full transcription (all top-level fields, nested blocks expanded into readable label/value rows) reusing the existing `formatValue` (objects stringify) and the `Field` component; keep the flat path byte-identical. Add any new chrome strings to the i18n catalog used by the dialog (e.g. a "Full transcription" heading) following the existing `t()` pattern.
- [x] T015 [US4] Keep the render robust: a typed record with a missing/odd block must not crash (guard nested access); a record with neither `doc_type` nor known flat fields falls back to the existing "no parsed values" notice.

## Phase 7: Integration & Verification

- [x] T016 Integration tests in `scripts/integration_tests/test_typed_record_d1.py` (real local D1): (a) `record-classification` a typed NFS-e → `apply-extractions` → assert `attachment_analysis_records.response` carries the typed JSON (`doc_type`/`schema_version` present) and the `attachment_analyses` reconciliation total = net; (b) a legacy flat record rolls up unchanged; (c) a schema-invalid typed payload is rejected (no staging row written). Scope all assertions to synthetic ids (per memory `integration-tests-shared-d1-scope`).
- [x] T017 Run `cd scripts && uv run python -m unittest discover -s integration_tests -t .` and the `tools` validator suite (`uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools`) — all green.
- [x] T018 UI verification via the running app (`pnpm preview` + `ui-login`): open the analysis detail dialog for a typed record and a flat record; confirm both render without error (delegated to the `ui-reviewer` agent, fixing any blocker/major it finds).

## Phase 8: Polish & Cross-Cutting

- [x] T019 Run `pnpm lint` and `pnpm format` (Prettier covers `scripts/`-adjacent JS/TS and markdown; run `prettier --write` over changed docs/TS per memory `prettier-docs-ci-gate`). Run `prettier --write 'tools/**/*.{json,md}'` only if any tools file changed (it should not).
- [x] T020 Update CLAUDE.md "Important Patterns" with a short EXTRACT-004 note (typed JSON persisted verbatim in `attachment_analysis_records.response`; reconciliation derived at read time via the mapper; `typed_gate.py` is the only analysis→tools runtime boundary; dual-path UI). Keep it concise.

## Dependencies

- Phase 1 → Phase 2 → Phases 3-6 (US1 and US2 share the read-site change in `attachments.py`; do US1
  then US2's regression check). US3 (gate) is independent of US1/US2 except both touch
  `page_classifications.py` — sequence T011/T012 after T003. US4 (UI) is independent of the Python work.
- Phase 7 (integration + UI verify) requires Phases 3-6. Phase 8 last.

## Parallel opportunities

- T008, T013 are `[P]` (separate test files / independent of each other).
- US4 (T014/T015, UI) can proceed in parallel with the Python US1/US2/US3 work.

## MVP scope

US1 + US2 (typed persists + reconciles; flat unchanged) is the MVP. US3 (gate) and US4 (UI) layer on.
