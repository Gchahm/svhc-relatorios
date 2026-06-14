# Feature Specification: triage-false-positives skill (batch orchestrator over open findings)

**Feature Branch**: `059-triage-false-positives`
**Created**: 2026-06-14
**Status**: Draft
**Input**: User description: "triage-false-positives skill: a thin batch orchestrator (.claude/skills/triage-false-positives/) that, given a period or finding filter, lists candidate documents read-only via the mismatches CLI, fans out one fix-document-findings agent per candidate document in parallel (budget-isolated, holding no page images itself), collects terse JSON results, and reports a summary (corrected N / left M findings / escalated K systematic faults). Implements design docs/features/false-positive-triage-agent.md §6 decision D1. Depends on the merged #92 fix-document-findings agent."

## Clarifications

### Session 2026-06-14

Resolved autonomously (unattended `full` run) — recorded here for traceability; full rationale in
the Assumptions section:

- Q: What is the fan-out unit when most findings carry only an attachment id? → A: candidate =
  `document_id` if present else `attachment_id`, deduped (one agent per candidate).
- Q: Does the orchestrator re-run classification/analysis to refresh findings before listing? → A:
  No — read-only `mismatches` only; agents do their own scoped propagation.
- Q: How is a finding filter expressed? → A: `--kind <kind…>` over the output and/or `--entry-id
  <id…>` through the `mismatches` CLI scope; no new persistence.
- Q: What happens when a dispatched agent errors? → A: that candidate is counted `agent-error` under
  "left for human"; the batch continues.
- Q: New CLI command or schema change? → A: None — skill prompt only, composing existing assets.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scrub a whole period's false positives before human review (Priority: P1)

An auditor (or an automated caller) wants the document-vision noise removed from a period's findings
queue **before a human looks at it**, so the human sees only findings genuinely worth attention. They
run the `triage-false-positives` skill for a period. The skill lists the period's candidate
documents (those carrying at least one open finding) read-only, fans out one context-isolated
`fix-document-findings` agent per candidate document in parallel — each agent views that one
document's page image(s) in its OWN context, autonomously corrects demonstrable misreads (audited,
verify-after-gated), and returns a terse result — then the skill collects those results and reports a
single summary: how many findings were corrected, how many were left for the human (true findings,
page-errors, verify-failures), and how many systematic faults were escalated for a code fix.

**Why this priority**: This is the entire feature — the batch orchestration over a period. Without
it there is no way to scrub a period in one action; the per-document agent (#92) only handles one
document at a time.

**Independent Test**: Run the skill for a period that has a known false-positive finding (a legible
page the system misread) plus a known true finding. After it completes, the false positive is gone
from `mismatches`, the true finding remains, and the printed summary reports `corrected ≥ 1`,
`left ≥ 1`, and the orchestrator's own context never opened a page image.

**Acceptance Scenarios**:

1. **Given** a period with several candidate documents (each with ≥1 open finding), **When** the
   skill runs, **Then** it dispatches exactly one `fix-document-findings` agent per distinct
   candidate document, in parallel, and reports a summary aggregating every agent's terse result.
2. **Given** a candidate document whose finding is a demonstrable misread, **When** its agent
   corrects it, **Then** the corresponding finding no longer appears in a fresh read-only
   `mismatches` and the summary counts it under "corrected".
3. **Given** a candidate document whose finding is a real discrepancy (`true`), **When** its agent
   triages it, **Then** the finding is left untouched and the summary counts it under "left for
   human" with reason `true`.
4. **Given** the orchestrator runs over a multi-document period, **When** it finishes, **Then** its
   own transcript contains no page-image reads (all image work happened inside the fanned-out
   agents).

---

### User Story 2 - Triage only a slice of findings via a filter (Priority: P2)

The auditor wants to scrub only one class of finding — for example "all open amount mismatches" — or
the findings for one entry. They run the skill with a finding filter. The skill lists only the
candidate documents matching that filter and triages exactly those, reporting the same summary scoped
to the slice.

**Why this priority**: A useful narrowing for large periods or for re-running after a targeted change,
but the period-wide P1 path delivers the core value on its own.

**Independent Test**: Run the skill for a period with `--kind amount`; confirm only documents whose
open finding is an amount mismatch are dispatched, and a vendor-only mismatch document is not.

**Acceptance Scenarios**:

1. **Given** a period and a `--kind amount` filter, **When** the skill lists candidates, **Then**
   only documents carrying an open amount finding are dispatched.
2. **Given** an `--entry-id <id>` filter, **When** the skill lists candidates, **Then** only the
   document(s) backing that entry are dispatched.

---

### User Story 3 - Nothing to triage / convergence (Priority: P3)

The auditor runs the skill on a period whose findings have already been scrubbed (or that never had
any). The skill finds zero candidate documents and reports a clean "nothing to triage" summary
without dispatching any agent.

**Why this priority**: A correctness guard, not new value — but it must not error or fan out a
spurious agent.

**Independent Test**: Run the skill on a period with no open findings; confirm it dispatches no agent
and prints a `corrected 0 / left 0 / escalated 0` (zero candidates) summary.

**Acceptance Scenarios**:

1. **Given** a period with no open findings, **When** the skill runs, **Then** it dispatches no
   agent and reports zero candidates.

---

### Edge Cases

- **A document overpayment finding spans multiple attachments/entries.** Its mismatch row carries a
  `document_id`; the orchestrator treats that one document as a single candidate (one agent), not one
  agent per attachment.
- **Several findings share one attachment** (amount + vendor + date on the same attachment): the
  orchestrator dispatches ONE agent for that candidate, which judges all of its findings — it never
  fans out per-finding.
- **A candidate attachment is not linked to any built document** (no confident number+CNPJ): it still
  has open findings and must be triaged. The orchestrator dispatches it by its attachment id, tagging
  it `attachment`, and the agent gathers evidence via `mismatches --attachment-id` (the document-keyed
  `document-evidence` resolver does not accept a bare attachment id). An attachment finding that IS
  covered by a built document is folded into that document candidate instead (one agent, document id).
- **An agent returns an error / times out**: the orchestrator records that candidate as un-triaged
  (counted under "left for human" with reason `agent-error`) and continues with the others; one bad
  agent never aborts the batch.
- **The same document is referenced by two filter-matching mismatch rows**: it is dispatched once
  (de-duplicated by candidate id).
- **`--remote` is passed**: every read-only listing AND every dispatched agent operates on production
  data; the default is local.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The skill MUST accept a period (`YYYY-MM`, first token) and optionally a finding filter
  (`--kind <amount|vendor|date|page-error|document_overpayment>` and/or `--entry-id <id…>`) and a
  `--remote` flag (default local).
- **FR-002**: The skill MUST list candidate documents **read-only** by invoking the existing
  `mismatches` CLI (never ad-hoc SQL, never `apply`/`analyze` — it does not re-run classification or
  re-derive analyses; it triages what is already on the books).
- **FR-003**: The skill MUST group the listed mismatch rows into **distinct candidates** and dispatch
  **exactly one `fix-document-findings` agent per candidate**, in parallel (one message, multiple
  agent invocations), passing each agent its candidate id and the target flag.
- **FR-004**: The candidate id MUST be the finding's `document_id` when the mismatch row carries one
  (e.g. `document_overpayment`), and the finding's `attachment_id` otherwise. A per-attachment finding
  whose `attachment_id` is one of a document candidate's `attachment_ids` MUST fold into that document
  candidate (not spawn a separate one), and rows are de-duplicated by candidate id, so a
  document/attachment with several findings yields exactly one agent.
- **FR-005**: When a finding filter is supplied, the skill MUST list only the matching candidates
  (filter applied via the `mismatches` CLI scope flags and/or a kind filter over its output) and
  dispatch only those.
- **FR-006**: The skill MUST collect each agent's terse JSON result
  (`{document_id, attachment_ids, corrections, left_as_finding, escalated, note?}`) and MUST NOT
  open any page image, run any correction command, or inspect any artifact in its own context — all
  heavy work stays inside the agents.
- **FR-007**: The skill MUST report a single concise summary aggregating across agents: total
  candidates, **corrected** (sum of `corrections`), **left for human** (sum of `left_as_finding`,
  broken down by reason: `true` / `page-error` / `verify-failed` / `unverifiable` / `no-op` /
  `agent-error`), and **escalated** (sum of `escalated`, listing each `{area, hypothesis}`).
- **FR-008**: When an agent errors or returns un-parseable output, the skill MUST count that
  candidate under "left for human" with reason `agent-error` and continue the batch (one failure
  never aborts the run).
- **FR-009**: When there are zero candidates, the skill MUST dispatch no agent and report a
  "nothing to triage" (zero-candidate) summary without error.
- **FR-010**: The skill MUST NOT merge code, push to `main`, or itself make any data correction —
  data corrections happen only inside the agents via their audited `apply-correction` path; code
  fixes for escalated systematic faults are deferred to the human / the `improve-classification`
  path.
- **FR-011**: The skill MUST thread the `--remote` flag to BOTH the read-only `mismatches` listing
  and every dispatched agent, so a remote run reads and corrects production consistently; default is
  local and production is never written implicitly.

### Key Entities *(include if feature involves data)*

- **Candidate**: a distinct document or attachment carrying ≥1 open finding in the target period
  (after filtering). Identified by `document_id` when available, else `attachment_id`. The unit of
  fan-out: one agent per candidate.
- **Mismatch row**: one open finding as printed by the `mismatches` CLI — `{period, kind,
  attachment_id?, entry_id?, document_id?, …, page_refs}`. The orchestrator reads only the
  identifying fields; it never opens `page_refs`.
- **Agent result**: the terse JSON a `fix-document-findings` agent returns —
  `{document_id, attachment_ids, corrections[], left_as_finding[], escalated[], note?}`. The unit the
  summary aggregates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running the skill over a period with a known false positive and a known true finding
  removes the false positive (it no longer appears in a fresh read-only `mismatches`) and leaves the
  true finding present.
- **SC-002**: The orchestrator's own context opens **zero** page images for any batch size — all
  image reads occur inside the fanned-out agents (verifiable from the transcript).
- **SC-003**: For a period with N distinct candidates the skill dispatches exactly N agents (one per
  candidate, de-duplicated), in parallel.
- **SC-004**: The reported summary's counts (corrected / left-by-reason / escalated) equal the
  element-wise sum of the agents' terse results.
- **SC-005**: An agent that errors does not abort the batch; its candidate is reported as
  `agent-error` and the remaining candidates are still triaged.

## Assumptions

- **Dispatch unit = candidate (document or attachment), not per-finding.** The design (§6 D1) says
  "one agent per document." Because most `mismatches` rows carry only an `attachment_id` (only
  `document_overpayment` carries a `document_id`), the orchestrator's universal unit is the candidate:
  `document_id` when present, else `attachment_id`. The `fix-document-findings` agent (#92) accepts
  "one document id (or attachment id)" per its own contract, so both forms are valid agent inputs.
  This is a documented decision, not a code change to the agent.
- **Read-only listing via `mismatches`.** The orchestrator does NOT run `classify`/`apply`/`analyze`
  to refresh the findings; it triages the findings already persisted. The per-document agents perform
  the scoped propagation (`apply-correction` → re-derive) themselves. Re-running the skill after
  corrections land naturally re-reads a shrunk candidate set (the durable work-queue is the
  re-derivable open-findings set).
- **Filter shape.** A finding filter is expressed as `--kind <kind>` (one or more) over the
  `mismatches` output and/or `--entry-id <id…>` passed through to the `mismatches` CLI scope. No new
  filter persistence is introduced.
- **No new CLI command, no D1 schema change, no migration.** This is a skill (orchestrator prompt)
  only; it composes the existing `mismatches` CLI and the existing `fix-document-findings` agent.
- **Skill, not agent.** It runs in the MAIN context (a skill can spawn agents; a subagent cannot —
  mirrors `improve-classification`), so it is built under `.claude/skills/`.
