# Feature Specification: Preserve user-set alert resolution state across analysis re-runs

**Feature Branch**: `023-preserve-alert-resolution`  
**Created**: 2026-06-11  
**Status**: Draft  
**Input**: GitHub issue #34 — "BUG-003: User-set alert `resolved`/`notes` state is wiped by every analysis re-run"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resolution survives a re-analysis (Priority: P1)

An auditor reviews an alert in the dashboard, decides it is handled, marks it **resolved**,
and writes a short note explaining the disposition. Later — possibly minutes later, because
the self-improving classification loop re-runs the analysis many times per period — the
analysis pipeline runs again. The alert's underlying finding still holds, so it is re-emitted.
The auditor expects the alert to remain **resolved with their note intact**; they should never
have to re-resolve the same finding.

**Why this priority**: This is the entire bug. User-entered data (resolution + notes) is
silently destroyed on every pipeline run, which makes the resolve feature effectively useless
and erodes trust in the audit record. Fixing it is the whole point of the feature.

**Independent Test**: Resolve an alert (set `resolved=true`, add notes) via the alert detail
page, re-run `python -m analysis analyze` for that alert's period, then reload the alert — it
must still be resolved and still carry the same notes.

**Acceptance Scenarios**:

1. **Given** a per-period alert (e.g. `attachment_amount_mismatch`) that a user has marked
   resolved with notes, **When** the analysis pipeline re-runs and re-emits that same alert
   (same deterministic id), **Then** the reloaded alert is still resolved, with the same
   `resolved_at` and notes.
2. **Given** the global `document_overpayment` alert that a user has resolved with notes,
   **When** the global overpayment writeback re-runs and re-emits it, **Then** its resolution
   state and notes are preserved.
3. **Given** an alert a user has annotated with notes but **not** resolved, **When** the
   pipeline re-runs and re-emits it, **Then** the notes are preserved and it remains unresolved.

---

### User Story 2 - Stale findings still clear (Priority: P2)

When a finding genuinely disappears (the underlying data was corrected, so the alert is no
longer emitted on the next run), the auditor expects that alert to vanish from the list —
including any resolution state it carried. Preserving disposition must not resurrect findings
that no longer apply.

**Why this priority**: The fix must not over-correct into "alerts never disappear." Carrying
state forward only makes sense for findings that re-fire; obsolete findings should still be
dropped so the alert list reflects current reality.

**Independent Test**: Resolve an alert, change the source data so the finding no longer fires,
re-run analysis, and confirm the alert is gone from the list (not preserved as a resolved-but-
orphaned row).

**Acceptance Scenarios**:

1. **Given** a resolved alert whose finding no longer reproduces, **When** the pipeline re-runs
   and does not re-emit that alert id, **Then** the alert is absent from the alert list.

---

### Edge Cases

- An alert is resolved, then the finding stops firing, then later fires again: the second
  appearance is a **fresh** finding (no prior row existed at write time) and correctly comes
  back unresolved. Preservation only carries state across a contiguous re-emission.
- A user resolves an alert during the brief window while the pipeline is mid-run: last-writer-
  wins on the row is acceptable; no locking is required. (The pipeline reads existing state at
  the moment it writes; a resolve that lands after that read is simply applied to the freshly
  written row by the next run.)
- The per-period writeback and the global `document_overpayment` writeback are two separate
  delete-then-insert paths; **both** must preserve state, not just one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the analysis pipeline re-writes alerts for a period, it MUST preserve the
  user-set resolution fields (`resolved`, `resolved_at`, `notes`) of any alert that is re-emitted
  with the same identity (deterministic id) as a row being replaced.
- **FR-002**: The global `document_overpayment` writeback MUST preserve the same resolution
  fields for re-emitted alerts, using the same identity-matching approach as the per-period path.
- **FR-003**: Alerts that are **not** re-emitted on a given run (their finding no longer fires)
  MUST be removed, including any resolution state they previously held.
- **FR-004**: The emitted-alert construction MUST NOT unconditionally reset resolution fields to
  "unresolved / no notes." Resolution state for a re-emitted alert MUST come from the existing
  row, not be hardcoded to a default.
- **FR-005**: A brand-new alert (no prior row with that id) MUST be written as unresolved with no
  notes — the default for findings that have never been seen.
- **FR-006**: Preservation MUST be keyed on the alert's deterministic id so it is reliable across
  re-runs; it MUST NOT rely on matching on volatile fields (title, description, extracted values).
- **FR-007**: The behavior MUST be idempotent: running the pipeline twice in a row with no source
  changes and no user interaction MUST leave alert resolution state unchanged.

### Key Entities *(include if feature involves data)*

- **Alert**: a detected finding written to the `alerts` table. Carries analysis-owned fields
  (id, type, severity, title, description, reference_period, metadata, created_at) and
  **user-owned** fields (`resolved`, `resolved_at`, `notes`). The id is deterministic
  (`det_id("alert", period, type, discriminator)`), so a re-emitted finding maps to the same row.
  The fix concerns the ownership boundary: the pipeline owns the analysis fields; the user owns
  the resolution fields; a re-run must not let the former overwrite the latter.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After resolving an alert and running the analysis pipeline any number of times for
  its period, the alert remains resolved with its notes intact 100% of the time (as long as the
  finding still fires).
- **SC-002**: An auditor never has to re-resolve a finding they have already dispositioned, for
  as long as that finding continues to be detected.
- **SC-003**: Findings that no longer reproduce disappear from the alert list on the next run
  (0% false-persistence of obsolete alerts).
- **SC-004**: Two consecutive pipeline runs with no source-data change and no user action produce
  identical alert resolution state (fully idempotent).
