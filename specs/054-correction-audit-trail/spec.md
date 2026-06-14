# Feature Specification: Data-correction audit trail + reversibility (autonomous-correction safety net)

**Feature Branch**: `054-correction-audit-trail`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "TRIAGE-003: a durable, human-visible, reversible data-correction audit trail + verify-after gate for the autonomous triage agent — records each correction {attachment_id, page, field, from, to, evidence read_path, agent, timestamp} to a queryable analysis-owned store, gates the write on verify-after (target finding cleared AND no new finding appeared, else roll back/flag), and supports human undo"

## Overview

The false-positive triage agent (design: `docs/features/false-positive-triage-agent.md`) corrects
fiscal data **fully autonomously** — no human pre-approval gate (decision D3). For a fraud/forgery
audit tool, that makes two things load-bearing rather than optional (design §4.4, promoted to 🔴):

1. a **durable, human-visible, reversible record** of every autonomous correction, and
2. a **verify-after gate** that confirms a correction actually cleared the targeted finding *and*
   introduced no new finding — rolling back (or flagging) instead of leaving a silent bad state.

This feature delivers exactly those two safety mechanisms as a reusable building block. It does
**not** build the triage agent itself (that is TRIAGE-004 / #92) — it provides the audit store, the
record/verify/undo operations, and a thin composite "apply-correction" step the agent will call so
that every correction it makes is, by construction, logged and verified.

## Clarifications

### Session 2026-06-13

Resolved autonomously (unattended full-pipeline run; no interactive questions). Each decision below
had a reasonable, documented default; recording them here removes downstream ambiguity.

- Q: Where does the durable correction store live? → A: A new analysis-owned DB table
  `data_corrections` (not the gitignored verdicts cache, not `alerts.notes`). (See Assumptions.)
- Q: At what granularity is a correction recorded — per changed field or per page? → A: **One record
  per changed field** (`field`, `from`, `to`), even though the underlying staging write replaces the
  whole page extraction object. A single apply-correction call that changes N fields on a page yields
  N records sharing one correlation id (so they undo together).
- Q: What "from" state is captured so rollback/undo can restore it deterministically? → A: A snapshot
  of the attachment's pre-correction **staging page extraction(s)** for the affected page(s). Restore
  = re-write that snapshot to staging + re-run the scoped staging-driven propagation. This is the
  inverse of apply and needs no guessing.
- Q: How is "no new finding appeared" scoped? → A: Compared over the **affected attachment(s)** only
  (the corrected attachment and its shared-NF siblings), using the existing finding detector
  (`summarize_mismatches` scoped by attachment id) — a finding key present after but absent before,
  for that scope, fails verify-after.
- Q: Does this feature build the triage agent or a UI? → A: No. It delivers only the store + the
  record / apply-correction (with verify-after) / list / undo operations. Agent = TRIAGE-004;
  orchestrator = TRIAGE-005; dashboard view = possible follow-up. "Human-visible" is satisfied by a
  durable, queryable, listable store + a human-runnable undo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autonomous correction is logged and verified before it sticks (Priority: P1)

The triage agent has read a page image, established that the page legibly shows R$ 320 while the
system recorded R$ 800, and wants to correct the attachment's extraction. It calls the
apply-correction step with the corrected per-page value(s) and the evidence (the page `read_path`).
The step records the intended change (from→to, field, page, evidence, agent, timestamp), applies it,
re-derives findings, and only lets the correction stand if the targeted finding cleared **and** no
new finding appeared. On verify failure it rolls the data back to the pre-correction state and marks
the audit record as rolled-back, so the system is never left in a silently-wrong state.

**Why this priority**: This is the safety net the whole autonomous-correction decision (D3) rests
on. Without it, an unattended agent can silently hide a real finding or trade one mismatch for
another. It is the minimum viable slice — recording + verify-after gating — and delivers value even
before the agent that drives it exists (a human or script can call it).

**Independent Test**: Drive the apply-correction step against the local seeded data with a known
misread attachment: assert (a) an audit record is written with all required fields, (b) the data
changed when verification passed, (c) on an injected verify failure the data is restored and the
record is marked rolled-back. Fully testable without the agent.

**Acceptance Scenarios**:

1. **Given** an attachment with a finding caused by a misread value, **When** the agent applies a
   correction whose verify-after passes (target finding gone, no new finding), **Then** the
   corrected value is persisted, a `data_corrections` record is stored with
   `{attachment_id, page, field, from, to, evidence, agent, timestamp, status=applied}`, and the
   step reports success.
2. **Given** the same attachment, **When** a correction is applied but verify-after fails (the
   targeted finding does not clear, or a new finding appears), **Then** the attachment's
   pre-correction analysis is restored, the `data_corrections` record is stored with
   `status=rolled-back` and the reason, and the step reports failure without leaving partial state.
3. **Given** a correction was applied successfully, **When** the agent records a second correction to
   the same attachment, **Then** both records exist and are independently attributable (distinct ids,
   timestamps, from/to).

---

### User Story 2 - A human can review and undo any autonomous correction (Priority: P1)

An auditor opening the system wants to see what the agent changed and, if they disagree, reverse it.
They list the corrections (filterable by attachment / period / status), read each one's from→to +
evidence + agent + timestamp, and undo a chosen correction. Undo restores the recorded `from`
state, re-derives findings (so the original finding reappears for human attention), and records the
reversal so the trail is complete (the undo is itself auditable).

**Why this priority**: Reversibility is half the issue's acceptance criterion ("can be
reviewed/undone by a human"). An un-undoable autonomous change is unacceptable for a fraud tool.

**Independent Test**: After applying a correction, list it (verify all fields render), then undo it
and assert the pre-correction value is restored, the original finding reappears, and an audit record
captures the reversal.

**Acceptance Scenarios**:

1. **Given** one or more stored corrections, **When** a human lists them, **Then** each correction's
   `{attachment_id, page, field, from, to, evidence, agent, timestamp, status}` is returned in a
   stable, queryable form, optionally scoped by attachment / period / status.
2. **Given** an applied correction, **When** a human undoes it, **Then** the recorded `from` value is
   restored as the attachment's extraction, findings are re-derived, and the correction's status
   becomes `reverted` with a reversal timestamp + actor recorded.
3. **Given** a correction that was already rolled back (verify-after failed) or already reverted,
   **When** a human tries to undo it, **Then** the operation is rejected with a clear message and no
   data changes (only `applied` corrections are undoable).

---

### User Story 3 - The trail survives cache clears and is independent of the code-fix loop (Priority: P2)

The existing `improve-classification` loop records *code-fix* verdicts in an ephemeral
`<period>.verdicts.json` cache file. A data correction is a different thing (data, not code) and must
**not** be lost when the ephemeral cache is cleared, nor be conflated with code-fix verdicts. The
correction trail lives in durable storage queryable alongside the rest of the fiscal data.

**Why this priority**: Durability is explicit in the issue ("durable, human-visible"). The cache is
gitignored scratch; a correction recorded there would vanish on the next cache wipe.

**Independent Test**: Apply a correction, clear the ephemeral analysis cache, and assert the
correction record is still listable and undoable.

**Acceptance Scenarios**:

1. **Given** an applied correction, **When** the ephemeral analysis cache is deleted, **Then** the
   correction record and its from/to/evidence are still retrievable and undoable.
2. **Given** the code-fix verdict store and the data-correction store, **When** either is inspected,
   **Then** neither contains the other's records (no schema or semantic conflation).

---

### Edge Cases

- **No staging change recorded**: apply-correction is asked to correct but the supplied corrected
  page values are identical to what's already recorded (no-op) → it makes no data change, records no
  audit row, and reports "nothing to correct" rather than a spurious verified correction.
- **Verify-after cannot run**: the targeted finding cannot be identified (e.g. the caller passes a
  finding key that does not exist in the current summary) → the correction is treated as unverifiable
  and is **not** applied (fail-closed), with a clear error.
- **Identity-key change**: a correction that would change `(numero_documento, cnpj_emitente)` re-keys
  the document (prunes/spawns). The store must capture from→to for those fields too, and verify-after
  must still hold (target finding cleared, no new finding) — the rollback must restore the original
  key so no zombie document is left behind.
- **Rollback failure**: if restoring the pre-correction state itself fails, the correction record is
  marked `flagged` (not silently `applied`), so a human sees a correction that could neither be
  verified nor cleanly rolled back.
- **Concurrent/duplicate apply**: re-applying the identical correction (same attachment, page,
  field, from, to) is idempotent — it does not create a second conflicting record nor double-apply.
- **Target = remote vs local**: corrections against production must be explicit; an apply-correction
  run never implicitly writes production.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST record every autonomous data correction as a durable, queryable record
  capturing at minimum `{attachment_id, page, field, from-value, to-value, evidence reference,
  agent/actor identifier, timestamp}`.
- **FR-002**: Each correction record MUST be uniquely identifiable and independently attributable
  (distinct id, timestamp) so multiple corrections — including several on the same attachment — never
  collapse into one.
- **FR-003**: The correction store MUST be durable across ephemeral-cache clears and MUST be
  inspectable alongside the rest of the fiscal data, NOT in the gitignored analysis cache and NOT
  conflated with the code-fix verdict store.
- **FR-004**: Applying a correction MUST be gated by a **verify-after** step that, after the data
  change, re-derives findings and confirms BOTH (a) the targeted finding cleared AND (b) no
  previously-absent finding appeared for the affected scope.
- **FR-005**: On verify-after failure the system MUST restore the attachment's pre-correction
  analysis state (roll back) and MUST NOT leave a partially-applied or silently-wrong state; the
  correction record MUST reflect the `rolled-back` outcome and the failure reason.
- **FR-006**: The system MUST let a human review the recorded corrections — listing them with all
  recorded fields, optionally scoped by attachment, period, and/or status.
- **FR-007**: The system MUST let a human **undo** a previously-applied correction: restoring the
  recorded `from` state, re-deriving findings (so any genuine finding reappears), and recording the
  reversal (status `reverted`, reversal timestamp + actor) so the trail stays complete.
- **FR-008**: Undo MUST be allowed only for corrections in the `applied` state; attempting to undo a
  `rolled-back`, `flagged`, or already-`reverted` correction MUST be rejected with a clear message
  and MUST NOT change any data.
- **FR-009**: A correction that produces no actual data change (the corrected values equal the
  current values) MUST be a no-op: no audit record, no propagation, and a clear "nothing to correct"
  result.
- **FR-010**: Verify-after MUST fail closed: if the targeted finding cannot be located in the current
  findings summary (so "did it clear?" is unanswerable), the correction MUST NOT be applied.
- **FR-011**: Correction and undo operations MUST default to the LOCAL data target; writing the
  production target MUST require an explicit opt-in (never implicit).
- **FR-012**: Re-applying an identical correction (same attachment, page, field, from, to) MUST be
  idempotent — it MUST NOT create a conflicting duplicate record nor double-apply the change.
- **FR-013**: The evidence reference recorded with each correction MUST point to the page image the
  decision was based on (the page `read_path` / page reference from the findings summary), so a human
  can open exactly what the agent saw.

### Key Entities *(include if feature involves data)*

- **Data correction**: one autonomous correction event. Attributes: a stable id; the affected
  attachment id; the page label/index; the corrected field name; the previous value (`from`); the
  new value (`to`); an evidence reference (page image read_path / page ref); the acting agent id; the
  status (`applied` / `rolled-back` / `flagged` / `reverted`); creation timestamp; optional reversal
  timestamp + actor; the targeted finding key; and a free-text reason/detail (verify-after outcome).
  Belongs to the analysis-owned data, not the mirror tables and not the ephemeral cache.
- **Correction batch / apply request** (transient, not stored separately): the inputs to one
  apply-correction call — attachment id, the corrected per-page values, the targeted finding key, the
  evidence reference, the agent id, and the target (local/remote). Produces zero or more correction
  records and a verified/rolled-back/flagged outcome.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of autonomous corrections that change data produce a stored correction record
  with all required fields (`attachment_id, page, field, from, to, evidence, agent, timestamp`) —
  zero un-logged data changes.
- **SC-002**: Every correction whose verify-after fails leaves the data byte-identical to its
  pre-correction state (provable by re-reading the affected analysis), with a `rolled-back` record.
- **SC-003**: A human can reverse any applied correction and the pre-correction value is fully
  restored and the original finding reappears — verifiable end-to-end.
- **SC-004**: Correction records survive an ephemeral-cache wipe and remain listable/undoable (the
  store is durable).
- **SC-005**: No correction is ever applied without verify-after running; an unverifiable correction
  (target finding unlocatable) is never applied (fail-closed) — verifiable by attempting one.

## Assumptions

- **Audit store = a new analysis-owned database table** (`data_corrections`), not the ephemeral
  `<period>.verdicts.json` cache and not `alerts.notes`. Rationale: the issue requires a *durable,
  human-visible, queryable, reversible* store; the cache is gitignored scratch (fails durability) and
  `alerts.notes` is free-text on a different entity (fails queryability/attribution). A dedicated
  analysis-owned table is consistent with the mirror-table invariant (analysis derives into its own
  tables, never the scraper mirror). (Resolves design Q3.)
- **The correction primitive is "record the verified per-page value via the existing
  record-classification staging path, then propagate via the existing staging-driven apply"**
  (decision D2 + design §4.5). This feature adds the audit + verify-after + undo wrapper around that
  existing primitive; it does not invent a new extraction path. The `from` state captured is the
  attachment's current rolled-up analysis (enough to restore it on rollback/undo).
- **Verify-after compares the findings summary (the existing mismatch/finding detector) scoped to the
  affected attachment(s) before and after the correction.** "Target cleared" = the targeted finding
  key is absent afterward; "no new finding" = the post set introduces no key that was not in the pre
  set for that scope. This reuses the single-source-of-truth finding detector — no parallel logic.
- **Undo restores the recorded `from` extraction and re-propagates**, the inverse of apply. Because
  apply captured the full pre-correction analysis state, undo is a deterministic restore, not a guess.
- **Agent/actor identifier** defaults to a caller-supplied string (e.g. `triage-agent` or a human
  username for manual undo); when omitted it records a sensible default so attribution is never empty.
- **Scope of this feature**: the store + the record/verify/undo/list operations + a composite
  apply-correction step that the future triage agent calls. The triage agent (TRIAGE-004) and the
  batch orchestrator (TRIAGE-005) are out of scope here.
- **No UI surface is required by the issue** ("human-visible" is satisfied by a queryable, listable
  store + a list command). A dashboard view is a possible follow-up but not in scope; "human-visible"
  is met by durable, queryable records and a human-runnable list/undo.

## Dependencies

- Depends on #84 (TRIAGE-001, staging-driven apply) — **closed/merged**. The staging-driven `apply`
  is what makes a targeted, non-destructive single-attachment correction possible (it is both the
  safety guard and the scoping mechanism this feature's verify-after relies on).
