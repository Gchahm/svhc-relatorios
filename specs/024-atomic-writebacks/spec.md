# Feature Specification: Atomic delete-then-insert writebacks (no partial-failure data loss)

**Feature Branch**: `024-atomic-writebacks`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "make analysis delete-then-insert writebacks atomic to prevent partial-failure data loss" (GitHub issue #37, BUG-006)

## Context

The analysis pipeline persists two kinds of recomputed state with a "clear the old rows, then
insert the new rows" pattern. Today each pattern runs the clear and the insert as **two separate
database calls**. A failure that lands between the two calls commits the delete but never runs the
insert, leaving the data store in an inconsistent state that is silently wrong:

- **Attachment analyses** — the delete batch also stamps the attachment as "classified" (so it
  leaves the work-to-do set). If the follow-up insert fails, the attachment ends up with **no
  analysis at all** yet is marked done, so no automatic re-run ever revisits it. The vision work
  is silently lost until an operator manually re-queues it.
- **Alerts** — the delete clears a period's alerts (or all overpayment alerts). If the follow-up
  insert fails, that scope ends up with **zero alerts**, which the dashboard renders as a clean
  bill of health — the most dangerous failure mode for an auditing tool, because it hides
  findings rather than surfacing an error.

## Clarifications

### Session 2026-06-11

- Q: When one attachment's writeback fails mid-batch run, should the whole run abort or continue with the remaining attachments? → A: Abort loudly (propagate the error). Attachments written before the failure were each committed atomically and stay classified; the failing one stays pending; a re-run picks it up. This matches the current per-attachment loop, which already propagates the underlying error.
- Q: What is the atomic unit for the attachment-analysis writeback — per attachment, or the whole period at once? → A: Per attachment (unchanged granularity). Each attachment's clear + insert + classified-stamp are folded into one submitted batch, so partial results across attachments still land incrementally and a failure is healed by re-running only the unwritten ones.
- Q: How is "atomic" achieved without new infrastructure? → A: Fold each writeback's statements (delete(s) + insert(s) [+ stamp]) into a single submitted database batch, which the database runs as one implicit transaction. No new dependency, no schema change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Alerts survive a transient writeback failure (Priority: P1)

An auditor relies on the dashboard's alert list to know which entries need scrutiny. When the
analysis pipeline re-runs and the database write hits a transient failure partway through, the
auditor must never be shown a falsely empty (or partially emptied) alert list. Either the alert
set is fully updated to the newly computed findings, or it is left exactly as it was before the
run — never an in-between state where findings silently vanish.

**Why this priority**: Silently hiding findings directly defeats the tool's purpose (fraud /
corruption detection). A clean-looking dashboard that is actually the result of a half-completed
write is the worst possible outcome.

**Independent Test**: Simulate a writeback where the insert step fails after the delete step. Verify
that the previously stored alerts for the affected scope are still present (the run is a no-op on
failure), and that the failure is reported loudly rather than swallowed.

**Acceptance Scenarios**:

1. **Given** a period that already has stored alerts, **When** the analysis re-run computes a new
   alert set but the database write fails midway, **Then** the period's previously stored alerts
   remain intact (no scope is left empty) and the operator is informed the run failed.
2. **Given** a period whose new alert set is empty (all prior findings resolved by the data), **When**
   the writeback succeeds, **Then** the period's alerts are cleared to empty — the legitimate
   "no findings" result is still achievable.
3. **Given** a successful re-run, **When** it completes, **Then** the stored alerts exactly equal the
   newly computed set for that scope (no stale rows from a prior run linger).

### User Story 2 - A failed attachment analysis re-runs automatically (Priority: P1)

An operator runs the classification/analysis pipeline over a batch of attachments. If writing one
attachment's analysis fails partway, that attachment must remain in the "to be analyzed" set so the
next run picks it up automatically — the operator should not have to discover the loss and manually
re-queue it.

**Why this priority**: A self-hiding loss (attachment marked done but holding no analysis) is
operationally invisible and erodes trust in the completeness of the data.

**Independent Test**: Simulate a writeback where the analysis insert fails after the delete. Verify
the attachment is still pending (not stamped classified) so a subsequent run re-attempts it, and the
prior analysis (if any) is not left half-deleted.

**Acceptance Scenarios**:

1. **Given** a pending attachment, **When** its analysis writeback fails, **Then** the attachment is
   still pending afterwards and a re-run re-attempts it without manual intervention.
2. **Given** a pending attachment with an earlier analysis on file, **When** its writeback fails,
   **Then** it is not left with the old analysis deleted and no new analysis written.
3. **Given** a pending attachment, **When** its analysis writeback succeeds, **Then** the attachment
   is marked classified (leaves the pending set) and carries exactly the newly written analysis with
   no stale per-page records from a prior analysis.

### User Story 3 - Operator sees a loud, actionable error on partial failure (Priority: P2)

When a writeback cannot complete, the operator must get a clear, scope-identifying error in the run
output rather than a silent success, so they know the data may be inconsistent and a re-run is
required.

**Why this priority**: Even with atomic writes, the operator needs to know a run did not fully
succeed. A loud failure is far better than a silent one.

**Independent Test**: Force a writeback failure and confirm the run surfaces a non-zero/clearly
logged error naming the affected scope.

**Acceptance Scenarios**:

1. **Given** any writeback that fails, **When** the run continues or exits, **Then** the failure is
   reported (logged at error level and/or raised) identifying the affected scope.

### Edge Cases

- **Empty new set**: When the freshly computed set is empty (no analyses / no alerts for the scope),
  the writeback must still clear the old rows so the scope correctly shows "none" — an empty result
  is a valid outcome, distinct from a failed write.
- **No prior rows**: When there were no rows to delete, the writeback proceeds normally (the clear is
  a no-op, the insert runs).
- **Stamp ordering**: The "mark classified" stamp must only take effect together with (or after) a
  successful analysis insert — never together with the delete alone.
- **Resolution preservation interaction (alerts)**: The existing behavior that carries user-set
  alert `resolved`/`notes` state onto re-emitted alerts (feature 023 / issue #34) must be preserved
  unchanged; making the write atomic must not regress it.
- **Concurrent / repeated runs**: Re-running after a failure must be safe and idempotent (the same
  inputs produce the same final state, with no duplicate or orphaned rows).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Each attachment-analysis writeback MUST apply its clear-old-rows step and its
  insert-new-rows step as a single atomic unit, so a failure can never commit the clear without the
  insert.
- **FR-002**: The "mark attachment classified" stamp MUST NOT be committed unless the new analysis is
  also committed; on a failed writeback the attachment MUST remain pending so it is re-attempted on
  the next run without manual re-queuing.
- **FR-003**: Each alerts writeback (per-period and the global overpayment writeback) MUST apply its
  clear-old-rows step and its insert-new-rows step as a single atomic unit, so a failure can never
  leave the scope with the old alerts deleted and the new ones not inserted.
- **FR-004**: A writeback that fails MUST surface the failure (propagate an error / log loudly,
  identifying the affected scope) rather than silently completing.
- **FR-005**: When the newly computed set for a scope is empty, the writeback MUST still clear the
  prior rows so the scope correctly reflects an empty result (a legitimate "no findings"/"no
  analysis" outcome must remain achievable).
- **FR-006**: A successful writeback MUST leave the scope holding exactly the newly computed rows,
  with no stale rows lingering from a prior run (parity with today's delete-then-insert result).
- **FR-007**: The existing preservation of user-set alert `resolved`/`notes` state across re-runs
  (feature 023 / issue #34) MUST continue to work unchanged.
- **FR-008**: The change MUST require no database schema migration (it is a write-sequencing fix
  over existing tables).

### Key Entities *(include if feature involves data)*

- **Attachment analysis writeback**: clears a single attachment's roll-up analysis and its per-page
  records, writes the freshly computed analysis, and (only on success) stamps the attachment as
  classified so it leaves the pending set.
- **Alerts writeback**: clears a scope's alerts (a period's alerts, or all overpayment alerts) and
  writes the freshly computed alert set for that scope, preserving user disposition on re-emitted
  rows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a simulated insert-after-delete failure of an alerts writeback, the affected scope
  retains 100% of its prior alerts (zero scopes left empty by the failure).
- **SC-002**: In a simulated insert-after-delete failure of an attachment-analysis writeback, the
  attachment remains in the pending set 100% of the time, and a subsequent run re-attempts it with no
  manual intervention.
- **SC-003**: Every writeback failure produces an operator-visible error identifying the affected
  scope (no silent successes on failure).
- **SC-004**: For successful runs, the final stored rows for every scope are identical to those the
  current (non-atomic) implementation produces — no behavioral regression for the happy path,
  including preservation of user-set alert resolution/notes.

## Assumptions

- **Atomicity mechanism**: The database executes the statements of a single submitted batch/file as
  one implicit transaction. Folding the clear and the insert into one submitted batch is therefore
  sufficient to make each writeback atomic; this is the project's existing escape hatch for
  multi-statement SQL and is assumed to remain the contract. (Issue #37's "batch atomically"
  suggestion.)
- **No schema change**: The fix is purely about how/when statements are submitted; no new tables or
  columns are introduced.
- **Scope**: Only the two writeback paths named in issue #37 are in scope — attachment-analysis
  writeback and the alerts writebacks (per-period + global overpayment). Other writes (e.g. the
  scraper's upserts, documents-entity build) are out of scope for this feature.
- **Testing approach**: Because the real database write goes through an external CLI, atomicity and
  the failure/ordering guarantees are verified primarily by unit tests that intercept the
  database-write seam (asserting a single combined batch is submitted, that the classified stamp
  is part of/after the insert, and that a simulated insert failure leaves prior state intact),
  rather than by provoking a real mid-batch network failure.
- **Loud-failure baseline**: The existing database-write seam already raises on a non-zero CLI exit;
  the fix keeps that propagation and adds scope-identifying context where helpful, rather than
  swallowing errors.
