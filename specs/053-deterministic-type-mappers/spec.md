# Feature Specification: Deterministic per-type mappers (typed JSON → reconciliation fields)

**Feature Branch**: `053-deterministic-type-mappers`  
**Created**: 2026-06-13  
**Status**: Draft  
**Input**: User description: "Deterministic per-type mappers (typed transcription JSON → reconciliation fields) wired into the analysis roll-up, replacing first-record-of-role guesswork (EXTRACT-003, issue #87)"

## Overview

The vision step was previously asked to both **read** a fiscal document page and **interpret**
it — to decide "which number is the total" and "who is the issuer" — emitting a flat ~10-field
object (`valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `numero_documento`, …).
That interpretation was guesswork that became data errors: the documented `757dedb0…` case where
the model reported an NFS-e total of R$ 800 when the page legibly showed R$ 320, and a whole class
of `amount_match` false positives where `_rollup_attachment_fields` picked the **first record of a
role** rather than the value the document actually carries.

With the typed transcription contract now in place (EXTRACT-001 schema registry, EXTRACT-002 vision
transcriber), the page is transcribed verbatim into a **typed JSON keyed by document type** (e.g. an
NFS-e records `valores.valor_servico` and `valores.valor_liquido` separately; a DANFE records
`totais.valor_total_nota`). "Which number is the total / who is the issuer" then becomes a
**deterministic, pure, testable function over that typed JSON** — a per-type mapper — replacing the
model's guesswork with versioned rules.

This feature delivers those per-type mappers and wires them into the analysis interpretation seam so
the documented false positives stop firing.

## Clarifications

### Session 2026-06-13

- No critical ambiguities detected worth formal clarification. The taxonomy scan found every
  high-impact category resolved by the spec or its documented Assumptions: scope (mappers' home,
  stdlib-only, no schema change), data model (the per-type field mappings + reconciliation field
  set are enumerated in FR-001/FR-002), edge cases (unknown type, missing total, non-positive zero,
  currency-string amounts, typed-vs-flat coexistence), and completion signals (SC-001..SC-005 are
  testable). Cardinality (Problem B) is explicitly out of scope. Proceeding to planning.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The 757dedb0 NFS-e maps to the page total, not the model's guess (Priority: P1)

An auditor reviews a period containing the `757dedb0…` NFS-e. The page legibly shows
`valor_servico = 320` and `valor_liquido = 320`. Under the typed-transcription + mapper model the
reconciliation total derived for that document is **320**, never the model's old phantom **800**, so
no false `amount_match` discrepancy is raised for it.

**Why this priority**: This is the canonical bug the feature exists to fix and the acceptance case
named in the issue. If the mapper does not turn this case from a false mismatch into a correct
reconciliation, the feature has not delivered its core value.

**Independent Test**: Feed the mapper the typed NFS-e JSON for the 757dedb0 case and assert the
derived reconciliation total is 320 (not 800), with `cnpj_emitente`/`numero_documento` taken from
the typed prestador/numero fields. Fully testable as a pure unit test with no DB/vision.

**Acceptance Scenarios**:

1. **Given** a typed `nfse` JSON with `valores.valor_liquido = 320`, **When** the nfse mapper runs,
   **Then** the derived `valor_total` (the reconciliation total) is 320.
2. **Given** the same typed JSON, **When** the mapper runs, **Then** `cnpj_emitente` is the
   prestador CNPJ and `numero_documento` is the NFS-e number — both by typed field access, not the
   model's flat guess.

---

### User Story 2 - The documented record-selection false positives no longer fire (Priority: P1)

The cases in `rollup-amount-false-positives.md` (Problem A — "first-record-of-role wins") stop
producing false `amount_match` mismatches once the reconciliation total for each document is derived
deterministically from the typed JSON rather than by picking the first record of a role.

**Why this priority**: Eliminating this whole class of false positives is the issue's acceptance
criterion. False positives erode trust in the audit tool; each one a reviewer must dismiss is wasted
effort.

**Independent Test**: For each documented case, build the per-page typed JSON and assert that the
roll-up's derived reconciliation total equals the document's true value (so the existing tolerance
check reconciles), and that a genuine over/under-claim still surfaces (no false negative introduced).

**Acceptance Scenarios**:

1. **Given** a document whose typed JSON carries the correct total in its type's total field,
   **When** the roll-up derives the reconciliation total via the mapper, **Then** the total matches
   the document's value and `amount_match` reconciles within tolerance.
2. **Given** a document whose typed values genuinely disagree with the ledger entry beyond
   tolerance, **When** the roll-up derives the reconciliation total, **Then** the mismatch still
   surfaces (no false negative).

---

### User Story 3 - Legacy flat records keep working unchanged (Priority: P2)

Periods classified before typed transcription rolled out still carry the legacy flat per-page
records (`valor_total`, `valor_liquido`, … at the top level). The interpretation seam continues to
read those records exactly as before, so a re-run over an un-reclassified period produces the same
roll-up it did previously — no regression, no re-classification forced.

**Why this priority**: Rollout is gradual (design §10.4 / T2: typed and flat records coexist). The
feature must not break or silently change interpretation for the data already in the database.

**Independent Test**: Feed the interpretation seam a legacy flat record and assert the derived
reconciliation fields are identical to today's behavior (regression fixtures).

**Acceptance Scenarios**:

1. **Given** a legacy flat per-page record (no `doc_type` discriminator), **When** the roll-up runs,
   **Then** the derived reconciliation fields equal the values produced by the pre-feature roll-up.
2. **Given** a mix of typed and flat records in one shared-NF group, **When** the group reconciles,
   **Then** each record contributes its correctly-derived values and the group still reconciles.

---

### Edge Cases

- **Unknown / unrecognized type**: a typed JSON whose `doc_type` is not one of the known types (or
  the generic `outro` fallback) must derive whatever reconciliation values it legibly can (e.g. a
  single identified amount) and otherwise leave fields empty — it must NEVER raise and must never
  block the pipeline.
- **Missing total field**: a typed JSON of a known type that is missing its total field (e.g. a
  DANFE with no `totais.valor_total_nota`) derives an empty total rather than guessing or raising;
  the existing graceful-degradation path (no reconcilable total ⇒ group left untouched) applies.
- **Non-positive / spurious zero**: a `valor_pago: 0.0` (or any non-positive amount) must not be
  selected as a real value when a genuine value is present elsewhere — the existing
  "treat-non-positive-as-missing" rule is preserved.
- **Amounts as strings**: a typed amount that arrives as a currency string (e.g. `"R$ 320,00"`) is
  parsed to the same numeric value as `320.0` (the existing BRL parsing is reused).
- **Both typed and flat present in the same input dict**: the discriminator (`doc_type`) decides;
  when present, the typed access path is used.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a pure mapper per supported document type that takes that
  type's typed transcription JSON and returns the reconciliation fields the analysis pipeline
  consumes: `valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `numero_documento`,
  `nome_emitente`, `data_emissao`, `descricao_servico`, and `tipo_documento`/`papel_artefato`.
- **FR-002**: Each mapper MUST derive each reconciliation field by typed field access on its type's
  schema, per the documented mapping: `danfe → valor_total = totais.valor_total_nota`;
  `nfse → valor_total = valores.valor_liquido` (and `valor_liquido = valores.valor_liquido`);
  `comprovante_pagamento → valor_pago = valor`; `boleto → valor_total = valor_documento`;
  `recibo → valor_total = valor`; `outro → valor_total` from a single identified amount when present.
- **FR-003**: A single dispatch function MUST select the correct mapper from the typed JSON's own
  `doc_type` discriminator (resolving aliases/spelling to the canonical type), falling back to the
  generic mapper for an unknown/missing type, and MUST NEVER raise on any input.
- **FR-004**: The dispatch MUST detect a legacy flat record (no `doc_type` discriminator) and pass
  its already-flat fields through unchanged, so periods classified before typed transcription
  produce the same reconciliation fields as before this feature.
- **FR-005**: The mappers MUST be wired into the analysis interpretation seam — `_rollup_attachment_fields`
  and `nf_total_for_reconciliation` (`scripts/analysis/attachments.py`) — so the attachment roll-up
  and the shared-NF reconciliation total are derived from the mapped fields rather than from the
  raw model output. The seam MUST keep the per-page record contract intact for downstream readers
  (the roll-up still reads the same flat field names per page).
- **FR-006**: The shared reconciliation-tolerance contract (`reconciliation_contract.json` and the
  `reconcile_group` tolerance) MUST remain intact — this feature changes only how the input values
  are derived, not the tolerance math or the contract.
- **FR-007**: The mapper MUST preserve the existing "treat non-positive amounts as missing" rule and
  reuse the existing BRL value parsing, so a spurious `0.0` never wins and currency-string and
  numeric amounts produce identical results.
- **FR-008**: The change MUST NOT introduce false negatives: a document whose mapped values
  genuinely disagree with the ledger beyond tolerance MUST still surface as a mismatch.
- **FR-009**: The mappers MUST live app-side in the analysis package (SVHC reconciliation policy,
  design T6) and be stdlib-only (no new dependency, no import of the `tools/doc_transcribe` package
  from the analysis package).
- **FR-010**: Unit tests MUST cover every mapper, the dispatch (typed, alias, unknown, flat
  pass-through), the 757dedb0 case (yields 320, not 800), and the documented record-selection cases
  from `rollup-amount-false-positives.md`.

### Key Entities *(include if feature involves data)*

- **Typed transcription JSON**: the per-document-type record produced by the typed transcription
  contract — keyed by a `doc_type` discriminator (`danfe`, `nfse`, `boleto`, `recibo`,
  `comprovante_pagamento`, `outro`) with type-specific nested fields (e.g. `totais.valor_total_nota`,
  `valores.valor_liquido`, `prestador.cnpj`).
- **Reconciliation fields**: the flat set of fields the analysis roll-up and reconciliation consume
  (`valor_total`, `valor_liquido`, `valor_pago`, `cnpj_emitente`, `numero_documento`, `nome_emitente`,
  `data_emissao`, `descricao_servico`, `tipo_documento`, `papel_artefato`).
- **Mapper**: a pure function per type that derives the reconciliation fields from a typed JSON; the
  dispatch selects the mapper from the discriminator and falls back gracefully.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The 757dedb0 NFS-e case yields a reconciliation total of 320 (not 800), verified by a
  unit test.
- **SC-002**: Every documented `amount_match` false positive in `rollup-amount-false-positives.md`
  (Problem A) no longer fires, verified by unit tests that assert the derived total reconciles.
- **SC-003**: A re-run of the analysis over a period of legacy flat records produces identical
  reconciliation fields to the pre-feature behavior (no regression), verified by pass-through tests.
- **SC-004**: No genuine over/under-claim is hidden — a constructed real-discrepancy case still
  surfaces as a mismatch, verified by a unit test (zero false negatives introduced).
- **SC-005**: The full Python unit suite (`pnpm test:py`) and the tools suite pass; no new
  dependency is added.

## Assumptions

- **Mappers' home is app-side, stdlib-only.** Per design T6 ("Lean: app-side until a second consumer
  needs them") and the analysis package's stdlib-only invariant, the mappers live in
  `scripts/analysis/` and do not import the `tools/doc_transcribe` package. The small canonical-type
  resolution (alias → canonical key) is mirrored locally rather than imported, consistent with how
  the scraper mirrors (not imports) the analysis tolerance.
- **The typed JSON's `doc_type` discriminator is the canonical key.** Typed JSON is produced by the
  EXTRACT-001/002 registry, which writes a canonical `doc_type`; the dispatch resolves aliases
  defensively but trusts the discriminator when canonical.
- **The per-page record contract downstream is unchanged.** The mappers produce the same flat field
  names (`valor_total`, `cnpj_emitente`, …) the roll-up already reads, so wiring is localized to the
  interpretation seam; no DB schema change, no migration, no change to the record-classification
  staging contract (that adapter is EXTRACT-004, out of scope here).
- **Coexistence is by discriminator, not schema_version column.** A record with a `doc_type`
  discriminator is treated as typed; one without is treated as legacy flat — no DB column is needed
  to distinguish them.
- **Invoice↔entry cardinality (Problem B in `rollup-amount-false-positives.md`) is out of scope** —
  it is SCOPE Phase 2 cross-reference reconciliation; this feature addresses only the deterministic
  field derivation (Problem A / §10.2), and the existing `_sum_distinct_invoices` group logic is
  retained as-is.

## Out of Scope

- The vision/transcription step itself and the record-classification staging contract / its typed
  adapter (EXTRACT-004) — this feature consumes the typed JSON, it does not change how it is produced
  or stored.
- The type-aware UI renderer (design §10.4 UI) and the `re-derive` propagation command (design §10.5).
- Invoice↔entry cardinality reconciliation (Problem B / SCOPE Phase 2).
- Any DB schema change or migration.
