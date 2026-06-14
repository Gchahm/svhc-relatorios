# Feature Specification: Persist typed transcriptions + flat-row coexistence

**Feature Branch**: `055-typed-record-persistence`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Persist typed transcription JSON in attachment_analysis_records.response tagged with schema_version, with record-classification validating typed payloads against the EXTRACT-001 schema and legacy flat rows still working (dual-path mapper + UI)"

## Context

This is the pipeline-wiring step (issue #89, EXTRACT-004) that lands the typed full-document
transcription contract (EXTRACT-001 schema registry, EXTRACT-002 transcriber, EXTRACT-003
deterministic per-type mappers — all merged) into the live classification pipeline. The goal is a
**gradual, non-breaking** rollout (design decision T2): new classifications persist the rich typed
JSON, old flat rows keep reading and reconciling exactly as before, and a schema-invalid typed
payload is rejected at the contract gate. No database migration: the rich JSON lives in the existing
`attachment_analysis_records.response` TEXT column (and the `page_classifications.response` staging
TEXT column it flows through).

## Clarifications

### Session 2026-06-13

Running unattended (no interactive reviewer). The architecture-impacting ambiguities are resolved
below with the best-practice answer for this codebase; each is also reflected in the Assumptions /
Functional Requirements.

- Q: How does `record-classification` (in `scripts/analysis`, which must not import `tools/`) reach
  the EXTRACT-001 schema to validate a typed payload? → A: Run the validation **above** the analysis
  package — make `tools/` importable from the `analysis` CLI process by adding the repo's `tools/`
  dir to `sys.path` at the CLI entry point and validating the typed payload with
  `doc_transcribe.validate_transcription` **in the CLI layer / a thin gate module**, NOT inside the
  stdlib-only `page_classifications` module. The analysis *library* code (roll-up, mappers) still
  never imports `tools/`; only the executable contract gate does. (Rationale: `record-classification`
  is the runtime contract gate, and `transcribe()` already shows `tools/` is meant to be imported by
  callers; the design's no-import rule protects the reusable *library*, which is preserved.)
- Q: What distinguishes a typed row from a flat row everywhere (store/derive/render)? → A: The
  presence of a `doc_type` key in the stored response (consistent with the already-shipped
  EXTRACT-003 mapper). A single shared helper owns this predicate (FR-008).
- Q: Are existing periods re-classified into typed schemas by this feature? → A: No — gradual rollout
  (design T2); legacy flat rows keep working via the mapper's identity pass-through.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New typed classifications persist and reconcile (Priority: P1)

A document classified with the typed transcription contract records a rich, per-type JSON for each
page. That JSON is validated at the contract gate, stored verbatim (tagged with its schema version),
and the reconciliation values the pipeline needs (total / issuer / number / date) are derived from
it deterministically so the existing analysis checks (amount/vendor/date match, shared-NF
reconciliation, documents entity, alerts) behave correctly.

**Why this priority**: This is the core capability the issue asks for — without it the typed
transcriber is built but never used by the running pipeline. It is the MVP slice.

**Independent Test**: Record a typed page payload via `record-classification`, run
`apply-extractions` → `analyze`, and confirm (a) the stored record carries the typed JSON with its
schema version, and (b) the rolled-up `attachment_analyses` reconciliation fields match what the
per-type mapper derives (e.g. an NFS-e reconciles on its `valor_liquido`).

**Acceptance Scenarios**:

1. **Given** a valid typed NFS-e payload, **When** it is recorded and applied, **Then** the page
   record's stored response is the typed JSON (carrying `doc_type` and `schema_version`), and the
   attachment roll-up's reconciliation total equals the NFS-e net (`valor_liquido`).
2. **Given** a valid typed DANFE payload, **When** it is recorded and applied, **Then** the roll-up
   reconciliation total equals the DANFE `totais.valor_total_nota` and the issuer CNPJ/name come from
   the `emitente` block.
3. **Given** a typed payload, **When** it is stored, **Then** it carries a `schema_version` tag so a
   reader can tell a typed row from a legacy flat row.

---

### User Story 2 - Legacy flat rows still read and reconcile (Priority: P1)

A page classified before the typed contract (a flat ~10-field object) continues to read, roll up,
reconcile, and render in the UI with no change in behavior. The rollout is additive.

**Why this priority**: A regression here would silently corrupt the entire existing corpus of
classified data. The no-regression guarantee is as critical as the new capability.

**Independent Test**: Record a legacy flat payload (no `doc_type`), apply and analyze, and confirm
the rolled-up reconciliation fields and the UI render are byte-identical to the pre-feature behavior.

**Acceptance Scenarios**:

1. **Given** a legacy flat payload (no `doc_type` discriminator), **When** it is recorded, **Then**
   it is accepted by the contract gate using the existing flat-field contract.
2. **Given** a stored legacy flat record, **When** the attachment is rolled up, **Then** the
   reconciliation fields are exactly what the pre-feature pipeline derived (identity pass-through).
3. **Given** a stored legacy flat record, **When** it is shown in the analysis detail dialog,
   **Then** it renders the known flat fields exactly as before.

---

### User Story 3 - Invalid typed payloads are rejected at the gate (Priority: P2)

A typed payload that violates the EXTRACT-001 schema (wrong type, missing required field, an
unexpected key for its document type) is rejected at `record-classification` with a clear error and
nothing is written, so a malformed transcription can be corrected and re-recorded.

**Why this priority**: Keeping `record-classification` the single contract-validation point prevents
malformed typed JSON from entering the staging table and silently degrading the roll-up; but it is a
guardrail on top of the P1 happy path.

**Independent Test**: Record a typed payload missing a required field for its type and confirm the
CLI exits non-zero, prints a located error, and writes no staging row.

**Acceptance Scenarios**:

1. **Given** a typed payload whose `doc_type` is recognized but whose body is missing a required
   field for that type, **When** it is recorded, **Then** the command rejects it (non-zero exit,
   located error) and writes nothing.
2. **Given** a typed payload with an unexpected key for its document type, **When** it is recorded,
   **Then** it is rejected.
3. **Given** a still-valid `{"error": "<reason>"}` page result, **When** it is recorded, **Then** it
   is accepted unchanged (the existing error-result alternative is preserved).

---

### User Story 4 - The reviewer sees the full typed transcription (Priority: P3)

When a typed record is stored, the analysis detail dialog shows the rich transcription (all the
labeled fields the page actually contains), not just the five flat fields, so a human (or the triage
agent) can judge a finding against complete evidence. A legacy flat record still renders its flat
fields. Neither row type produces an error in the UI.

**Why this priority**: This is the "show what the AI saw" payoff (design §10.4 UI), but the pipeline
correctness (P1/P2) and the gate (P2) deliver value first; the richer render layers on top.

**Independent Test**: Open the detail dialog for an attachment with a typed record and confirm the
typed fields render legibly; open one with a legacy flat record and confirm the prior render is
unchanged.

**Acceptance Scenarios**:

1. **Given** a stored typed record, **When** the detail dialog opens, **Then** the derived
   reconciliation fields are shown AND the rich typed content is viewable (no crash, no empty panel).
2. **Given** a stored legacy flat record, **When** the detail dialog opens, **Then** the render is
   unchanged from the pre-feature behavior.

---

### Edge Cases

- **Typed payload with an unknown `doc_type`** (not in the registry): resolves to the generic
  `outro` fallback schema (never blocks), is validated against it, and the `outro` mapper derives a
  best-effort total.
- **Partial / malformed typed JSON that still validates** (e.g. an optional block missing): the
  mapper degrades to `None` reconciliation fields rather than raising; the attachment still rolls up.
- **A typed payload that echoes a wrong `schema_version`**: the stored row is tagged with the
  registry-canonical schema version, so a reader can trust the tag.
- **Shared-NF fan-out**: a sibling reusing a representative's typed record must carry the same stored
  response shape as the representative (the fan-out copies the record), so siblings render and
  reconcile identically.
- **A `{"error": ...}` page result**: still the one permitted non-fields alternative; stored as an
  error (no response), unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `record-classification` MUST accept a typed page payload (a payload carrying a
  `doc_type` discriminator) and validate it against the EXTRACT-001 schema for that type before
  writing; an invalid typed payload MUST be rejected (non-zero exit, located error message) with
  nothing written.
- **FR-002**: `record-classification` MUST continue to accept a legacy flat payload (no `doc_type`),
  validated against the existing flat-field contract, and the single `{"error": "<reason>"}`
  alternative — both with unchanged behavior.
- **FR-003**: A stored typed record (in the `page_classifications` staging table and, after roll-up,
  in `attachment_analysis_records.response`) MUST preserve the rich typed JSON verbatim and carry the
  registry-canonical `schema_version` so a reader can distinguish a typed row from a legacy flat row.
- **FR-004**: The `attachment_analyses` reconciliation roll-up (total / net / paid / issuer CNPJ /
  issuer name / date / number / type / description / artifact role) MUST be derived from a typed
  record via the EXTRACT-003 deterministic per-type mapper, and from a legacy flat record via the
  mapper's identity pass-through — so both row types reconcile correctly.
- **FR-005**: The feature MUST NOT require a database migration; the rich JSON MUST be stored in the
  existing `attachment_analysis_records.response` / `page_classifications.response` TEXT columns.
- **FR-006**: Existing analysis consumers (shared-NF reconciliation, the documents entity build, the
  duplicate-billing / document-overpayment checks, the mismatches summary, the alerts) MUST continue
  to read the correct reconciliation values for BOTH typed and legacy flat stored records.
- **FR-007**: The analysis detail dialog MUST render BOTH a typed stored record (showing the rich
  transcription, with the reconciliation fields legible) and a legacy flat stored record (unchanged),
  without error for either.
- **FR-008**: The schema-version / typed-vs-flat detection MUST live in a single shared place so the
  store / derive / render paths agree on what counts as a typed vs. a flat row (no two code paths
  drift on the discriminator).
- **FR-009**: The shared-NF fan-out MUST copy a representative's stored response shape to its
  siblings unchanged, so siblings render and reconcile identically to the representative.

### Key Entities *(include if feature involves data)*

- **Typed transcription record**: the per-page EXTRACT-001-conformant JSON for one document type
  (e.g. NFS-e: `prestador`, `valores`, `discriminacao_servico`; DANFE: `emitente`, `totais`,
  `itens`), carrying its own `doc_type` and `schema_version`. Stored verbatim in
  `page_classifications.response`, then in `attachment_analysis_records.response`.
- **Legacy flat record**: the pre-typed ~10-field reconciliation object (no `doc_type`). Still
  accepted, stored, read, and rendered.
- **Reconciliation fields**: the flat dict (`valor_total`, `valor_liquido`, `valor_pago`,
  `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico`,
  `tipo_documento`, `papel_artefato`) the analysis roll-up consumes. Derived deterministically from
  either stored shape.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new typed classification is stored with its full typed content and a schema-version
  tag, and the rolled-up reconciliation total equals the value the per-type mapper derives (e.g. an
  NFS-e reconciles on its net, never its gross — the documented 800-vs-320 class of bug cannot occur).
- **SC-002**: 100% of legacy flat records produce byte-identical reconciliation fields and UI render
  before and after the change (zero regressions on the existing corpus).
- **SC-003**: 100% of schema-invalid typed payloads are rejected at `record-classification` with a
  located error and no staging write.
- **SC-004**: The analysis detail dialog renders both a typed and a legacy flat record without error.

## Assumptions

- **Gradual rollout (design T2).** Existing classified periods are NOT re-classified into typed
  schemas as part of this feature; they remain legacy flat rows and keep working via the identity
  pass-through. Re-classification is on-demand (a future campaign or the triage agent touching a
  document), out of scope here.
- **The schema discriminator is `doc_type`.** A stored response carrying a `doc_type` key is typed;
  one without is legacy flat. `schema_version` is also stored, but `doc_type` is the path
  discriminator (consistent with the EXTRACT-003 mapper already shipped).
- **The vision-skill output shape is the EXTRACT-002 transcriber's `fields` object** — the
  EXTRACT-001-conformant per-type object that itself carries `doc_type` / `schema_version` /
  `raw_text` plus the type blocks. That is exactly what `validate_transcription` validates and what
  the EXTRACT-003 mapper consumes; the staging row stores this object as `response`.
- **The EXTRACT-001 validator/registry live under `tools/doc_transcribe` and the analysis package
  must not import from `tools/`** (design §11.6). The contract-gate validation in
  `record-classification` therefore reaches the EXTRACT-001 schema via a boundary that does not make
  `scripts/analysis` depend on `tools/` at import time. The exact seam is a planning decision; the
  spec requires only that typed payloads are validated against the EXTRACT-001 schema at the gate.
- **No new third-party dependency.** Validation stays stdlib-only (design T1).

## Dependencies

- #83 (EXTRACT-001 schema registry) — merged.
- #86 (EXTRACT-002 transcriber) — merged.
- #87 (EXTRACT-003 per-type mappers) — merged.
