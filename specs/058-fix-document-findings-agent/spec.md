# Feature Specification: fix-document-findings agent (per-document autonomous false-positive correction)

**Feature Branch**: `058-fix-document-findings-agent`
**Created**: 2026-06-14
**Status**: Draft
**Input**: User description: "fix-document-findings agent: a context-isolated per-document false-positive correction agent (.claude/agents/fix-document-findings.md) plus a composite `reclassify --attachment-id` CLI helper (§4.5). Implements design docs/features/false-positive-triage-agent.md §6, §4.5, §5, §7."

## Context

This is feature TRIAGE-004 (GitHub issue #92), the per-document correction worker of the
false-positive triage system designed in `docs/features/false-positive-triage-agent.md`. Its
dependencies have shipped: TRIAGE-001 (staging-driven `apply-extractions`, #84), TRIAGE-002
(`document-evidence` resolver, #85), and TRIAGE-003 (data-correction audit trail + reversibility +
verify-after, the `apply-correction` / `list-corrections` / `undo-correction` CLI, #88).

This feature builds the **agent that drives those primitives**, plus the one missing low-level
ergonomic primitive (the composite `reclassify` CLI, §4.5). It does NOT build the batch orchestrator
skill (`triage-false-positives`, TRIAGE-005 / #93) — that fans this agent out across many documents.

## Clarifications

### Session 2026-06-14

Run unattended (no interactive clarifier). The ambiguity scan found all high-impact categories already
resolved by the spec's Assumptions (A1–A6) and dependency contracts; the materially-impactful decisions
are recorded here for traceability:

- Q: Audit store for corrections (design Q3)? → A: Reuse the TRIAGE-003 `data_corrections` D1 table via
  `apply-correction`; no new store, no migration (A1).
- Q: Default target local vs remote (design Q5)? → A: LOCAL by default; `--remote` explicit per run for
  every command (A3, FR-011, FR-015).
- Q: How is each `apply-correction` outcome bucketed in the agent's result? → A: Only `applied` counts as
  a `correction`; `rolled-back`/`flagged`/`unverifiable`/`no-op` are reported under `left_as_finding`
  (still open); `systematic-fault` judgments go to `escalated` without a data change (FR-009, FR-010).
- Q: Is the typed-transcription `re-derive` path required to ship? → A: No — optional companion; the floor
  is per-attachment re-classification via the existing extraction primitive (A4).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autonomously correct a demonstrable misread (Priority: P1)

An auditor (or, ultimately, the batch orchestrator) hands the agent a single document/attachment id
whose dashboard finding is a known class of vision noise — e.g. an amount mismatch where the page
legibly shows R$ 320 but the system recorded R$ 800 (the 757dedb0 case). The agent gathers the
findings, opens the page image(s) in its own context, confirms at high resolution that the page
contradicts the recorded value, records the corrected per-page extraction, propagates it through the
pipeline, and confirms the finding cleared with no new finding appearing — all auditably and
reversibly, with no human pre-approval (design D3).

**Why this priority**: This is the entire purpose of the feature — autonomously scrubbing
vision-noise findings off the human review queue. Without it, every false positive needs a manual
re-classification (the runbook flow).

**Independent Test**: Given a seeded document whose recorded amount disagrees with a legible page,
invoke the agent with that document id; verify it returns a `corrections` entry, the
`data_corrections` store has an `applied` row, and the finding no longer appears in
`document-evidence` for that document.

**Acceptance Scenarios**:

1. **Given** a document with an `amount` mismatch where the page legibly shows the ledger value,
   **When** the agent runs, **Then** it records the corrected extraction, the finding clears, the
   correction is logged as `applied`, and the result JSON lists it under `corrections`.
2. **Given** a correction whose verify-after fails (the finding did not clear, or a new finding
   appeared), **When** the agent runs, **Then** the underlying primitive rolls the data back and the
   agent reports the finding as still open (left for the human), not as a successful correction.
3. **Given** an amount misread, **When** the agent records the correction, **Then** it preserves the
   document identity key `(numero_documento, cnpj_emitente)` so the document is corrected in place
   (not re-keyed into a new document) — unless the number/CNPJ itself is the misread.

---

### User Story 2 - Leave real findings and unreadable pages untouched (Priority: P1)

For a finding where the page genuinely disagrees with the books (a real discrepancy — possible
fraud), or where the page image is missing/illegible, the agent must change NOTHING and report the
finding for the human. Hiding a real finding is the worst possible failure for a fraud-audit tool.

**Why this priority**: This is the correctness floor (design §7). The agent is autonomous and
unreviewed, so an over-eager correction silently erases evidence. P1 alongside US1 — the two are
inseparable.

**Independent Test**: Given a document whose page legibly shows a value that really differs from the
ledger, invoke the agent; verify it makes NO data correction (no `data_corrections` row), the finding
remains open, and it is reported under `left_as_finding` with reason `true`/`page-error`.

**Acceptance Scenarios**:

1. **Given** a finding the agent judges `true` (page really disagrees), **When** it runs, **Then** it
   makes no correction and reports the finding under `left_as_finding` with reason `true`.
2. **Given** a finding whose page image is missing or illegible (`page-error`), **When** it runs,
   **Then** it makes no correction and reports it under `left_as_finding` with reason `page-error`.
3. **Given** any finding, **When** the agent is uncertain whether the page contradicts the record,
   **Then** it defaults to leaving the finding (evidence-bound only — never "make it match the
   ledger").

---

### User Story 3 - Escalate systematic faults instead of mass-correcting (Priority: P2)

When the agent recognizes that a finding is caused by a recurring code/mapper fault (e.g. roll-up
precedence, grouping, reconciliation tolerance) rather than an isolated misread, it must NOT data-correct
it. Per-document data correction of a systematic fault papers over the bug N times instead of fixing
it once. The agent reports it under `escalated` with a root-cause hypothesis for the code-fix path
(`improve-classification` / `fix-mismatch`).

**Why this priority**: Prevents the documented anti-pattern (design §5) of hand-correcting 100
documents when one code bug is the cause. Lower than P1 because misjudging a systematic fault as an
isolated one is recoverable (the correction's verify-after + audit trail catch it), whereas the US1/US2
floor is not.

**Independent Test**: Given a finding the agent attributes to a systematic root cause, verify it makes
no correction and reports it under `escalated` with an `area` + `hypothesis`.

**Acceptance Scenarios**:

1. **Given** a finding whose root cause is a systematic code/mapper fault, **When** the agent runs,
   **Then** it makes no data correction and reports the finding under `escalated` with a root-cause
   hypothesis.

---

### User Story 4 - Composite reclassify CLI for safe ordering (Priority: P2)

A maintainer (or the agent, when it wants a propagation without the full audit/verify gate) needs a
single command that records corrected per-page staging for one attachment and propagates it through
the pipeline in the correct, pinned order (`record-classification` per page → staging-driven
`apply-extractions` → `build-documents` → `analyze`), scoped to that attachment's period. This shrinks
the orchestration surface and pins the order (design §4.5).

**Why this priority**: Ergonomic primitive that the agent and humans both use. P2 because the
correction path the agent relies on for *audited* corrections is `apply-correction` (TRIAGE-003), which
already pins the order with the safety net; `reclassify` is the un-gated sibling for the cases the
audit trail does not require (e.g. re-running a known-good page set).

**Independent Test**: Run `python -m analysis reclassify --attachment-id <id> --pages '<json>'`
against seeded local D1; verify the staging rows are written, the attachment's roll-up is re-derived,
the global documents entity rebuilt, and alerts refreshed — and that an attachment whose staging was
NOT recorded is untouched (staging-driven `apply` safety).

**Acceptance Scenarios**:

1. **Given** corrected per-page fields for one attachment, **When** `reclassify` runs, **Then** the
   staging is recorded, the analysis re-derived, documents rebuilt, and alerts refreshed, scoped to
   the attachment's period.
2. **Given** an empty/invalid corrected-pages payload, **When** `reclassify` runs, **Then** it rejects
   the input (validation gate) and writes nothing.
3. **Given** `--remote` is omitted, **When** `reclassify` runs, **Then** it targets LOCAL D1 only
   (never an implicit production write).

---

### Edge Cases

- **Target finding not present before the correction**: the underlying `apply-correction` fails closed
  (`unverifiable`, no data change). The agent reports the finding under `left_as_finding` (it could not
  be verified) rather than silently dropping it.
- **No-op correction** (corrected values equal current): no `data_corrections` row, no change; the
  agent treats the finding as still open and reports it.
- **Document resolves to no source attachments**: `document-evidence` returns empty findings; the agent
  returns empty `corrections`/`left_as_finding`/`escalated` and a note.
- **Image budget**: a single document's pages must fit the agent's context (~18-image cumulative
  budget). The agent reads only this document's pages; a batch is fanned out one-agent-per-document by
  TRIAGE-005, out of scope here.
- **`--remote` threading**: the agent must thread the target flag end-to-end (resolver, correction,
  re-read) or it silently corrects only local data. Default LOCAL; remote requires an explicit flag.
- **Identity-key change**: when the *number or CNPJ itself* is the misread, correcting it re-keys the
  document (prunes old, spawns new) — that is correct in that case; the guardrail only forbids changing
  the key while fixing an *amount*.
- **Bash hook substrings**: the damage-control hook blocks `.key`/`.dump` substrings in inline Bash;
  the agent writes JSON payloads to a temp file rather than inlining `json.dumps`/`.keys()`.

## Requirements *(mandatory)*

### Functional Requirements

#### The agent (`.claude/agents/fix-document-findings.md`)

- **FR-001**: The agent MUST accept as input ONE document id (or attachment id) plus a target flag
  (default local), and operate only on that document's resolved attachments.
- **FR-002**: The agent MUST gather the document's findings + page-image `read_path`s via the existing
  `document-evidence` resolver (it MUST NOT issue ad-hoc SQL to map a document to its attachments).
- **FR-003**: For each finding, the agent MUST view the page image(s) in its OWN context (via the Read
  tool) and judge it as one of: `true` (real disagreement), `false-misread` (legible page the system
  misread, isolated), `systematic-fault` (recurring code/mapper cause), or `page-error`
  (missing/illegible).
- **FR-004**: For a `false-misread` only, the agent MUST correct the data by calling `apply-correction`
  with the corrected per-page extraction and the finding's `mismatch_key` as `--target-finding`, so the
  correction is recorded, applied, and gated by verify-after (TRIAGE-003).
- **FR-005**: The agent MUST NOT correct any finding judged `true` or `page-error` — these go to the
  human untouched (guardrail §7.2).
- **FR-006**: The agent MUST NOT data-correct a finding judged `systematic-fault`; it MUST report it for
  the code-fix path with a root-cause hypothesis (guardrail §7.5, decision tree §5).
- **FR-007**: A correction MUST be evidence-bound: allowed ONLY when the page legibly shows a value that
  contradicts what the system recorded. The agent MUST NOT correct merely to make a value match the
  ledger (guardrail §7.1).
- **FR-008**: For an amount correction, the agent MUST preserve the document identity key
  `(numero_documento / numero_nota, cnpj_emitente)` so the document is corrected in place; it changes
  the key only when the number/CNPJ itself is the misread (guardrail §7.3).
- **FR-009**: The agent MUST respect the verify-after result returned by `apply-correction`: only an
  `applied` result counts as a correction; `rolled-back`, `flagged`, `unverifiable`, and `no-op` results
  mean the finding was NOT cleared and MUST be reported as still open (left for the human).
- **FR-010**: The agent MUST return ONLY a terse JSON result of the shape
  `{document_id, attachment_ids, corrections: [...], left_as_finding: [...], escalated: [...]}` and MUST
  NOT return page images, transcripts, or full artifacts.
- **FR-011**: The agent MUST thread the target (local/remote) end-to-end through every CLI call
  (resolver, correction, re-read). Default LOCAL; remote only when explicitly requested.
- **FR-012**: The agent MUST be context-isolated (its own tools `Bash, Read, Glob`) so its page-image
  reads and judgment stay out of the caller's context.

#### The composite `reclassify` CLI helper (§4.5)

- **FR-013**: The analysis CLI MUST expose a `reclassify --attachment-id <id> --pages <json>` command
  that records the supplied corrected per-page extraction(s) as `page_classifications` staging, then
  propagates in the pinned order: staging-driven `apply-extractions` → `build-documents` → `analyze`,
  scoped to the attachment's period.
- **FR-014**: `reclassify` MUST validate each supplied page payload against the existing
  `page_classifications` contract (the same `validate_page_fields` gate as `record-classification`) and
  write nothing on a validation failure.
- **FR-015**: `reclassify` MUST default to LOCAL D1 and write REMOTE only with an explicit `--remote`
  flag (decision Q5 — never an implicit production write).
- **FR-016**: `reclassify` MUST accept the `--pages` payload as a JSON string or via stdin (`-` / omitted)
  and MUST print a terse JSON result to stdout (the propagation banner routed to stderr), consistent with
  the existing correction CLI commands.
- **FR-017**: `reclassify` MUST be non-destructive by construction: because `apply-extractions` is
  staging-driven (feature 050), an attachment for which no staging was recorded is never rolled up, so a
  mid-sequence crash leaves the attachment pending and self-healing (the helper adds ordering ergonomics,
  not a new safety mechanism).

### Key Entities *(include if feature involves data)*

- **Finding**: a per-document discrepancy from `document-evidence` — `kind` (amount/vendor/date/
  page-error/document_overpayment), the ledger-vs-extracted values, `page_refs`, and a stable
  `mismatch_key` identity.
- **Correction**: one `apply-correction` call's outcome — the corrected per-page fields, the
  `target_finding` key, and an `applied`/`rolled-back`/`flagged`/`unverifiable`/`no-op` result, recorded
  in the `data_corrections` store (TRIAGE-003).
- **Agent result**: the terse JSON the agent returns — `corrections` (cleared findings), `left_as_finding`
  (true / page-error / verify-failed / no-op), `escalated` (systematic faults + hypotheses).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Given a false-positive document (legible page contradicts the recorded value), the agent
  corrects it autonomously: the targeted finding no longer appears for that document, and the
  `data_corrections` store holds an `applied`, reversible row citing the page evidence.
- **SC-002**: Given a document whose page genuinely disagrees with the books, the agent makes ZERO data
  changes (no `data_corrections` row) and reports the finding for the human — i.e. the agent never hides
  a real finding.
- **SC-003**: The agent returns a terse JSON result and no page images/transcripts, keeping a caller's
  context clean (verified by the result shape).
- **SC-004**: `reclassify --attachment-id` re-derives one attachment's analysis + documents + alerts in
  a single command with the correct ordering, and leaves un-staged attachments untouched.
- **SC-005**: All new CLI behavior defaults to LOCAL D1; a production write requires an explicit
  `--remote`.

## Assumptions

- **A1 (audit store, design Q3)**: resolved by TRIAGE-003 — corrections are recorded in the
  `data_corrections` D1 table via `apply-correction`. This feature reuses that store; it adds no new
  store and no schema migration.
- **A2 (correction path)**: the agent's audited corrections go through `apply-correction` (which already
  pins record→propagate→verify-after and records/rolls back). The new `reclassify` CLI is the *un-gated*
  ordering primitive (§4.5) for propagation without the audit/verify gate; the agent uses
  `apply-correction` for any data change that must be audited (every autonomous correction).
- **A3 (local vs remote, design Q5)**: every command defaults LOCAL; `--remote` is explicit per run.
- **A4 (typed transcription / re-derive, §10)**: integration with the typed transcription + a `re-derive`
  step is OPTIONAL and not required to ship (issue note). The agent corrects via the existing
  per-page extraction primitive; if a `re-derive` command exists it MAY be used for systematic
  mapper-only cases, but the floor is per-attachment re-classification.
- **A5 (no batch orchestrator)**: the period/filter batch orchestrator (`triage-false-positives`,
  TRIAGE-005) is out of scope; this feature ships only the per-document agent + the `reclassify` CLI.
- **A6 (skill definitions cached)**: editing an agent `.md` mid-session does not reload it; the agent is
  exercised via its CLI primitives in this feature's verification, and the prompt is reviewed for
  correctness against the shipped CLI contracts.
