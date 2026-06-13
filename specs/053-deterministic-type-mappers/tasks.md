# Tasks: Deterministic per-type mappers (typed JSON → reconciliation fields)

**Feature**: `053-deterministic-type-mappers` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests ARE requested (FR-010, SC-001..SC-005). Stdlib `unittest`, run via `pnpm test:py`.

## Phase 1: Setup

- [x] T001 Confirm baseline: `pnpm test:py` and the tools suite (`cd scripts && uv run python -m unittest discover -s ../tools/doc_transcribe/tests -t ../tools`) both pass on the branch before changes.

## Phase 2: Foundational (blocking — the mappers are the shared core both user stories consume)

- [x] T002 Create `scripts/analysis/type_mappers.py` (stdlib only, no `tools` import) with `_canonical_doc_type(value)` mirroring the EXTRACT-001 six-type taxonomy (danfe/nfse/boleto/recibo/comprovante_pagamento/outro; alias + case/underscore/hyphen-insensitive; unknown/None → "outro").
- [x] T003 In `scripts/analysis/type_mappers.py`, add the per-type mappers `_map_danfe`, `_map_nfse`, `_map_boleto`, `_map_recibo`, `_map_comprovante`, `_map_outro` per `contracts/type_mappers.md` / `research.md` Decision 4 (defensive nested access; never raise). Key: `_map_nfse → valor_total = valor_liquido = valores.valor_liquido`; `_map_danfe → totais.valor_total_nota`; `_map_comprovante → valor_pago = valor`; `_map_boleto → valor_documento`; `_map_recibo → valor`; `_map_outro → first valores_identificados[].valor`.
- [x] T004 In `scripts/analysis/type_mappers.py`, add the dispatch `to_reconciliation_fields(response)`: None/non-dict → empty-valued reconciliation dict; `doc_type` present → canonicalize + per-type mapper; `doc_type` absent → legacy flat pass-through (project the known reconciliation keys off `response`, values unchanged); never raises. Define the canonical reconciliation-key list as a module constant.

## Phase 3: User Story 1 — 757dedb0 NFS-e maps to the page total (Priority: P1) 🎯 MVP

**Goal**: The nfse mapper deterministically yields 320 (not 800) and the right issuer/number.
**Independent test**: `cd scripts && uv run python -m unittest tests.test_type_mappers` asserts the 757dedb0 nfse case → `valor_total == 320`, `cnpj_emitente == prestador.cnpj`, `numero_documento == numero`.

- [x] T005 [US1] Create `scripts/tests/test_type_mappers.py` with the 757dedb0 nfse case: typed nfse JSON (`valores.valor_liquido = 320`) → `to_reconciliation_fields` yields `valor_total == 320.0` and `valor_liquido == 320.0` (NOT 800), `cnpj_emitente` = prestador cnpj, `numero_documento` = numero, `papel_artefato == "nfse"`.
- [x] T006 [P] [US1] In `scripts/tests/test_type_mappers.py`, add per-type mapper unit tests (danfe/boleto/recibo/comprovante/outro) using inline fixtures mirroring `tools/doc_transcribe/examples/*.json`, asserting each derived reconciliation field; include amount-as-currency-string (`"R$ 320,00"`) parity and a spurious `valor_pago: 0.0` not winning.
- [x] T007 [P] [US1] In `scripts/tests/test_type_mappers.py`, add dispatch edge tests: unknown `doc_type` → `_map_outro` (no raise); `None`/non-dict input → empty-valued dict (no raise); alias resolution (`"NFS-e"`, `"nota fiscal"`) → canonical type.

## Phase 4: User Story 2 — documented record-selection false positives no longer fire (Priority: P1)

**Goal**: Wire the mappers into the roll-up so the `rollup-amount-false-positives.md` Problem A cases reconcile, with no false negative introduced.
**Independent test**: roll-up tests over typed records assert the derived total reconciles; a constructed real over/under-claim still surfaces.

- [x] T008 [US2] Wire `to_reconciliation_fields` at the record-build boundary in `build_attachment_analysis` (`scripts/analysis/attachments.py`): after `provider` returns `parsed`, set `record.response = to_reconciliation_fields(parsed)` then `record.artifact_role = _map_artifact_role(record.response)`. Idempotent on flat (no-op for legacy data). Preserve all existing roll-up/selection logic unchanged.
- [x] T009 [US2] Add a defensive (idempotent) `to_reconciliation_fields` map inside `nf_total_for_reconciliation` (`scripts/analysis/attachments.py`) before reading `valor_total`, so the read-back path in `documents.build_documents` also derives typed totals. Keep the `reconcile_group` tolerance + `reconciliation_contract.json` untouched.
- [x] T010 [US2] In `scripts/tests/` (extend an existing attachment roll-up test module or add a focused one), add tests over **typed** records: the documented Problem-A cases (e.g. an nfse whose líquido matches the entry) reconcile (`amount_match` true / total matches), and `nf_total_for_reconciliation` returns the typed total.
- [x] T011 [P] [US2] Add a false-negative guard test: a typed record whose mapped total genuinely disagrees with the ledger beyond tolerance still surfaces as a mismatch (SC-004) — assert `amount_match` false / mismatch detected.

## Phase 5: User Story 3 — legacy flat records unchanged (Priority: P2)

**Goal**: A pre-typed flat record produces the same reconciliation fields as before (no regression).
**Independent test**: pass-through tests assert flat record → identical reconciliation fields; mixed typed+flat group still reconciles.

- [x] T012 [US3] In `scripts/tests/test_type_mappers.py`, add legacy flat pass-through tests: a flat record (no `doc_type`, the `page_classifications.REQUIRED_KEYS` shape) → `to_reconciliation_fields` returns those exact values; extra/unknown keys ignored.
- [x] T013 [US3] Add a roll-up regression test: a flat-record attachment produces the same `extracted_amount`/`extracted_cnpj`/etc. as the pre-feature behavior (lock the legacy path); a shared-NF group mixing one typed + one flat record still reconciles.

## Phase 6: Polish & Cross-Cutting

- [x] T014 Add a module docstring to `type_mappers.py` documenting the per-type mapping table + the app-side/stdlib-only rationale (design T6); cross-reference `rollup-amount-false-positives.md` §Problem A and the design §10.2.
- [x] T015 Run `pnpm test:py` (full suite) + the tools suite; run `pnpm lint` and `pnpm format` (Prettier covers the spec docs). Confirm green and no new dependency in `scripts/pyproject.toml` / `package.json`.

## Dependencies

- Phase 1 → Phase 2 (mappers) → Phases 3/4/5 (US1 pure mapper, US2 wiring, US3 pass-through) → Phase 6.
- US1 and US3 are pure-mapper tests (depend only on Phase 2). US2 (wiring) depends on Phase 2 and is independent of US1/US3 test code.
- Within a phase, `[P]` tasks touch different test cases/files and may run in parallel.

## Implementation Strategy

- **MVP = Phase 1 + 2 + 3 (US1)**: the mappers exist and the 757dedb0 case is proven. Phase 4 (US2 wiring) delivers the actual false-positive elimination in the pipeline; Phase 5 (US3) locks the no-regression guarantee. Ship all phases in this one PR (the issue's acceptance spans all three).
