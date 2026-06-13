# Feature Specification: Standalone vision transcriber module (image → typed JSON)

**Feature Branch**: `052-vision-transcriber`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "EXTRACT-002: standalone vision transcriber module under tools/doc_transcribe that turns a fiscal-document image into typed JSON (transcribe() library function + CLI), validating against the EXTRACT-001 schema above a pluggable backend — default 'cli' (shells out to `claude -p`, no anthropic SDK / no ANTHROPIC_API_KEY) and optional 'api' (Anthropic Messages API with json_schema structured outputs, anthropic SDK as optional extra). Closes #86"

## Clarifications

### Session 2026-06-13

- Q: How does the `cli` backend extract JSON when `claude -p` wraps it in prose or a ```` ```json ```` fence? → A: Best-effort extraction — strip a leading/trailing markdown code fence, then parse the largest balanced `{...}` block; if no JSON parses, return an `outro` best-effort object with a `parse_errors` entry (never raise).
- Q: What does the result's top-level `doc_type` reflect when validation fails on a caller-forced type? → A: The resolved canonical `doc_type` is always authoritative (forced type wins over the model's echo for an explicit type; model detection wins for `"auto"`); validation failures are reported in `parse_errors`, they never change `doc_type`.
- Q: Does the `api` backend stream or use a single non-streaming call? → A: Single non-streaming `messages.parse()`-style call with `output_config.format` json_schema (adaptive thinking, `claude-opus-4-8` default); single-call extraction is the right surface per design §11.3.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcribe a fiscal-document image to validated typed JSON via the default backend (Priority: P1)

A pipeline (or a triage agent doing a one-off correction) hands the transcriber a fiscal-document
page image and gets back a typed-JSON object that conforms to the EXTRACT-001 contract: the document
type the model detected, the schema version, the typed fields for that type, and — if anything in the
returned shape failed validation — a list of parse errors. The default path requires only the
`claude` binary already on the machine (the existing Claude Code login); it needs no Anthropic API key
and the module imports even when the `anthropic` SDK is not installed. Because the model call runs in
its own subprocess, the page image never enters the caller's context.

**Why this priority**: This is the reusable capability the whole EXTRACT line is built around —
"fiscal-document image → typed JSON" — and the `cli` backend is the default because it matches the
repo's current auth posture (no new secret) and serves the primary use case (per-document on-demand
transcription). Without it the module delivers nothing.

**Independent Test**: Call `transcribe(image, doc_type="auto")` (and the equivalent CLI) on a sample
page with the backend stubbed to return a known JSON body; assert the result is a typed object whose
`fields` validate against the registry schema for the detected type, with no `parse_errors`. Confirm
the module imports with `anthropic` absent and with no `ANTHROPIC_API_KEY` set.

**Acceptance Scenarios**:

1. **Given** a fiscal-document image and the default backend, **When** `transcribe` is called, **Then**
   it returns `{ doc_type, schema_version, fields }` where `fields` validates clean against the
   EXTRACT-001 schema for `doc_type` and no `parse_errors` key is present.
2. **Given** a caller passes an explicit `doc_type` (e.g. `"recibo"`), **When** `transcribe` is called,
   **Then** the returned `doc_type` is the canonical resolution of that type and `fields` is validated
   against that type's schema.
3. **Given** the `anthropic` SDK is not installed and `ANTHROPIC_API_KEY` is unset, **When** the module
   is imported and the default backend is used, **Then** import succeeds and transcription works.
4. **Given** the backend returns JSON that is missing a required field or has a wrong-typed field,
   **When** `transcribe` validates it, **Then** the result still returns the (best-effort) typed object
   AND a non-empty `parse_errors` list describing each validation failure — it does not raise.

---

### User Story 2 - Transcribe via the Anthropic API backend with wire-enforced typed shape (Priority: P2)

For bulk / production transcription, a caller selects the `api` backend. The transcriber calls the
Anthropic Messages API with the page image and the chosen type's JSON Schema as a structured-output
`json_schema`, so the typed shape is enforced at the wire, then re-validates the returned JSON against
the same schema above the backend. This backend needs the `anthropic` SDK (an optional extra) and an
`ANTHROPIC_API_KEY`; selecting it without those present fails with a clear, actionable error rather
than a confusing crash.

**Why this priority**: The `api` backend unlocks the bulk re-classification campaign (Batch + prompt
caching) that the `cli` backend cannot do. It is secondary because the default `cli` path already
delivers the core capability and the `api` backend's dependency + secret are deliberately optional.

**Independent Test**: With the Anthropic client stubbed, call `transcribe(image, backend="api")` and
assert the request carries an image block and the resolved type's schema as the structured-output
format, that the validated typed object is returned, and that selecting `api` with the SDK missing or
the key unset produces a clear error.

**Acceptance Scenarios**:

1. **Given** the `api` backend, the SDK installed, and a key set, **When** `transcribe` is called,
   **Then** the API request includes the page image and the type's schema as the enforced output
   format, and the returned JSON is re-validated above the backend.
2. **Given** the `api` backend is selected but the `anthropic` SDK is not installed, **When**
   `transcribe` is called, **Then** it raises a clear error naming the missing optional dependency
   (e.g. "install the `api` extra"), not an opaque `ImportError` at module top level.
3. **Given** the `api` backend is selected but `ANTHROPIC_API_KEY` is unset, **When** `transcribe` is
   called, **Then** it raises a clear error stating the key is required for the `api` backend.

---

### User Story 3 - Use the transcriber as a command-line tool (Priority: P2)

An operator (or an orchestrator script) runs the transcriber as a CLI: `transcribe --image <path>
[--type auto] [--backend cli|api]` and gets the typed-JSON object printed to stdout, ready to pipe
into a downstream step. The CLI is a thin wrapper over the same library function, so it behaves
identically and stays within the self-contained module.

**Why this priority**: The design specifies the transcriber is exposed as **both** a library function
and a CLI; the CLI is how an orchestrator shells out per page (keeping images out of its context).
Secondary because it is a thin surface over the P1 library function.

**Independent Test**: Run the CLI against a sample image with the backend stubbed and assert it prints
a single JSON object to stdout matching the library result, and exits non-zero with a readable message
on a missing image / unselectable backend.

**Acceptance Scenarios**:

1. **Given** a valid image path, **When** the CLI is run with `--image <path>`, **Then** it prints one
   typed-JSON object to stdout and exits 0.
2. **Given** a missing image path or an unusable backend, **When** the CLI is run, **Then** it prints a
   readable error to stderr and exits non-zero.

---

### Edge Cases

- **Backend returns non-JSON / malformed JSON**: the transcriber surfaces this as a `parse_errors`
  entry on an `outro`-typed best-effort object (so the contract still holds), rather than raising — a
  garbled response must not crash a bulk run.
- **Model reports an unknown / unconfident `doc_type`**: resolved through the registry's alias map to a
  canonical type, falling back to `outro` (which never blocks). The returned `doc_type` is always a
  canonical EXTRACT-001 type.
- **`schema_version` mismatch**: the transcriber always stamps the result with the registry's current
  `SCHEMA_VERSION`; a version the model echoes back is ignored in favor of the authoritative constant.
- **`doc_type="auto"`**: the model detects the type; the result's `doc_type` reflects the detection (no
  caller-forced type).
- **Large or unreadable image file**: the CLI / library fails with a clear error before invoking a
  backend.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The module MUST expose a library function `transcribe(image, doc_type="auto") → { doc_type,
  schema_version, fields, parse_errors? }` where `image` accepts a file path (and, where practical, raw
  image bytes), `doc_type` accepts `"auto"` or any of the EXTRACT-001 types, `fields` is the typed JSON
  for the resolved type, and `parse_errors` is present only when validation found problems.
- **FR-002**: The module MUST expose an equivalent command-line interface (`transcribe --image <path>
  [--type auto] [--backend ...]`) that prints the same typed-JSON object to stdout.
- **FR-003**: The module MUST place schema validation **above** the backend: whichever backend produces
  the JSON, the module validates the returned shape against the EXTRACT-001 schema for the resolved
  `doc_type` before returning, and records any failures in `parse_errors`.
- **FR-004**: The module MUST support a pluggable backend selected by a `backend` argument with values
  `"cli"` (default) and `"api"`, behind one interface, so the rest of the module is independent of which
  backend ran.
- **FR-005**: The `cli` backend MUST shell out to the `claude` binary (`claude -p`, headless Claude
  Code) in its own subprocess, requiring **no** `ANTHROPIC_API_KEY` and **no** `anthropic` SDK
  dependency, and keeping page images out of any orchestrator's context.
- **FR-006**: The `api` backend MUST call the Anthropic Messages API via the `anthropic` SDK using the
  resolved type's JSON Schema as a structured-output `json_schema` so the typed shape is enforced at the
  wire, and MUST require an `ANTHROPIC_API_KEY`.
- **FR-007**: The `anthropic` SDK MUST be an **optional** dependency: the module MUST import and the
  `cli` backend MUST work with the SDK absent. Selecting the `api` backend without the SDK installed or
  without the key set MUST fail with a clear, actionable error (not an opaque module-load failure).
- **FR-008**: The transcriber MUST be transcribe-only: it records what the page shows into the typed
  schema and MUST NOT decide reconciliation values (that is EXTRACT-003) — no field is computed/derived
  beyond what the model transcribed.
- **FR-009**: Every result MUST carry the full raw page text (the evidence floor). This is satisfied by
  the EXTRACT-001 envelope, where `raw_text` is a standard required field on **every** type's schema
  (not only `outro`) — so the typed `fields` always include the verbatim transcription.
- **FR-010**: The module MUST NOT import from `scripts/analysis` (it stays self-contained and
  extractable, per the design), and MUST add **no** new mandatory pip/npm dependency (the `cli` backend
  needs only the `claude` binary; the `api` backend's SDK is an optional extra).
- **FR-011**: The module MUST resolve a model's reported/forced `doc_type` through the EXTRACT-001
  registry (aliases + `outro` fallback) and stamp the result with the registry's `SCHEMA_VERSION`, so
  the returned `doc_type`/`schema_version` are always authoritative canonical values.
- **FR-012**: The module's pure surface (the validate-above-backend assembly, type resolution, error
  capture, request assembly) MUST be unit-tested with the repo's stdlib `unittest` convention and a
  stubbed/injected backend (no real `claude` subprocess, no real API call, no network) — mirroring the
  EXTRACT-001 test layout under `tools/doc_transcribe/tests/`.

### Key Entities *(include if feature involves data)*

- **Transcription result**: the returned object — `doc_type` (canonical EXTRACT-001 type),
  `schema_version` (registry constant), `fields` (the typed JSON for that type, conforming to the
  EXTRACT-001 schema, including the required `raw_text`), and optional `parse_errors` (a list of
  located validation-error strings, present only when validation found problems).
- **Backend**: the swappable model-call seam — one interface with two implementations (`cli` shelling
  out to `claude -p`; `api` calling the Anthropic Messages API). Takes the page image + the resolved
  type's schema/instruction, returns raw JSON text; knows nothing about validation, the registry, or
  persistence.
- **Document type**: one of the EXTRACT-001 canonical types (`danfe`, `nfse`, `boleto`, `recibo`,
  `comprovante_pagamento`, `outro`), resolved via the registry. `"auto"` defers detection to the model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Both backends return a typed-JSON result that validates clean against the EXTRACT-001
  schema for the resolved type on sample pages (with the backend stubbed for the test, and against a
  representative live page in manual verification).
- **SC-002**: The module imports and the default (`cli`) backend functions with the `anthropic` SDK not
  installed and with `ANTHROPIC_API_KEY` unset — verified by an import + transcribe path that touches
  neither.
- **SC-003**: The `api` backend enforces the typed shape at the wire (the type's JSON Schema is sent as
  the structured-output format) and the same shape is re-validated above the backend — verified with the
  client stubbed.
- **SC-004**: The module contains **zero** imports of `scripts/analysis` and adds **zero** new mandatory
  dependencies (the `api` SDK is an optional extra) — verifiable by inspection and by the test suite
  running with no extra install.
- **SC-005**: 100% of malformed/invalid backend responses are surfaced as a returned result with
  `parse_errors` (or an `outro` best-effort object) rather than an unhandled exception in a bulk run.

## Assumptions

- **`fields` envelope vs. the EXTRACT-001 flat shape.** The design's interface returns `{ doc_type,
  schema_version, fields }`. The EXTRACT-001 schemas are flat objects whose top level already includes
  `doc_type`, `schema_version`, and `raw_text`. The result's `fields` is therefore the full
  EXTRACT-001-conformant object for the type (carrying its own `doc_type`/`schema_version`/`raw_text`
  plus the type-specific blocks); the top-level `doc_type`/`schema_version` on the result mirror those
  authoritative values for caller convenience. This keeps validation a direct call to the EXTRACT-001
  `validate_transcription` with no reshaping.
- **`texto_integral` decision** (design §11.2 open item): the full raw text is a **standard field on
  every type** (`raw_text`, already required by every EXTRACT-001 schema), not only on `outro` — chosen
  so the evidence floor exists for every transcription. No schema change is needed; this feature only
  relies on that existing contract.
- **Model tier for the `api` backend** (design T4): defaults to `claude-opus-4-8` (best fidelity for
  dense fiscal documents), overridable by the caller. The `cli` backend uses whatever model the local
  Claude Code session is configured with.
- **Deterministic mappers (T6) are out of scope** — they stay app-side (EXTRACT-003/005); this module
  is transcribe-only.
- **No DB schema change, no migration, no app-code change, no UI change.** This is a new self-contained
  module under `tools/doc_transcribe/`, alongside the EXTRACT-001 contract.
- The `cli` backend's prompt instructs the local Claude Code model to transcribe the page into the
  resolved type's JSON Schema and emit only JSON; the module parses + validates that JSON (the CLI does
  not enforce a schema, which is exactly why the module's own validation layer is mandatory).
- The transcriber's tests run with the same `-t tools` discovery as EXTRACT-001 and add no CI wiring
  beyond what already exists for the module (wiring `tools/` tests into CI is a separate follow-up).
