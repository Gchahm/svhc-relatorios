# Feature Specification: All-CLI typed document transcription — `classify` command, retire classify skills, typed-only

**Feature Branch**: `066-classify-cli-typed-only`
**Created**: 2026-06-14
**Status**: Draft
**Input**: GitHub issue #113 (EXTRACT-007). "Make document transcription a single, CLI-driven, typed path."

## Overview

Document transcription (page image → per-page extraction) currently has **two** producers with
**two** contracts:

1. The live path — the `classify-doc-page` / `classify-period` **skills** (Claude reads the image
   inline, in the operator's context) — emits the **legacy flat** ~10-field reconciliation object.
2. A **dormant** headless transcriber — `tools/doc_transcribe.transcribe()` (`claude -p`/API behind
   a pluggable backend) — emits the **typed** EXTRACT-001 JSON. Only its validator half is used live
   (via `typed_gate`).

This feature collapses both into **one** CLI-driven, **typed-only** path: a new `classify`
subcommand drives `doc_transcribe` headlessly per page, the transcription skills + the `analyze-docs`
agent are deleted, and the `record-classification` gate is tightened to **reject** flat payloads
(with the dead flat code deleted). The D1 database has been wiped to the new flow, so there is **no
backlog migration** — the system is typed-only from day one.

## Clarifications

### Session 2026-06-14

Run unattended (no human available); ambiguities were resolved by informed default and recorded in
**Assumptions** rather than asked interactively. The decisions that would otherwise be clarification
questions:

- Q: How is the `doc_transcribe` subprocess launched so it resolves `tools/`? → A: with `tools/` as
  its `cwd`/`PYTHONPATH` (mirrors the `typed_gate` seam) — see A1.
- Q: Forced doc-type or auto-detect per page? → A: `--type auto` (model detection), matching prior
  skill behavior — see A2.
- Q: Default backend / fallback behavior? → A: `cli` default; `--backend`/`--model` pass-through; no
  silent fallback — see A3, FR-006.
- Q: How is a per-page transcription failure detected? → A: a non-empty `parse_errors` list on a
  zero-exit result — see A4, FR-007.
- Q: Do `apply-correction`/`reclassify` inject the typed schema validator after tightening? → A: yes,
  to satisfy FR-010 end-to-end — see A5.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Headless typed classification of a period (Priority: P1)

An operator (or an orchestrator running unattended) classifies a scraped period's pending
attachments with a single command, with no human reading images in the loop. Each pending page is
transcribed into typed JSON and recorded to the staging table, ready for `apply-extractions`.

**Why this priority**: This is the core capability the feature delivers — the vision step becomes a
plain standalone CLI step like `scrape` / `apply-extractions` / `analyze`, so the whole pipeline can
run unattended without spawning a skill that pulls page images into context.

**Independent Test**: With a seeded period that has pending, non-`recorded` pages, run
`python -m analysis classify --periodo <p>` (with a fake/test transcriber backend) and assert one
typed `page_classifications` row is recorded per page; then `apply-extractions` → `analyze` produces
`attachment_analyses` + alerts.

**Acceptance Scenarios**:

1. **Given** a period with pending pages and no recorded classifications, **When** `classify
   --periodo <p>` runs, **Then** a typed `page_classifications` row (carrying `doc_type` /
   `schema_version`) is recorded for every pending page and the command reports the count.
2. **Given** a page whose extraction is already `recorded`, **When** `classify` runs, **Then** that
   page is skipped (not re-transcribed).
3. **Given** `--min-amount N` / `--limit N`, **When** `classify` runs, **Then** the pending set is
   scoped exactly as `docs-plan` scopes it.
4. **Given** an attachment marked pending via `mark-pending`, **When** `classify` runs, **Then** its
   pages are re-transcribed (a fresh read).

### User Story 2 - A bad page does not abort the period; a config error does (Priority: P1)

A single unreadable page (the model returns no usable structured result) must not stop the whole
period — its row is recorded as an error and the run continues. But a missing prerequisite (e.g. the
`claude` binary is not on PATH for the `cli` backend) is the operator's to fix, so the run stops with
a clear message rather than silently producing nothing.

**Why this priority**: Robustness + operator clarity. An ambiguous half-finished run (some silent
failure swallowed) is worse than a clean stop.

**Independent Test**: Inject a transcriber that (a) returns `parse_errors` / no usable fields for one
page → assert an `{"error": …}` row is recorded for that page and the run continues over the rest;
(b) raises the config error → assert the run stops, propagates the message, and records nothing
further.

**Acceptance Scenarios**:

1. **Given** the transcriber returns no usable `fields` for a page (exit 0 with `parse_errors`),
   **When** `classify` processes it, **Then** an `{"error": "<reason>"}` row is recorded for that
   page and remaining pages are still processed.
2. **Given** a config/environment error (the transcriber exits non-zero, e.g. `claude` not on PATH),
   **When** `classify` hits it, **Then** the run stops and surfaces the transcriber's message — with
   no silent fallback to a different backend.

### User Story 3 - One typed contract end to end (Priority: P1)

A reviewer/correction agent feeding a corrected page through `record-classification` (directly, or
via `apply-correction` / `reclassify`) sees exactly one accepted contract: the typed EXTRACT-001
payload (or `{"error": …}`). A legacy flat payload is rejected. There is no second shape to reason
about anywhere in the pipeline or UI.

**Why this priority**: Eliminating the dual contract removes a whole class of "which shape is this"
bugs and dead code, and is the explicit acceptance bar of the issue.

**Independent Test**: Submit a flat payload to the gate → assert rejection with a clear message;
submit a valid typed payload → assert acceptance; confirm `apply-correction` / `reclassify` still
pass the gate end to end with typed payloads.

**Acceptance Scenarios**:

1. **Given** a legacy flat fields object (no `doc_type`), **When** it reaches the
   `record-classification` gate, **Then** it is rejected (non-zero exit, clear message, nothing
   written).
2. **Given** a valid typed payload, **When** it reaches the gate, **Then** it is accepted and stored
   verbatim.
3. **Given** `apply-correction` / `reclassify` with a typed corrected page, **When** invoked, **Then**
   the page passes the gate, is recorded, and propagates.

### User Story 4 - The classify skills and analyze-docs agent are gone; dependents rewired (Priority: P2)

The repository no longer carries the `classify-doc-page` / `classify-period` skills or the
`analyze-docs` agent. `improve-classification` runs the CLI steps directly. `fix-mismatch` /
`review-mismatch` references are updated. Docs reflect the all-CLI flow.

**Why this priority**: Removes the redundant in-context vision path and keeps the docs/agent surface
honest. Functional but secondary to the working `classify` command itself.

**Independent Test**: Grep the repo for the deleted skill/agent names → assert no live path
references them; run `improve-classification`'s steps as plain CLI; confirm docs updated.

**Acceptance Scenarios**:

1. **Given** the change is complete, **When** searching the repo, **Then** no live path references
   `classify-doc-page`, `classify-period`, or the `analyze-docs` agent.
2. **Given** `improve-classification`, **When** it runs its loop, **Then** it invokes
   `classify → apply-extractions → analyze → mismatches` as plain bash (no `analyze-docs` delegation).

### Edge Cases

- **Empty period / nothing pending** — `classify` reports nothing to do and exits 0 (no error).
- **All pages already `recorded`** — `classify` records nothing new and exits 0.
- **A group's representative has multiple pages** — each page is transcribed in turn (serially).
- **An attachment with no `file_path` (no pages)** — contributes no pages to transcribe.
- **A typed payload that fails EXTRACT-001 schema validation** at the gate — rejected (the gate
  always schema-validates a typed payload via the injected validator).
- **The transcriber returns a typed object but with `parse_errors`** — treated as a per-page failure
  (error row), not a config error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a standalone `classify` subcommand
  (`python -m analysis classify --periodo <YYYY-MM> [--remote] [--min-amount N] [--limit N]
  [--backend cli|api] [--model …]`) that classifies a period's pending, non-`recorded` pages.
- **FR-002**: `classify` MUST build its work plan via the existing `build_plan` (same DB-controlled
  pending selection + `--min-amount`/`--limit` filters as `docs-plan`, and the same image
  materialization), and MUST skip any page already flagged `recorded`.
- **FR-003**: For each page to transcribe, `classify` MUST run `doc_transcribe` **as a subprocess**
  (`python -m doc_transcribe --image <read_path> --type auto`, threading `--backend`/`--model` when
  given), take the typed `fields` object from its result, and record it via `record_classification`.
- **FR-004**: `classify` MUST process pages **serially, one at a time** (simple, cost-predictable).
  Vision only — it MUST NOT run apply/analyze.
- **FR-005**: `classify` MUST NOT import the `tools/` package — `doc_transcribe` is reached **only**
  as a subprocess. The analysis library MUST remain import-clean of `tools/` except the existing
  `typed_gate` validator seam.
- **FR-006**: On a **config/environment error** — the `doc_transcribe` subprocess exits non-zero
  (e.g. `claude` not on PATH) — `classify` MUST stop the run and propagate the subprocess's message.
  It MUST NOT fall back to a different backend silently.
- **FR-007**: On a **per-page transcription failure** — the subprocess exits 0 but its result carries
  `parse_errors` / no usable `fields` — `classify` MUST record an `{"error": "<reason>"}` row for
  that page and continue with the remaining pages.
- **FR-008**: `record-classification`'s gate (`validate_page_fields`) MUST accept ONLY a typed
  EXTRACT-001 payload (a dict carrying a valid `doc_type`, schema-validated via the injected
  validator) or the `{"error": …}` alternative, and MUST **reject** any other payload (including the
  legacy flat fields object).
- **FR-009**: The dead legacy-flat code MUST be removed: the flat validation branch + flat constants
  (`REQUIRED_KEYS` / `PAPEL_VALUES` / `STRING_OR_NULL` / `AMOUNT_KEYS`) in `page_classifications.py`,
  the legacy-flat read-tolerance in `type_mappers.to_reconciliation_fields`, and the typed-vs-flat
  dual-render (`is_typed` / `isTyped`) in the UI. End state: one contract, no discriminator.
- **FR-010**: `apply-correction` and `reclassify` MUST continue to pass the tightened gate end to
  end — they MUST emit typed payloads and schema-validate them through the same gate.
- **FR-011**: The `classify-doc-page` and `classify-period` skills (including
  `classify-doc-page/scripts/validate_image.py`) and the `analyze-docs` agent MUST be deleted, and no
  live path may reference them.
- **FR-012**: `improve-classification` MUST run the CLI steps directly
  (`classify → apply-extractions → analyze → mismatches`) instead of delegating to `analyze-docs`;
  `fix-mismatch` / `review-mismatch` descriptive references to the removed skills/agent MUST be
  updated.
- **FR-013**: `tools/doc_transcribe` MUST be used **as-is** — this feature makes **no changes** to
  it; it stays repo-agnostic (no SVHC-specific prompt text). The sole `tools/` touch point remains
  the `typed_gate` validator import (plus the new `classify` subprocess invocation, which is not an
  import).
- **FR-014**: Documentation MUST be updated to the all-CLI typed flow: `docs/pipeline.md`,
  `scripts/pipeline-flow.md`, `scripts/README.md`, the relevant runbook(s), and `CLAUDE.md`.
- **FR-015**: Unit tests MUST cover the `classify` loop (injected fake transcriber: typed happy path,
  per-page error row, config-error-stops-the-run, skip-`recorded`, `--min-amount`/`--limit` scoping)
  and the tightened gate (flat rejected, typed accepted, error accepted).

### Key Entities *(include if feature involves data)*

- **Typed transcription payload** — the EXTRACT-001-conformant per-type `fields` object (carries
  `doc_type` / `schema_version`); the **only** accepted per-page fields shape after this feature.
- **`page_classifications` staging row** — one per `(attachment_id, page_label)`; `response` holds
  the typed payload verbatim (or NULL for an error row); `error` holds the reason for an error row.
- **`classify` subcommand** — the headless vision step: pending plan → per-page `doc_transcribe`
  subprocess → `record_classification`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `classify --periodo <p>` on a period with pending pages records a typed
  `page_classifications` row for every pending, non-`recorded` page with **zero** human-in-the-loop
  steps.
- **SC-002**: A single bad page yields exactly one `{"error": …}` row and **100%** of the remaining
  pending pages are still processed in the same run.
- **SC-003**: A missing `claude` binary (cli backend) **fails the run** with the transcriber's
  message and records **no** silent fallback — confirmable by observing a non-zero exit and the
  propagated message.
- **SC-004**: A flat payload submitted to `record-classification` is rejected **100%** of the time;
  a valid typed payload is accepted; `apply-correction` / `reclassify` round-trip typed payloads
  successfully.
- **SC-005**: A repo-wide search finds **zero** live-path references to `classify-doc-page`,
  `classify-period`, or the `analyze-docs` agent after the change.
- **SC-006**: The full unit suite (existing + new) passes; the analysis library still imports with
  `tools/` off `sys.path` beyond the `typed_gate` seam.

## Assumptions

- **A1**: `doc_transcribe`'s CLI is invoked as `python -m doc_transcribe --image <path> --type auto`
  with `tools/` resolved onto its module path the same way `typed_gate` resolves `<repo>/tools`. The
  analysis package runs with `cwd = scripts/`, so the subprocess must be launched with `tools/` as
  its working directory (or `PYTHONPATH`).
- **A2**: `--type auto` is the default classification mode (the model detects the document type); a
  per-page forced type is out of scope for `classify` (the transcriber supports `--type` but the
  pipeline lets the model auto-detect, consistent with the prior skill behavior).
- **A3**: The default backend is `cli` (matching `doc_transcribe`'s default); `--backend api` and
  `--model` are pass-through options. No environment auto-detection or fallback.
- **A4**: A "per-page transcription failure" is detected by the result carrying a non-empty
  `parse_errors` list (the transcriber's documented signal) — that page's error row reason is derived
  from those messages.
- **A5**: `apply-correction` / `reclassify` already record through `validate_page_fields`; to satisfy
  FR-010 the typed validator (`typed_gate.validate_typed`) is injected at those call sites so typed
  payloads are schema-validated (matching the `record-classification` CLI), rather than only
  structurally checked. The agents that build their payloads (`fix-document-findings`) already emit
  the page's existing typed shape, so no agent-side payload construction change is needed beyond doc
  wording.
- **A6**: There is no standalone "full-run" convenience command, and the human-judgment review
  surfaces (`fix-document-findings` agent, `triage-false-positives` skill) are unchanged — both
  explicitly out of scope per the issue.
- **A7**: No D1 schema change and no migration (the `response` TEXT column already stores typed JSON;
  the DB was wiped, so no flat rows exist to migrate).

## Out of Scope

- A standalone "full-run" convenience command chaining all steps.
- Any change to `tools/doc_transcribe` itself.
- The human-judgment review surfaces (`fix-document-findings` agent, `triage-false-positives` skill).
- Parallel/concurrent page transcription (serial is intentional).
- Any UI feature beyond removing the now-dead flat dual-render path.
