# Tasks: Typed document-extraction schema registry

**Feature**: `049-typed-extraction-schemas` | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests ARE requested (issue acceptance: "Schemas + registry + validator exist with unit tests"). Test tasks are included per user story.

All paths are relative to repo root `/home/agent/workspace/svhc-relatorios/`.

## Phase 1: Setup

- [x] T001 Create the self-contained module skeleton: `tools/doc-transcribe/__init__.py` (re-exports + `SCHEMA_VERSION`), `tools/doc-transcribe/schemas/`, `tools/doc-transcribe/examples/`, `tools/doc-transcribe/tests/__init__.py`. Ensure zero imports from `scripts/analysis`.

## Phase 2: Foundational (blocking prerequisites for all stories)

- [x] T002 Implement the registry in `tools/doc-transcribe/registry.py`: `SCHEMA_VERSION="1"`, `DOC_TYPES`, `ALIASES`, `canonical_type()`, `load_schema()` (loads + caches `schemas/<key>.json`), `schema_for()` (alias/unknown → `outro`, never raises), `supported_types()`. Per `contracts/api.md`.
- [x] T003 Implement the stdlib-only validator in `tools/doc-transcribe/validator.py`: `validate(payload, schema) -> list[str]` (type incl. nullable unions, enum, required, properties + `additionalProperties:false`, items, anyOf, `$ref` into `$defs`; bool-is-not-number; `$`/`.field`/`[i]` paths) and `validate_transcription(payload, doc_type)`. Per `contracts/api.md` + `data-model.md`.
- [x] T004 Wire the public API in `tools/doc-transcribe/__init__.py`: export `SCHEMA_VERSION`, `DOC_TYPES`, `schema_for`, `load_schema`, `supported_types`, `canonical_type`, `validate`, `validate_transcription`.

## Phase 3: User Story 1 — Schema author defines/extends the typed contract (P1)

**Goal**: Six JSON Schemas mirroring real Brazilian layouts, resolvable via the registry, each validating a real/representative example. **Independent test**: each type resolves to a valid schema, unknown→outro, each example validates.

- [x] T005 [P] [US1] Author `tools/doc-transcribe/schemas/danfe.json` (envelope `doc_type`/`schema_version`/`raw_text` + emitente/destinatário/itens/totais/duplicatas/chave_acesso/numero/serie/natureza/data per `data-model.md`; `$defs` for item/duplicata/party; every object `additionalProperties:false`; subset only).
- [x] T006 [P] [US1] Author `tools/doc-transcribe/schemas/nfse.json` (prestador/tomador/valores/retencoes/discriminacao per `data-model.md`).
- [x] T007 [P] [US1] Author `tools/doc-transcribe/schemas/boleto.json` (beneficiario/pagador/valor_documento/vencimento/linha_digitavel/nosso_numero/codigo_barras per `data-model.md`).
- [x] T008 [P] [US1] Author `tools/doc-transcribe/schemas/recibo.json` (pagador/recebedor/valor/data/referente_a/numero per `data-model.md`).
- [x] T009 [P] [US1] Author `tools/doc-transcribe/schemas/comprovante_pagamento.json` (tipo enum pix|ted|doc|boleto|outro|null, pagador/recebedor/valor/identificador/instituicao/data per `data-model.md`).
- [x] T010 [P] [US1] Author `tools/doc-transcribe/schemas/outro.json` (generic fallback: required `raw_text`, optional `descricao`, `valores_identificados[]{rotulo,valor}`; never blocks).
- [x] T011 [P] [US1] Author example fixtures `tools/doc-transcribe/examples/{danfe,nfse,boleto,recibo,comprovante_pagamento,outro}.json` — danfe = AGUA MARINHA `000006227` vNF=2790,00; nfse = the R$320 service note; representative others — each a complete, valid transcription of its schema.
- [x] T012 [US1] Write `tools/doc-transcribe/tests/test_registry.py`: every `DOC_TYPES` key resolves to a dict with matching `doc_type` enum + `schema_version`==SCHEMA_VERSION; aliases resolve (`comprovante`/`payment_proof`→comprovante_pagamento, `NF-e`/`nfe`→danfe, `nfs-e`→nfse); unknown/None/""→outro; `load_schema` raises KeyError on a non-DOC_TYPES key; `set(supported_types())` matches the schema files.
- [x] T013 [US1] Write `tools/doc-transcribe/tests/test_examples_validate.py`: for each type, `validate_transcription(load_example(t), t) == []` (FR-009 / SC-002).

## Phase 4: User Story 2 — Contract boundary validates a transcription (P1)

**Goal**: The stdlib validator catches every malformed-payload category with located messages. **Independent test**: positive + missing/wrong-type/extra-key/enum/non-object negatives.

- [x] T014 [US2] Write `tools/doc-transcribe/tests/test_validator.py`: positive (a valid nfse passes); negatives each return a non-empty located error — missing required `doc_type`; wrong type (`valor_liquido` as string); unknown extra key on an `additionalProperties:false` object; out-of-enum `doc_type`; non-object root (a list); `True` rejected for a `number` field; a valid `anyOf`/nullable union passes and a value matching no branch fails. Assert the error path format (`$`, `.field`, `[i]`).

## Phase 5: User Story 3 — Schemas stay within the structured-output subset (P2)

**Goal**: Automated proof the subset holds for every registered schema. **Independent test**: subset checker over all schemas.

- [x] T015 [US3] Write `tools/doc-transcribe/tests/test_subset_constraints.py`: walk every `load_schema(t)`; assert no disallowed keyword anywhere (`minimum`/`maximum`/`exclusive*`/`multipleOf`/`minLength`/`maxLength`/`pattern`/`min/maxItems`/`uniqueItems`/`min/maxProperties`/`format`/`if`/`then`/`else`/`not`/`allOf`/`oneOf`); every object node declares `additionalProperties:false`; every `$ref` is `#/$defs/<name>` and the `$defs` graph is acyclic (FR-007 / SC-004).

## Phase 6: Polish & Cross-Cutting

- [x] T016 Write `tools/doc-transcribe/README.md` (FR-010): each type's schema, the registry + alias map + fallback, the validator API + error-string format, the subset constraints, `SCHEMA_VERSION` semantics, and the explicit out-of-scope list (no transcriber/mappers/persistence/UI). Note the run-tests command.
- [x] T017 Run the full suite `uv run python -m unittest discover -s tools/doc-transcribe/tests -t tools/doc-transcribe` and confirm green; run `pnpm lint` (no TS changed → clean) and confirm no DB migration / dependency changed (SC-005).

## Dependencies

- Phase 1 (T001) → Phase 2 (T002–T004) → Phases 3–5.
- T002 (registry) blocks T012/T013; T003 (validator) blocks T013/T014; both block T015.
- Schema files T005–T010 block T011 examples and T012/T013/T015 tests.
- T016/T017 last.

## Parallel opportunities

- T005–T011 (the six schemas + examples) are all independent files → `[P]`.
- Within Phase 2, T002 and T003 touch different files and can proceed in parallel after T001.

## MVP scope

User Story 1 (the schemas + registry + their resolution/example tests) is the MVP — it alone delivers the contract the downstream EXTRACT issues consume. US2 (validator negatives) and US3 (subset proof) harden it.
