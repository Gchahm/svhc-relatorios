# Feature Specification: Document→attachment(s) evidence resolver for the triage agent

**Feature Branch**: `051-document-evidence-resolver`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Add a document-evidence resolver CLI for the triage agent" (GitHub issue #85, TRIAGE-002)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One-shot evidence for a document id (Priority: P1)

A false-positive triage agent (or an operator) is handed a **document** id — the same id the
dashboard and alerts surface. To decide whether a finding on that document is a real discrepancy
or a vision misread, the agent must look at the actual page image(s) of the **attachment(s)** the
document was built from and read the existing findings for them. Today no command maps a document
id to its source attachments; the manual flow used ad-hoc SQL against `document_entries`. This
story gives the agent a single read-only command that, given a document id, returns that document's
findings plus the page-image read paths in one shot.

**Why this priority**: This is the agent's single entry point and the foundation issue for the
triage agent (no blockers). Without it every triage run starts with hand-written SQL, which is
brittle and unsafe to embed in an autonomous agent.

**Independent Test**: With a seeded document that links to one or more attachments carrying known
mismatches, run the resolver with that document id and confirm it returns exactly that document's
findings, each with the attachment's page-image read paths — with no SQL written by the caller.

**Acceptance Scenarios**:

1. **Given** a document id that links (via its source attachments) to entries with classification
   mismatches, **When** the resolver runs with `--id <document_id>`, **Then** it prints the existing
   scoped mismatch summary (the same shape `mismatches` produces) for that document's source
   attachments, each finding carrying `page_refs` with materialized image `read_path`s.
2. **Given** a document that spans several source attachments (N:N with entries), **When** the
   resolver runs, **Then** findings for all of the document's distinct source attachments are
   included, and no finding from an unrelated attachment is included.
3. **Given** a document id, **When** the resolver runs, **Then** it makes no writes to any table
   (read-only).

### Edge Cases

- **Unknown document id**: the resolver reports that the document was not found and exits non-zero,
  rather than silently emitting an empty summary that could be mistaken for "no findings."
- **Document with no source attachments recorded** (links exist but `source_attachment_id` is NULL):
  the resolver emits an empty findings list (a valid "nothing to triage" result) and notes the
  resolved attachment set was empty.
- **Document whose source attachments currently carry no mismatches**: the resolver emits an empty
  findings list (the document is clean) — distinct from the unknown-id error above.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analysis CLI MUST expose a read-only command that takes a single document id and
  returns that document's classification findings.
- **FR-002**: The command MUST resolve the document id to its distinct **source attachment ids** via
  the document→entry links (the recorded `source_attachment_id` provenance), without the caller
  writing any SQL.
- **FR-003**: The command MUST emit the **existing** scoped mismatch summary for the resolved
  attachment set (the same per-finding shape the `mismatches` command already produces), including
  each finding's `page_refs` with materialized image `read_path`s the triage agent can open directly.
- **FR-004**: The command MUST be strictly read-only — it MUST NOT write D1 or mutate any data;
  materializing page images into the ephemeral local cache (so `read_path`s resolve) is permitted, as
  the existing `mismatches` command already does this.
- **FR-005**: When the document id does not exist, the command MUST fail clearly (non-zero exit with
  an explanatory message) rather than print an empty result.
- **FR-006**: When the document exists but resolves to no source attachments, the command MUST emit
  an empty findings result (not an error), so the agent can distinguish "no attachments to triage"
  from "unknown document."
- **FR-007**: The command MUST support the same local/remote D1 target selection the other analysis
  commands use, defaulting to local.
- **FR-008**: The resolved findings MUST be limited to the document's source attachments — findings
  belonging to other attachments MUST NOT appear.

### Key Entities *(include if feature involves data)*

- **Document**: a real fiscal document (global, identified by normalized number + issuer CNPJ),
  built from attachment analyses; what the UI/alert shows.
- **Document→entry link**: the N:N association between a document and ledger entries, carrying the
  `source_attachment_id` provenance — the bridge from a document id to the attachment(s) that
  produced it.
- **Attachment**: the downloaded multi-page bundle; corrections (re-classification) happen at this
  level, and its page images are the evidence the triage agent reads.
- **Mismatch finding**: an existing per-attachment classification discrepancy (amount/vendor/date/
  page-error) or `document_overpayment`, carrying `page_refs` (page-image read paths).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given any document id, the triage agent obtains that document's findings + page
  read paths with a single command invocation and zero hand-written SQL.
- **SC-002**: For a document spanning multiple source attachments, 100% of the document's distinct
  source attachments are covered by the returned findings, and 0% of unrelated attachments' findings
  appear.
- **SC-003**: The command performs zero data writes (verifiable by diffing D1 row state before/after
  an invocation).
- **SC-004**: An unknown document id produces a non-zero exit and a clear message in 100% of cases
  (never a misleading empty success).

## Clarifications

### Session 2026-06-13

No outstanding ambiguities. Running unattended, all decision points were resolved with documented
defaults rather than questions (see Assumptions): dedicated `document-evidence --id` subcommand
(not a `--mismatches` flag), reuse of the existing `summarize_mismatches` engine, source attachment
ids read from the global document→entry link provenance, JSON-to-stdout output, and a non-zero exit
for an unknown document id.

## Assumptions

- The resolver is added as a dedicated `document-evidence --id <document_id>` subcommand (one of the
  two options the design doc §4.3 offers), rather than a `--document-id` flag on `mismatches`. A
  dedicated command keeps the document-resolution concern isolated, gives a clear place for the
  unknown-id error, and leaves the `mismatches` flag surface unchanged. This is an internal,
  agent-facing CLI assumption with no user-visible UI impact.
- The command reuses the existing `summarize_mismatches` engine scoped by attachment ids — it adds
  only the document→attachment resolution step in front of it, so finding shape and `page_refs`
  behavior are identical to the existing command (no drift).
- Source attachment ids are read from the document→entry links' recorded provenance; this is global
  (a document is not period-scoped), matching how documents are built.
- Output is JSON to stdout (matching the existing `mismatches` command), for machine consumption by
  the agent.
