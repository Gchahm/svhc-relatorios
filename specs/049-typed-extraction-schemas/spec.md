# Feature Specification: Typed document-extraction schema registry

**Feature Branch**: `049-typed-extraction-schemas`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Typed document-extraction schema registry: JSON Schemas per Brazilian fiscal doc type (danfe, nfse, boleto, recibo, comprovante_pagamento, outro), a type-to-schema registry, and a stdlib-only validator with schema_version. Closes #83"

## Overview

Today the document-vision step emits a flat ~10-field object and asks the model to *interpret* the page ("which number is the total"), which both throws away almost everything on the page and turns interpretation errors into data errors (the documented `757dedb0` R$800-vs-R$320 misread). The target architecture (design doc §10–§11) splits that one fuzzy step into **transcribe everything into a typed schema** then **derive reconciliation fields with a deterministic mapper**.

This feature (EXTRACT-001) is the **foundation** of that architecture: it defines the **typed JSON-Schema contract** every later piece (the transcriber backend, the deterministic mappers, the persistence adapter, the type-aware UI) builds on. It delivers **only** the schemas, a type→schema registry, a stdlib-only validation helper, and a `schema_version` constant — no transcriber, no mappers, no persistence change, no UI change, no wiring into `record-classification`. Those are separate downstream issues (EXTRACT-002 … EXTRACT-006).

## Clarifications

### Session 2026-06-13 (resolved autonomously — unattended run)

- Q: What concrete home for the contract layer? → A: `tools/doc-transcribe/` with a `schemas/` dir of `.json` files plus a `registry.py` (registry + `SCHEMA_VERSION`) and `validator.py` (stdlib validator); zero imports from `scripts/analysis` (design §11.6, Assumption A1/A2).
- Q: Validator return shape? → A: A pure function `validate(payload, schema) -> list[str]` returning a list of located, human-readable error strings (empty == valid); plus a convenience `validate_transcription(payload, doc_type) -> list[str]` that resolves the schema via the registry. No exceptions on validation failure (only on a malformed schema/programmer error).
- Q: How does a payload self-identify its type? → A: Each schema requires a top-level `doc_type` field as a single-value `enum` (e.g. `["danfe"]`), and a top-level `schema_version` field as a single-value `enum` (e.g. `["1"]`); both are required (FR-008). The registry's resolver also accepts a raw type string for callers that detect type out-of-band.
- Q: Are the `comprovante`/`payment_proof` aliases mapped now? → A: Yes — the registry records an alias map so the existing flat taxonomy resolves onto the new canonical `comprovante_pagamento` key, but the current flat `record-classification` contract is left untouched (Assumption A3, FR-011).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A schema author defines/extends the typed contract (Priority: P1)

A developer building the transcriber or a mapper needs a single, authoritative place that says exactly what a fully-transcribed `danfe` / `nfse` / `boleto` / `recibo` / `comprovante_pagamento` / `outro` looks like — every field present on the real Brazilian layout, named and typed — and a registry that resolves a detected document type to its schema. Adding a new document type is "add a schema + register it"; nothing else in the contract layer changes.

**Why this priority**: It is the contract that unblocks every other EXTRACT issue. Without it, the transcriber has nothing to fill and the mappers have nothing to read.

**Independent Test**: Resolve each supported type through the registry and confirm a valid JSON Schema is returned; confirm an unknown type resolves to the `outro` fallback; confirm a real example page from the corpus for each type validates against its schema.

**Acceptance Scenarios**:

1. **Given** the registry, **When** a caller requests the schema for `danfe`, **Then** it returns the DANFE/NF-e JSON Schema (with emitente, destinatário, items, totais, chave de acesso).
2. **Given** the registry, **When** a caller requests the schema for an unrecognized type string, **Then** it resolves to the `outro` generic-fallback schema rather than raising.
3. **Given** a schema and a real example transcription for that type (drawn from documented corpus pages), **When** the example is validated, **Then** validation passes.

### User Story 2 - A contract boundary validates a transcription against its type schema (Priority: P1)

The future `record-classification` adapter (EXTRACT-004) and the transcriber's own post-backend check (EXTRACT-002/003) need to validate a candidate transcription against the chosen type's schema **using only the Python standard library** — the `analysis` package is deliberately stdlib-only (CLAUDE.md), and the `cli` transcriber backend has no wire-level schema enforcement, so a local validator is mandatory and must not pull in a new pip dependency.

**Why this priority**: Validation is the guarantee that backends are interchangeable and that bad payloads are caught at the boundary. It is delivered here so downstream issues only have to *call* it.

**Independent Test**: Feed the validator a conforming transcription (passes, no errors) and several non-conforming ones (missing a required field, wrong JSON type, an unknown extra key, an out-of-enum value) and confirm each is reported with a clear, located error message.

**Acceptance Scenarios**:

1. **Given** a valid `nfse` transcription, **When** validated against the `nfse` schema, **Then** the validator reports success with no errors.
2. **Given** a transcription missing a required field, **When** validated, **Then** the validator reports the missing field by path.
3. **Given** a transcription with an extra unspecified key on an `additionalProperties:false` object, **When** validated, **Then** the validator rejects it (mirroring the structured-output `additionalProperties:false` rule).
4. **Given** a value outside an enum (e.g. a `doc_type` not in the registry), **When** validated, **Then** the validator reports the enum violation.

### User Story 3 - Schemas stay within the structured-output subset (Priority: P2)

The EXTRACT-002 `api` transcriber backend will hand these schemas to the Anthropic Messages API structured-output feature, which supports objects/arrays/enums/`anyOf`/`$ref` and requires `additionalProperties:false`, but rejects numeric/length bounds (`minimum`/`maxLength`/…) and recursion. The same schemas must be safe to send at the wire, so they must stay within that subset.

**Why this priority**: A schema that uses an unsupported keyword would be silently stripped (changing its meaning) or rejected by the API backend. Enforcing the subset here keeps the contract honest for the `api` backend that consumes it later.

**Independent Test**: A test walks every schema in the registry and asserts no disallowed keyword (`minimum`, `maximum`, `minLength`, `maxLength`, `minItems`, `maxItems`, `pattern`, `format`-as-constraint) appears, that every `object` declares `additionalProperties:false`, and that no `$ref` forms a cycle.

**Acceptance Scenarios**:

1. **Given** any schema in the registry, **When** the subset checker walks it, **Then** it finds no numeric/length/pattern bound and no recursive `$ref`.
2. **Given** any `object`-typed node in any schema, **When** inspected, **Then** it declares `additionalProperties: false`.

### Edge Cases

- **Unknown / unconfident document type** → resolves to `outro`, whose schema captures best-effort key/values plus the full raw page text and **never blocks** (all fields nullable/optional except a required raw-text container).
- **A `null` value for a transcribable-but-absent field** → schemas permit `null` for optional/absent fields via `["<type>","null"]` or `anyOf`, never forcing `0`/empty-string sentinels.
- **Validation of a payload that is not a JSON object** (e.g. a list, or the legacy `{"error": "..."}` shape) → the validator reports a clear top-level error rather than crashing.
- **Schema evolution** → a `SCHEMA_VERSION` constant lets old flat rows and new typed rows coexist downstream; bumping it is the documented signal that the contract changed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a JSON Schema for each document type in the corpus: `danfe` (NF-e), `nfse` (DANFSe), `boleto`, `recibo`, `comprovante_pagamento`, and `outro` (generic fallback).
- **FR-002**: Each typed schema MUST mirror the real Brazilian layout for its type — for `danfe`/`nfse`: emitente block (nome, CNPJ/CPF, IE, endereço), destinatário block, item list (descrição, quantidade, valor unitário, valor total, and NF-e codes NCM/CFOP where applicable), a totais block (`danfe`: `valor_total_nota`/vNF, base+valor de ICMS, valor dos produtos; `nfse`: `valor_servico`/`valor_liquido`/retenções), `chave_acesso` (transcribed as a string), número, série, data de emissão, natureza/discriminação; for `boleto`: beneficiário, pagador, `valor_documento`, vencimento, linha digitável, nosso número; for `recibo`/`comprovante_pagamento`: pagador/recebedor (beneficiário/favorecido), valor pago, data, meio de pagamento (PIX/TED/boleto), identificadores (autenticação/end-to-end).
- **FR-003**: The system MUST provide a registry that maps a detected document-type string to its schema, and MUST resolve any unrecognized type to the `outro` fallback schema (never raise on an unknown type).
- **FR-004**: Adding a new document type MUST require only adding a schema and registering it — no change to the validator or to existing schemas.
- **FR-005**: The system MUST provide a validation helper, implemented using **only the Python standard library** (no new pip dependency), that validates a candidate transcription against a given schema and returns a clear, located list of errors (empty on success).
- **FR-006**: The validator MUST enforce: required keys present; declared JSON types (including `["<type>","null"]` unions and `anyOf`); `enum` membership; `additionalProperties:false` rejection of unknown keys; arrays' `items`; and `$ref` resolution within the schema's `$defs`.
- **FR-007**: Every schema MUST stay within the structured-output subset: objects/arrays/enums/`anyOf`/`$ref`, every object declaring `additionalProperties:false`, and **no** numeric/length/pattern bounds and **no** recursive `$ref`. The system MUST include an automated check (a test) that asserts this subset holds for every registered schema.
- **FR-008**: The system MUST expose a `SCHEMA_VERSION` constant (a stable identifier of the contract version) so downstream consumers can distinguish typed rows from legacy flat rows and detect contract changes. Each schema MUST carry a `doc_type` discriminator (an enum with the single type value) so a payload self-identifies its type.
- **FR-009**: Each schema MUST validate at least one real/representative example transcription drawn from the corpus (the documented `danfe` AGUA MARINHA `000006227` with vNF=2790,00 and the `nfse` R$320 service note, plus representative examples for the remaining types), proven by unit tests.
- **FR-010**: The contract artifacts MUST be documented (a README/module docstring) describing each type's schema, the registry, the validator API, the subset constraints, and the `SCHEMA_VERSION` semantics.
- **FR-011**: This feature MUST NOT change live pipeline behavior — no DB schema/migration, no change to `record-classification`'s current flat-field contract, no transcriber, no mappers, no UI change. It only **adds** the contract layer for later issues to consume.

### Key Entities *(include if feature involves data)*

- **Document-type schema**: a JSON Schema describing the complete typed transcription of one Brazilian fiscal document type (`danfe`, `nfse`, `boleto`, `recibo`, `comprovante_pagamento`, `outro`). Mirrors the real layout; stays within the structured-output subset.
- **Schema registry**: a mapping from a document-type string to its schema, with `outro` as the fallback for any unrecognized type, and a list of supported types. Extensible by adding one entry.
- **Validation result**: the outcome of validating a candidate transcription against a schema — success with no errors, or a located list of human-readable errors (path + reason).
- **`SCHEMA_VERSION`**: a constant identifying the contract version, used downstream to distinguish typed from legacy flat rows.

## Assumptions

- **A1 — Placement.** The design doc proposes a self-contained, reuse-oriented module at `tools/doc-transcribe/` (design §11.6), deliberately with **zero imports from `scripts/analysis`**. The schemas are the most portable, project-agnostic piece (national-standard layouts), so they live there. The directory does not yet exist; this feature creates it. The stdlib-only validator lives alongside the schemas so the `cli` backend (no SDK) and the future `analysis`-side adapter can both call it without a new dependency. (The deterministic mappers — EXTRACT-005 — stay app-side per design §11.4/T6 and are out of scope here.)
- **A2 — Schema language.** JSON Schema (draft-2020-12 vocabulary, restricted to the structured-output subset) is the format, per design T1/T5 ("JSON Schema is both the prompt spec and the wire contract"). Schemas are stored as `.json` files (data, not code) plus a thin Python registry/validator wrapper, so they are equally usable as the API `output_config` schema, the prompt spec, and the local validation target.
- **A3 — `comprovante_pagamento` vs `comprovante`.** The issue names the type `comprovante_pagamento`; today's flat contract uses `comprovante`/`payment_proof`. This feature uses the issue's `comprovante_pagamento` as the canonical registry key and records aliases (`comprovante`, `payment_proof`) so the future adapter can map the existing taxonomy onto the new one. No change to the current flat contract is made here.
- **A4 — Real example corpus.** "A real example page from the corpus" is satisfied with example transcriptions modeled on the concrete corpus pages documented in the design doc (the `8293d3db` DANFE — `000006227`, AGUA MARINHA, vNF=2790,00; the `757dedb0` NFS-e — R$320 service) plus representative examples (boleto, recibo, comprovante, outro) built to match real Brazilian layouts. These examples are committed as test fixtures.
- **A5 — Validator depth.** The validator covers exactly the subset the schemas use (types incl. nullable unions, `required`, `enum`, `additionalProperties:false`, `items`, `anyOf`, `$ref`/`$defs`). It deliberately does NOT implement the full JSON Schema spec (no bounds/patterns/formats — those are excluded by the subset anyway), keeping it small, stdlib-only, and unit-tested.
- **A6 — `SCHEMA_VERSION` value.** Set to `"1"` (string) for the initial contract; the convention is a monotonically increasing string bumped on any breaking contract change.
- **A7 — Verification.** Because there is no app-facing behavior (FR-011), verification of this foundation is via the unit-test suite (schemas validate examples, validator catches violations, subset holds) run through the project's Python test runner; there is no dashboard surface to drive. The PR records the test run as the verification evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six document types (`danfe`, `nfse`, `boleto`, `recibo`, `comprovante_pagamento`, `outro`) resolve through the registry to a valid schema, and an unknown type resolves to `outro` — 100% of supported types covered, proven by tests.
- **SC-002**: Each schema validates its real/representative example transcription with zero validation errors — 6/6 example fixtures pass.
- **SC-003**: The validator correctly rejects every category of malformed payload it is responsible for (missing required, wrong type, unknown extra key, out-of-enum, non-object root) — 100% of negative cases reported with a located message, proven by tests.
- **SC-004**: The structured-output subset holds for 100% of registered schemas (no disallowed keyword, every object `additionalProperties:false`, no recursive `$ref`), proven by an automated subset checker test.
- **SC-005**: The contract adds zero new pip/npm dependencies and makes zero DB schema/migration/pipeline-behavior changes (validated by the unchanged migration set and a stdlib-only import).
