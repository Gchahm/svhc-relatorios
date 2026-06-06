# Feature Specification: Claude Vision Agent for Document Analysis (retire the VLM flow)

**Feature Branch**: `006-analyze-docs-agent`
**Created**: 2026-06-06
**Status**: Draft
**Input**: User description: "I want to create a claude agent that does the work of analyze-docs so I can retire the vlm flow"

## Overview

The document-analysis stage (`analyze-docs`) extracts structured fields from each page image of
a fiscal document (gross/net/paid amounts, CNPJ, issuer, date, document number, service, and an
artifact role) and feeds them into downstream grouping, reconciliation, and fraud checks. Today
that per-page extraction runs on a local Apple-Silicon vision model (`mlx_vlm` / Qwen2.5-VL),
which cannot run on most maintainer machines or in CI, so the stage is effectively unrunnable
outside one specific laptop.

This feature replaces **only** the image→structured-fields extraction step with a Claude vision
**subagent** (in the same `.claude/agents/` style as the existing PM agent). Everything that
surrounds extraction — NF grouping by byte-identical page content, the heterogeneity-aware
document roll-up, group reconciliation, sibling fan-out, entry-level validation, JSON write-back,
the duplicate-billing check, and the D1 import contract — is **preserved unchanged** and is fed
from an intermediate extractions file instead of from the local model. The local-model code path
and its dependency are then removed, retiring the VLM flow.

## Clarifications

### Session 2026-06-06

- Q: How much of `analyze-docs` should the Claude agent own vs. the existing deterministic Python? → A: Extraction only — the agent replaces just the per-page image→structured-fields step; NF grouping, roll-up, reconciliation, fan-out, validation, and JSON write-back stay in deterministic Python.
- Q: How should the new agent be invoked (the VLM flow was a `python -m scraper analyze-docs` CLI)? → A: A `.claude/agents/` subagent writes a per-page extractions file; a thin deterministic command then merges those extractions into the period JSON (no runtime model/API in the loop).
- Q: What should happen to the existing `mlx_vlm` code? → A: Remove the model-load + per-page inference path and drop the `mlx_vlm` dependency; keep all deterministic helpers (grouping, roll-up, reconciliation, models, import).

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Run document extraction without a local vision model (Priority: P1)

A maintainer on any machine (no Apple Silicon, no `mlx_vlm`) wants to analyze the documents for a
scraped period. They invoke the document-analysis subagent inside their Claude Code session for a
period; the subagent looks at each relevant document page image and produces the structured fields
for that page into an extractions file. A deterministic step then merges those extractions into the
period JSON exactly as the old flow did.

**Why this priority**: This is the core of the request — making `analyze-docs` runnable anywhere by
removing the hard local-model dependency. Without it, the stage stays locked to one machine.

**Independent Test**: On a machine with no `mlx_vlm` installed, run the subagent against a period
that has downloaded page images and confirm a populated extractions file is produced and that the
deterministic merge writes `document_analyses` / `document_analysis_records` into the period JSON.

**Acceptance Scenarios**:

1. **Given** a period JSON with documents whose `file_path` points to real page images, **When** the
   subagent is run for that period, **Then** an extractions file is produced containing one
   structured record per analyzed page, using the same field set the previous flow produced
   (`papel_artefato`, `tipo_documento`, `valor_total`, `valor_liquido`, `valor_pago`,
   `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico`).
2. **Given** an extractions file, **When** the deterministic merge step runs, **Then** the period
   JSON gains `document_analyses` rows (with nested `analysis_records`) of the same shape as before,
   and `scripts/import-to-d1.mjs` imports them without changes.
3. **Given** a document whose page images are byte-identical to another document's (a shared Nota
   Fiscal), **When** extraction runs, **Then** the shared pages are extracted once and reused for the
   siblings — not re-viewed per sibling.

### User Story 2 - Preserve grouping, reconciliation, and fraud checks (Priority: P1)

The maintainer relies on the existing shared-NF reconciliation and the duplicate-billing alert.
Swapping the extraction source must not change any of that behavior: given the same extracted
values, the grouping, roll-up, reconciliation outcomes, sibling fan-out, entry validation, and
duplicate-billing alerts must be identical to the old flow.

**Why this priority**: These checks are the product's value (correctness + forgery/over-claim
detection). The change is a like-for-like extraction swap and must be behavior-preserving for
everything downstream.

**Independent Test**: Feed a fixed set of per-page extracted values through the deterministic merge
and confirm the resulting `document_analyses`, reconciliation classifications, and any
`duplicate_billing` alerts match what the old code produces for the same values (verifiable with
synthetic extractions, no model needed).

**Acceptance Scenarios**:

1. **Given** a shared-NF group whose sibling entry amounts sum within tolerance of the NF gross
   total, **When** the merge runs, **Then** the group reconciles (`amount_match` true) and no
   over-claim alert is raised — identical to today.
2. **Given** a shared-NF group whose sibling sum exceeds the NF total, **When** the merge runs,
   **Then** a `critical` `duplicate_billing` alert is produced, identical to today.
3. **Given** a heterogeneous document (invoice + boleto + payment proof across pages), **When** the
   roll-up runs, **Then** identity fields and the amount-precedence roll-up resolve exactly as the
   existing heterogeneity-aware logic dictates.

### User Story 3 - Retire the local VLM flow (Priority: P2)

After the agent-based extraction is in place, the maintainer wants the local-model path gone: the
`mlx_vlm` model-loading and per-page model-inference code removed, the dependency dropped, and the
documentation/commands updated so there is one obvious way to run the stage.

**Why this priority**: This is the stated end goal ("retire the vlm flow"), but it depends on P1
being in place and proven first.

**Independent Test**: Search the codebase for `mlx_vlm` and the model-load/inference functions and
confirm they are gone; confirm the project's dependency manifest no longer requires `mlx_vlm`;
confirm `analyze-docs` documentation points at the new two-step flow.

**Acceptance Scenarios**:

1. **Given** the updated codebase, **When** searching for the local vision-model imports/functions,
   **Then** none remain in the analysis pipeline.
2. **Given** the updated codebase, **When** a maintainer reads `CLAUDE.md` / command help, **Then**
   the documented way to analyze documents is the agent + merge flow, with no reference to the local
   model.

### Edge Cases

- **Missing or unreadable page image**: the page is recorded with a per-page error (mirroring the
  old `parse_error` behavior) and does not abort the document; other pages still extract.
- **A page that cannot be confidently parsed** (illegible/blank): recorded as a per-page error
  rather than fabricated values.
- **Document with no extractable page**: recorded as a document-level error, exactly as before.
- **Re-running extraction**: an already-analyzed period is skipped unless re-analysis is requested;
  targeting specific document/entry ids forces re-extraction of just those.
- **Filters**: minimum-amount, max-document limit, and id targeting behave as in the current flow
  (they govern which documents are put in front of the agent).
- **Shared NF where pages cannot be hashed** (missing files): treated as ungroupable singletons —
  never merged with other documents — exactly as today.
- **Values as strings vs numbers**: extracted amounts may arrive as Brazilian-formatted strings or
  numbers; the existing currency parsing must continue to accept both.
- **Non-determinism of vision**: extracted values may vary slightly run-to-run; record identifiers
  remain stable (they are derived from document identity, not from extracted content).

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The system MUST provide a Claude vision subagent that, given a scraped period, views
  each relevant document page image and produces that page's structured fields using the existing
  extraction field set and semantics (roles invoice / nfse / boleto / payment_proof / other; gross,
  net, and paid amounts; CNPJ; issuer; emission date; document number; service description).
- **FR-002**: The subagent MUST write its results to an intermediate extractions artifact that the
  deterministic merge step consumes, keyed so each extraction maps unambiguously back to a document
  page.
- **FR-003**: The system MUST provide a deterministic (non-model) step that consumes the extractions
  artifact and produces, in the period JSON, `document_analyses` rows with nested
  `analysis_records` of the **same shape** as the current flow, such that `scripts/import-to-d1.mjs`
  imports them without modification.
- **FR-004**: The deterministic step MUST reuse the existing NF grouping (byte-identical page
  content), heterogeneity-aware roll-up, group reconciliation (5% relative OR R$0.05 absolute
  tolerance; over_claim / under_claim / reconciled), sibling fan-out, and entry-level
  amount/vendor/date validation — behavior MUST be unchanged given identical extracted values.
- **FR-005**: The system MUST extract each unique shared-NF page only once and reuse the result for
  sibling documents (no redundant per-sibling vision passes).
- **FR-006**: The system MUST honor the existing selection controls — restrict to specific periods,
  a minimum entry amount, a maximum document count, and specific document or entry ids (the latter
  forcing re-extraction of those) — and MUST skip already-analyzed documents unless re-analysis is
  requested.
- **FR-007**: The system MUST record per-page extraction failures (missing/unreadable/illegible
  image, unparseable content) as page-level errors without aborting the rest of the document, and
  MUST record a document-level error when no page yields a usable extraction — matching current
  failure semantics.
- **FR-008**: The duplicate-billing check MUST continue to operate on the persisted
  `document_analyses` produced by the new flow, raising a `critical` `duplicate_billing` alert for
  over-claim groups exactly as today, with no D1 schema change.
- **FR-009**: The system MUST remove the local vision-model code path (model loading and per-page
  model inference) and drop the `mlx_vlm` dependency from the analysis pipeline.
- **FR-010**: Project documentation and command help MUST be updated to describe the agent + merge
  flow as the way to analyze documents, with no remaining instructions to use the local model.
- **FR-011**: The subagent MUST NOT fabricate values for content it cannot read; absent or
  unreadable fields MUST be represented as empty/null, consistent with the existing field contract.

### Key Entities _(include if feature involves data)_

- **Document**: a fiscal artifact attached to an accountability entry; has one or more page images
  referenced by a `;`-separated `file_path`. Several documents may share one byte-identical Nota
  Fiscal.
- **Page extraction**: the structured fields read from a single page image (artifact role plus
  gross/net/paid amounts, CNPJ, issuer, date, document number, service description). Mirrors the
  existing per-page `page_extraction` record's `response`.
- **Extractions artifact**: the intermediate file the subagent writes and the deterministic merge
  step reads — a map from a document page to its page-extraction fields (plus any per-page error).
- **Document analysis (roll-up)**: the per-document summary derived from its page extractions
  (document type, rolled-up amount, identity fields, and the entry-validation match flags), unchanged
  in shape from today and normalized on import into `document_analyses` /
  `document_analysis_records`.
- **Shared-NF group**: the set of documents whose page bytes are identical; reconciled as a group
  (sibling-sum vs. NF total) and the unit of duplicate-billing detection.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: The full document-analysis stage runs to completion on a machine with **no** local
  vision model installed (zero dependence on Apple-Silicon-only components).
- **SC-002**: For a given set of per-page extracted values, the resulting `document_analyses` /
  `document_analysis_records`, reconciliation classifications, and duplicate-billing alerts are
  **identical** to the current flow's output for the same values (verified with synthetic
  extractions).
- **SC-003**: The period JSON produced by the new flow imports through `scripts/import-to-d1.mjs`
  with no changes to the importer and no schema migration.
- **SC-004**: On a spot-check of analyzed documents, the agent's extracted key fields (gross amount,
  CNPJ, issuer name, document number, emission date) match the visible document content in at least
  90% of fields checked.
- **SC-005**: Shared-NF documents are extracted once per unique NF (no redundant vision passes for
  byte-identical siblings).
- **SC-006**: No reference to the local vision model (`mlx_vlm` and its model-load/inference
  functions) remains in the analysis pipeline or its dependency manifest after the change.

## Assumptions

- The new subagent follows the existing `.claude/agents/` convention (a Markdown agent definition
  like `pm.md`), invoked from within a Claude Code session; it is not required to be runnable as a
  fully headless `python -m scraper` CLI subcommand on its own.
- The intermediate extractions artifact lives alongside the period JSON under `data/scrape/` and is
  a working artifact (not necessarily committed/imported directly).
- The extraction field set and artifact-role taxonomy remain exactly as the current prompt defines;
  this feature changes the _source_ of the extraction, not its schema.
- Slight run-to-run variation in vision extraction is acceptable; deterministic record identifiers
  (derived from document identity) keep JSON ids stable across runs.
- All deterministic helpers currently in the analysis module (grouping, roll-up, reconciliation,
  fan-out, validation, write-back) are retained and reused; only model loading and per-page model
  inference are removed.
