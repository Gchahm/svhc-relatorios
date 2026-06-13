# Implementation Plan: Typed document-extraction schema registry

**Branch**: `049-typed-extraction-schemas` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/049-typed-extraction-schemas/spec.md`

## Summary

Create the typed document-extraction **contract layer** (EXTRACT-001): six JSON Schemas mirroring real Brazilian fiscal document layouts (`danfe`, `nfse`, `boleto`, `recibo`, `comprovante_pagamento`, `outro`), a type→schema **registry** with `outro` fallback + alias map, a **stdlib-only validator** covering exactly the structured-output subset the schemas use, and a `SCHEMA_VERSION` constant. Schemas are `.json` data files; the registry + validator are thin Python. The module lives at `tools/doc-transcribe/` with **zero imports from `scripts/analysis`** (design §11.6) so it is independently reusable. Delivered with a unit-test suite (schemas validate real/representative example fixtures, validator catches every malformed-payload category, an automated subset checker). No DB/migration/UI/pipeline change (FR-011); no new dependency.

## Technical Context

**Language/Version**: Python 3.12 (stdlib only) for the registry + validator; JSON for the schema/fixture data. The repo runs Python via `uv`.
**Primary Dependencies**: None new. Python stdlib (`json`, `pathlib`, `unittest`). No pip/npm dependency added (FR-005, SC-005). Deliberately NOT adding `jsonschema`.
**Storage**: N/A — reads no D1/R2, writes nothing. Schemas + fixtures are static files in the repo.
**Testing**: Python stdlib `unittest`, discovered the same way as the existing analysis suite. New tests under `tools/doc-transcribe/tests/` (kept with the module so it stays self-contained/extractable) plus the existing `pnpm test:py` discovery is `scripts/tests`; this module is separate so it gets its own runner invocation documented in quickstart. (Alternative considered: put tests in `scripts/tests` — rejected because it would couple the reusable module to the app's test dir.)
**Target Platform**: CLI / library, runs anywhere Python 3.12 runs. No edge-runtime concern (this is build/tooling Python, not the Next.js Worker).
**Project Type**: Single self-contained Python tooling module (`tools/doc-transcribe/`), parallel to `scripts/`.
**Performance Goals**: N/A (contract definition + a small pure validator; validation is O(size of payload)).
**Constraints**: stdlib-only; schemas confined to the structured-output subset (objects/arrays/enums/`anyOf`/`$ref`, `additionalProperties:false`, no numeric/length/pattern bounds, no recursion).
**Scale/Scope**: 6 schemas, 1 registry module, 1 validator module, 6 example fixtures, ~3 test files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — ✅ No Drizzle/auth schema touched; no DB schema change (FR-011). The JSON Schemas ARE the new contract and are explicit/typed. Python uses type hints. PASS.
- **II. Cloudflare-Native Architecture** — ✅ No DB access at all; no bindings; this is offline tooling Python (like `scripts/`). PASS.
- **III. Quality Gates Before Commit** — ✅ The issue explicitly requests unit tests; they are included and MUST pass. `pnpm lint`/`pnpm format` apply to TS — no TS changed; Python follows the repo's stdlib-`unittest` convention. `pnpm format` (Prettier) is run; it will not touch the new `.py`/`.json` unless configured to, and we keep JSON valid. PASS.
- **IV. Security & Auth by Default** — ✅ No routes, no data exposure, no secrets. PASS.
- **V. Simplicity & Incremental Delivery** — ✅ Smallest thing that satisfies the contract: data-file schemas + a minimal subset-only validator (NOT a full JSON Schema engine), no new dependency. This is a single, independently shippable foundation increment that unblocks EXTRACT-002…006. PASS.

No violations — Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/049-typed-extraction-schemas/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the validator/registry API contract)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
tools/
└── doc-transcribe/
    ├── README.md                       # FR-010: documents schemas, registry, validator, subset, SCHEMA_VERSION
    ├── __init__.py                      # re-exports registry/validator public API; defines SCHEMA_VERSION
    ├── registry.py                      # SCHEMA_VERSION, DOC_TYPES, ALIASES, load_schema()/schema_for()/supported_types()
    ├── validator.py                     # stdlib validate(payload, schema) + validate_transcription(payload, doc_type)
    ├── schemas/
    │   ├── danfe.json
    │   ├── nfse.json
    │   ├── boleto.json
    │   ├── recibo.json
    │   ├── comprovante_pagamento.json
    │   └── outro.json
    ├── examples/                        # FR-009: real/representative example transcriptions (test fixtures)
    │   ├── danfe.json                   # AGUA MARINHA 000006227, vNF 2790,00
    │   ├── nfse.json                    # R$320 service note (the 757dedb0 case)
    │   ├── boleto.json
    │   ├── recibo.json
    │   ├── comprovante_pagamento.json
    │   └── outro.json
    └── tests/
        ├── __init__.py
        ├── test_registry.py             # resolution, fallback, aliases, SCHEMA_VERSION
        ├── test_validator.py            # positive + negative (missing/wrong-type/extra-key/enum/non-object)
        ├── test_examples_validate.py    # each example validates against its schema (FR-009)
        └── test_subset_constraints.py   # subset checker over every registered schema (FR-007)
```

**Structure Decision**: A single self-contained tooling module at `tools/doc-transcribe/`, mirroring the design doc's §11.6 placement. Schemas/examples are JSON data; only `registry.py`/`validator.py` are code. Tests live inside the module so it remains extractable to its own repo with no untangling. Nothing imports from `scripts/analysis`; the only contract between this module and the app is the typed JSON.

## Phase 0 — Research

See `research.md`. Key resolved decisions: structured-output subset keyword list; the minimal validator's supported keyword set; the canonical field layouts for each Brazilian doc type (national standards for NF-e/DANFSe); the `comprovante_pagamento` canonical key + alias mapping; `SCHEMA_VERSION = "1"`.

## Phase 1 — Design & Contracts

- `data-model.md` — the per-type schema field inventory + the registry/validation-result entities.
- `contracts/` — the registry + validator API contract (function signatures, return shapes, error-string format) and the subset-constraint contract.
- `quickstart.md` — how to resolve a schema, validate a payload, run the tests.
- Agent context update via the speckit script.

## Complexity Tracking

> No constitution violations — table intentionally empty.
