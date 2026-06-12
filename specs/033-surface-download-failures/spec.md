# Feature Specification: Surface partial attachment-download failures

**Feature Branch**: `033-surface-download-failures`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "Surface partial attachment-download failures during scrape: track failed attachment ids per period, record a downloads-missing count and the failed ids on the scrape_runs row, mark the run status partial (not success) when any --download-docs page fetch fails, and raise an idempotent alert for attachments still missing their pages after a download pass" (GitHub issue #41 / IMP-004)

## Context

During a scrape with attachment downloading enabled, an attachment whose page fetch fails ends up
persisted with no stored linkage to its pages — it is silently un-groupable (it can't join its
shared-invoice siblings) and unviewable (the detail dialog has no pages to render). Today the run
still reports as a success, nothing names which attachments failed, and recovery depends on an
operator happening to know that a separate "download-docs backfill" pass exists. A flaky portal
session therefore quietly produces a period with missing evidence.

This feature makes those partial failures **visible** at three levels: the run log, the persisted
run record, and the auditor-facing alert surface.

## Clarifications

### Session 2026-06-12

No critical ambiguities required interactive clarification — the materially-impactful decisions are
recorded in the Assumptions section (status value `partial`, run-level data via the existing
errors/notes channel rather than a new column, the alert produced by the analysis pass keyed on the
mirror's `file_path IS NULL` state). The ambiguity scan found all taxonomy categories Clear or
resolved by documented assumption.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator sees a partial run and knows to re-fetch (Priority: P1)

An operator runs a scrape with attachment downloading enabled. The portal session is flaky, so a
handful of attachments fail to download their pages. The operator needs to know — without combing
the verbose log line-by-line — that the run did not fully succeed and that a re-fetch is required.

**Why this priority**: This is the core operability gap. Without it, partial failures are invisible
and a period silently ships with missing evidence. A queryable run-level signal is the foundation
that the other stories build on.

**Independent Test**: Run a scrape where one or more attachment downloads fail. Verify the run's
persisted record reports a non-success status and carries the count and identifiers of the failed
attachments, and that the final run-log summary names them. Verify a fully-successful download run
still reports success with a zero failure count.

**Acceptance Scenarios**:

1. **Given** a scrape with downloading enabled where every attachment downloads successfully,
   **When** the run finishes, **Then** the run record's status is `success` and its failure count is
   zero.
2. **Given** a scrape with downloading enabled where at least one attachment fails to download its
   pages, **When** the run finishes, **Then** the run record's status is `partial` (distinct from
   both `success` and `error`) and its persisted record carries the number of failed attachments and
   their identifiers.
3. **Given** a run that had a fatal scrape error in addition to a download failure, **When** the run
   finishes, **Then** the status remains `error` (a fatal error dominates a partial-download
   warning).
4. **Given** any scrape with downloading enabled that has at least one failed attachment, **When**
   the run finishes, **Then** the final run-log summary lists the affected period(s) and the count of
   failed attachments per period.
5. **Given** a scrape run with downloading **disabled** (no `--download-docs`), **When** the run
   finishes, **Then** the failure count is zero and the status is unaffected by this feature (no
   attachment is expected to have pages).

### User Story 2 - Auditor sees an alert for unfetchable attachments (Priority: P2)

An auditor reviewing the dashboard needs missing evidence to surface as a finding, consistent with
the existing "large expense with no attachment" precedent. An attachment the portal exposed but the
scraper could not fetch is audit-relevant: there is a receipt the books reference that we could not
obtain.

**Why this priority**: Turns the operability signal into an audit signal on the alert surface that
auditors already monitor. Builds on the tracking from Story 1 but is independently valuable and
independently testable.

**Independent Test**: With a period that has at least one attachment still missing its pages, run the
analysis pass and verify exactly one alert per affected attachment appears on the alert surface, that
re-running does not duplicate it, and that the alert disappears once the attachment's pages are
fetched.

**Acceptance Scenarios**:

1. **Given** a period with an attachment that has no stored pages after a download pass, **When** the
   alert-producing pass runs, **Then** exactly one alert of a dedicated "attachment not downloaded"
   type exists for that attachment, scoped to its period, naming its entry for deep-linking.
2. **Given** the same unchanged state, **When** the pass runs again, **Then** the alert count for
   that attachment is unchanged (idempotent — no duplicate).
3. **Given** an attachment whose pages are subsequently fetched (its linkage becomes present),
   **When** the pass runs again, **Then** the alert for that attachment no longer exists.
4. **Given** an attachment that the books expect to have pages but for which the portal exposed none
   at all, the behavior is the same as a fetch failure — see Assumptions for how "missing pages" is
   determined.

### User Story 3 - Operator recovers with the existing backfill (Priority: P3)

After a partial run, the operator re-runs the existing download-backfill pass (which picks up
attachments still missing their pages) to recover the missing evidence; on success, the alert and
the run-level signal clear on the next pass.

**Why this priority**: No new recovery mechanism is needed — the backfill already exists. This story
documents that the new signals correctly clear once recovery succeeds, closing the loop.

**Independent Test**: After a partial run, run the backfill, then re-run the analysis pass; verify the
attachment now has stored pages and its alert is gone.

**Acceptance Scenarios**:

1. **Given** a partial run left attachments missing their pages, **When** the operator runs the
   existing backfill pass and it succeeds for those attachments, **Then** those attachments have
   stored page linkage and no longer count toward the failure signal on the next pass.

### Edge Cases

- **All downloads fail**: every attachment in a period fails. Status is `partial`, the count equals
  the number of expected attachments, and the alert pass raises one alert per attachment.
- **Re-scrape of a previously-partial period that now succeeds**: the run record reflects the new
  (lower or zero) failure count for that run; the alerts for now-fetched attachments clear.
- **Re-scrape that omits `--download-docs`**: existing stored page linkage is preserved (per the
  existing scrape-column-preservation behavior); this feature does not flip a previously-successful
  attachment into "failed" merely because this run did not attempt a download. Failure tracking
  counts only attachments this run actually attempted to download and could not obtain.
- **Fatal error mid-period**: a period that never completed its download phase is not counted as a
  partial-download failure (its failure is the fatal error, already surfaced as `error`).
- **An attachment with no pages already alerted, then the portal removes the whole row**: portal
  deletions are reconciled by the existing reconciliation step, which cascade-cleans the
  attachment's analysis-owned dependents (including its alerts) — no special handling here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: During a download-enabled scrape, the system MUST track, per period, the set of
  attachments it attempted to download but could not obtain any pages for.
- **FR-002**: The system MUST persist, on the scrape-run record, a count of attachments that failed
  to download and an identifier list of those attachments (across all periods in the run), in a form
  that is queryable after the run.
- **FR-003**: The system MUST set the scrape-run status to `partial` when at least one attachment
  failed to download AND no fatal scrape error occurred. A fatal scrape error MUST take precedence
  (status `error`). A run with no download failures and no fatal error MUST remain `success`.
- **FR-004**: The system MUST emit a final run-log summary that names the affected period(s) and the
  per-period count of attachments that failed to download, whenever any failed.
- **FR-005**: A run with no failed downloads (including any run where downloading was not requested)
  MUST report a failure count of zero and MUST NOT have its status changed by this feature.
- **FR-006**: The analysis/alert-producing pass MUST raise exactly one alert per attachment that the
  books reference but that has no stored page linkage, of a dedicated "attachment not downloaded"
  alert type, scoped to the attachment's period and carrying the attachment id and its owning entry
  id for deep-linking.
- **FR-007**: The "attachment not downloaded" alert MUST be idempotent across re-runs (a stable
  identity keyed on the attachment) and MUST clear once the attachment has stored page linkage.
- **FR-008**: Tracking and alerting MUST distinguish "attempted-and-failed this run" (which drives
  the run status and count) from "has no stored pages right now" (which drives the alert). The alert
  reflects the persistent state of the mirror, so it does not depend on whether the current run
  attempted a download.
- **FR-009**: This feature MUST NOT change the mirror tables' write contract: the scraper remains the
  only writer of mirror rows, and the alert is written through the existing analysis-owned alert
  path.

### Key Entities *(include if feature involves data)*

- **Scrape run record**: the persisted record of a scrape execution. Gains a queryable indication of
  how many attachments failed to download and which ones, plus a `partial` status value alongside the
  existing `running` / `success` / `error`.
- **Attachment**: a downloaded page bundle for a ledger entry. Its "has stored pages" state is what
  determines whether it is missing evidence; an attachment with no stored page linkage after a
  download pass is the subject of the alert.
- **Alert**: an auditor-facing finding. Gains a new "attachment not downloaded" type that flows
  through the existing alert surface (no new surface).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a scrape where any attachment download failed, an operator can determine from the
  persisted run record alone (without reading the verbose log) that the run was partial and exactly
  how many — and which — attachments failed, in under 1 minute.
- **SC-002**: 100% of attachments that fail to download during a run are reflected in the run's
  failure count and identifier list.
- **SC-003**: For every attachment a period references but cannot show pages for, exactly one
  auditor-facing alert exists, and re-running the alert pass any number of times does not create a
  duplicate.
- **SC-004**: Once an operator successfully re-fetches the missing pages, both the run-level failure
  signal (on the next run) and the per-attachment alert clear with no manual cleanup.
- **SC-005**: A fully-successful download run and a download-disabled run are indistinguishable from
  before this feature with respect to status and failure count (zero false positives).

## Assumptions

- **"Missing pages" is determined by the absence of stored page linkage** (the attachment's
  page-path field being empty/NULL). This is the same condition the existing download-backfill pass
  uses to find work, so the alert and the backfill stay in lockstep. An attachment for which the
  portal exposed zero images is therefore treated identically to a fetch failure — both leave no
  stored pages — which matches the audit intent ("we have no evidence for this attachment").
- **The new status value is `partial`**, sitting between `success` and `error`. Existing consumers of
  the status string render it generically, so introducing a third value requires no consumer change.
- **The run-level failure data is recorded in the existing free-form errors/notes channel on the run
  record** (the same channel the consistency-validation and parse-skip notes already use), formatted
  so the count and ids are human- and grep-queryable. No new run-record column is introduced, keeping
  this change schema-light and consistent with the established non-fatal-note convention. (The issue
  suggested "record the count on the scrape_runs row"; the notes channel satisfies "queryable after
  the run" without a migration. A dedicated column is deferred.)
- **The alert is produced by the analysis pass, not the scraper**, because alerts are analysis-owned
  and the scraper must not write analysis-owned tables (mirror invariant). The scraper surfaces the
  failure at the run level; the analysis pass surfaces the persistent missing-evidence state as the
  alert. This keeps a single source of truth for the alert (the mirror's stored-pages state) and
  makes the alert correct even for attachments left missing by an earlier run that the current run
  did not touch.
- **The alert reuses the existing alerts table and dashboard** (which render any type generically),
  with a deterministic per-attachment id for idempotency and a `DELETE`-then-`INSERT` atomic
  writeback consistent with the other analysis alert writebacks, so it self-clears when the
  attachment is fetched.
- **Failure tracking counts an attachment as failed only when a download was attempted and produced
  no pages**, so a re-scrape that omits the download flag does not manufacture failures, and the
  existing scrape-column preservation keeps prior successful linkage intact.
