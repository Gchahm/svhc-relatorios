# Feature Specification: Prune stale documents and links after re-classification

**Feature Branch**: `025-prune-stale-documents`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "Make build_documents an authoritative write: prune stale documents and document_entries rows that are no longer in the current run's desired state (so re-classification leaves no zombie document rows or links), batched atomically with the upsert"

## Clarifications

### Session 2026-06-11

Run unattended in the one-shot pipeline; the following decisions were resolved by reasonable
default (recorded here per the "document assumptions" mandate) rather than asked:

- Q: Should `document_entries` and `documents` be pruned by deleting only stale rows, or by a full
  delete-then-reinsert of all derived rows? → A: Authoritative full delete-then-reinsert in one
  batch (mirrors the alert writeback; simplest path to FR-001/FR-005 since these are pure derived
  tables with no user-owned state per A-002).
- Q: When the desired state is empty, prune all or skip? → A: Prune all (FR-004) — the empty desired
  state is the correct authoritative state.
- Q: Must pruning be period-scoped or global? → A: Global (FR-006) — the build itself is global, so a
  scoped prune could wrongly delete other periods' documents.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Re-classification removes the obsolete document (Priority: P1)

An auditor relies on the documents view and the overpayment alert to reflect what the
pipeline currently believes about each invoice. When a page is re-read (e.g. by the
self-improving classification loop) and its extracted invoice number / issuer changes,
the auditor expects the previously-built (wrong) document — and its link to the entry — to
disappear, leaving only the document that matches the current extraction.

**Why this priority**: This is the core bug. Today the document builder only inserts/updates;
the obsolete document and its entry link survive forever, so the same entry's amount is
counted under two documents — a zombie that distorts the documents list and can trigger a
false `document_overpayment` (critical) alert. Correctness of derived fiscal data is the
project's whole purpose.

**Independent Test**: With local data, build documents once, mutate an attachment analysis's
extracted invoice number/CNPJ to a new key, re-run the build, and confirm the old document
row and its `document_entries` link are gone while the new ones are present.

**Acceptance Scenarios**:

1. **Given** an attachment analysis previously yielded document D1 (with link L1 to its entry),
   **When** the analysis is re-classified to a new (number, CNPJ) key and the build is re-run,
   **Then** D1 and L1 no longer exist in the database and the new document D2 + link L2 do.
2. **Given** a document whose only supporting analysis loses its confident (number, CNPJ) key
   (e.g. a re-read that can no longer read the invoice number), **When** the build is re-run,
   **Then** that document and its link are removed (it has zero supporting links).
3. **Given** the documents page lists D1 before re-classification, **When** the build is re-run
   after re-classification, **Then** D1 is absent from `/dashboard/documents`.

---

### User Story 2 - No false overpayment alert from a zombie document (Priority: P1)

An auditor must trust that a `document_overpayment` alert reflects a real over-claim, not an
artifact of stale derived rows.

**Why this priority**: A zombie document still sums its entry's live amount, so an entry whose
amount is legitimately claimed once can appear over-claimed because it is linked to both the
zombie and the current document — a false critical alert that wastes auditor time and erodes
trust in the signal.

**Independent Test**: Reproduce the scenario in User Story 1, then run the full analysis and
confirm no `document_overpayment` alert is raised solely because the obsolete document still
links the entry.

**Acceptance Scenarios**:

1. **Given** re-classification has moved an entry from document D1 to D2, **When** the analysis
   pipeline runs, **Then** the overpayment check evaluates the entry under D2 only and does not
   raise an alert attributable to the now-removed D1.

---

### User Story 3 - Visible accounting of what the build changed (Priority: P3)

An operator running the pipeline wants to see at a glance that the documents set shrank when a
re-classification removed documents, not just that it grew.

**Why this priority**: Observability aid; nice-to-have. Without it a shrinking set is silent and
a regression (over-pruning) would be hard to notice from the logs.

**Independent Test**: Run the build after a re-classification that removes a document and confirm
the run's log line reports the number of documents and links pruned in addition to those upserted.

**Acceptance Scenarios**:

1. **Given** a build run that removes 1 document and 1 link, **When** it completes, **Then** the
   log reports both the upserted counts and the pruned counts.

---

### Edge Cases

- **Empty desired state**: every analysis loses its confident key (or there are no analyses) →
  the build must remove ALL documents and links (the desired state is empty), not skip pruning.
- **No change**: re-run with an identical desired state → no rows removed, no rows effectively
  changed; the operation is idempotent.
- **Document still referenced by other entries**: a key shared across multiple entries where only
  one entry's analysis was re-classified → only the obsolete link is removed; the document and its
  remaining links survive (the document is still in the desired set).
- **Partial-failure safety**: if the write fails midway, the database must not be left with the
  stale rows removed but the new rows missing (or vice versa) — the clear-and-rebuild must be a
  single atomic unit, like the existing alert writebacks.
- **Scope**: the build is global (reads all analyses across all periods); pruning MUST also be
  global so a period filter on the surrounding analysis run never causes documents from other
  periods to be wrongly removed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The document build MUST be an authoritative write of the complete derived state:
  after a build, the set of documents and the set of entry links present MUST equal exactly the
  set the current analyses produce — no extra (stale) documents or links may remain.
- **FR-002**: The build MUST remove any entry link that is not in the current run's desired link
  set (e.g. a link whose supporting analysis was re-classified to a different document).
- **FR-003**: The build MUST remove any document that is not in the current run's desired document
  set (e.g. a document whose only supporting analyses lost or changed their identifying key).
- **FR-004**: When the desired state is empty (no analysis carries a confident key), the build MUST
  remove all documents and all links.
- **FR-005**: The remove-stale and insert/update steps MUST be applied as a single atomic unit so a
  partial failure cannot leave the derived data in a state where stale rows were removed but the new
  rows were not written (or vice versa), matching the existing alert-writeback atomicity guarantee.
- **FR-006**: Pruning MUST be global (covering documents/links from all periods), independent of any
  period filter applied to the surrounding analysis run.
- **FR-007**: The build MUST remain idempotent: re-running it with an unchanged desired state MUST
  not remove any document/link beyond reasserting the same state.
- **FR-008**: The build's run log MUST report the number of documents and links pruned in addition to
  the number upserted, so a shrinking derived set is visible.

### Key Entities *(include if feature involves data)*

- **Document**: a real fiscal document (NF/NFS-e/receipt/boleto) identified inside attachment pages,
  keyed by (normalized number, issuer CNPJ); global, not period-scoped. Derived solely from the
  current attachment analyses.
- **Document–entry link**: the N:N association between a document and a ledger entry, with the
  source attachment recorded for provenance. Derived solely from the current attachment analyses.
- **Attachment analysis**: the rolled-up per-attachment extraction that supplies each document's
  identifying key and reconciliation total; the authoritative source for the desired document state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a re-classification that changes an analysis's document key, the count of
  documents not backed by any current analysis is 0 (no zombie documents remain).
- **SC-002**: After a re-classification that re-points an entry to a new document, the count of
  entry links pointing at documents/keys no longer produced by the analyses is 0.
- **SC-003**: No `document_overpayment` alert is attributable to a document that is not backed by a
  current analysis.
- **SC-004**: Re-running the build with an unchanged desired state changes 0 documents and 0 links
  (the persisted state is identical before and after).
- **SC-005**: A build that removes documents/links reports the pruned counts in its run output.

## Assumptions

- **A-001**: The desired state is fully and correctly recomputable from the current
  `attachment_analyses` on every run (the build already reads ALL analyses globally), so an
  authoritative replace of the documents/links derived rows is safe — these tables are pure derived
  data with no user-owned state to preserve (unlike `alerts`, which preserve resolution/notes).
- **A-002**: There is no user-editable state on `documents` or `document_entries` to graft back after
  a delete (confirmed: the only user-owned analysis state lives on `alerts`); therefore pruning may
  delete-and-reinsert freely without a resolution-preservation step.
- **A-003**: Identity is deterministic (`det_id`), so a document/link that survives a rebuild keeps the
  same id; the prune compares against the freshly computed id sets rather than diffing field values.
- **A-004**: The number of documents/links is small enough that an authoritative `DELETE … WHERE id
  NOT IN (<desired ids>)` (or equivalent) is acceptable; if the desired set is empty the prune becomes
  an unconditional `DELETE FROM` of both tables.
- **A-005**: No database schema change is required — only the write logic of the existing build changes.
