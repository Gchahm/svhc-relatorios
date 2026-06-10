# Feature Specification: Actionable Alerts — Drill-Down to Entry/Attachment Validation

**Feature Branch**: `018-actionable-alerts`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: GitHub issue #25 — "Actionable alerts: link each alert to the individual entry/attachment view for human validation"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Drill from an alert into the validation view (Priority: P1)

An auditor reviewing the alerts page sees an alert that concerns one or more ledger
entries. Today the alert only states an aggregate ("N entries …") with no way to inspect
the underlying evidence. The auditor wants to click the affected entry directly from the
alert and land on the entries page with the attachment-analysis detail dialog already open
for that entry — page images side-by-side with the extracted-vs-ledger values — so they can
judge in one click whether the alert is a true or false positive.

**Why this priority**: This is the core value of the feature — turning aggregate, inert
alerts into one-click investigations. Without it the auditor must manually find the entry,
defeating the purpose.

**Independent Test**: From the alerts page, click an affected-entry link on any existing
entry-level alert; verify the browser navigates to the entries page on the correct period,
the row is located/highlighted, and the attachment-analysis detail dialog opens for that
entry showing page images and extracted-vs-ledger values.

**Acceptance Scenarios**:

1. **Given** an existing entry-level alert (duplicate billing, duplicate entry, negative
   credit, large expense without attachment) on the alerts page, **When** the auditor clicks
   the link for one affected entry, **Then** the entries page opens on that entry's period
   with the attachment-analysis detail dialog auto-opened on that entry.
2. **Given** an alert that spans multiple entries (e.g. duplicate billing across sibling
   entries), **When** the auditor views the alert, **Then** each affected entry is shown as a
   separate clickable link.
3. **Given** the auditor opened the deep link, **When** they close the dialog, **Then** they
   remain on the entries page on the same period with the row still locatable.

---

### User Story 2 - See per-attachment document mismatches as their own alerts (Priority: P1)

When a downloaded attachment's extracted values disagree with the ledger — the amount does
not match, the vendor does not match, the date does not match, or the page image could not be
read — the auditor wants a dedicated, clickable alert for that mismatch on the alerts page.
Today these mismatches surface only through an internal command used by the self-improvement
loop and are invisible to a human reviewer.

**Why this priority**: Document mismatches are the most direct signal of a potential
forgery/corruption and currently have no user-facing surface at all. They must be alertable
and drillable to be actionable.

**Independent Test**: For a period with at least one attachment whose extracted amount/vendor/
date disagrees with the ledger (or whose page is unreadable), run the analysis; verify the
alerts page shows one alert per mismatch with a working link into the validation dialog for
that entry.

**Acceptance Scenarios**:

1. **Given** an attachment whose extracted amount does not match the ledger, **When** the
   period is analyzed, **Then** an alert is emitted identifying that attachment's entry, the
   kind of mismatch, the ledger value, and the extracted value.
2. **Given** an attachment whose vendor or date does not match, **When** the period is
   analyzed, **Then** a corresponding mismatch alert is emitted for each disagreeing field.
3. **Given** an attachment whose page image could not be read (page error), **When** the
   period is analyzed, **Then** an informational alert is emitted for that attachment.
4. **Given** a multi-entry shared-NF group that reconciles within tolerance, **When** the
   period is analyzed, **Then** no spurious amount-mismatch alert is emitted for the split
   (consistent with existing reconciliation behavior).

---

### User Story 3 - Re-running analysis does not pile up duplicate alerts (Priority: P2)

An operator re-runs the period analysis after re-classifying documents. They expect the alert
set for that period to be replaced cleanly — the same underlying mismatch produces the same
single alert, never accumulating duplicates across runs.

**Why this priority**: Idempotency keeps the alerts page trustworthy; duplicate alerts would
erode confidence and make true/false triage harder. It builds on US1/US2 but is a quality
guarantee rather than a new surface.

**Independent Test**: Analyze a period twice without changing the data; verify the alert count
and identities for that period are identical after the second run.

**Acceptance Scenarios**:

1. **Given** a period already analyzed once, **When** analysis is re-run with unchanged data,
   **Then** the set of alerts for that period is unchanged (no duplicates, stable identities).
2. **Given** a mismatch that was present and is later resolved in the data, **When** analysis
   is re-run, **Then** that mismatch's alert no longer appears for the period.

---

### Edge Cases

- An alert that has no single entry to point at (period/category-level: balance, subtotal,
  trend alerts) shows no entry links — these are explicitly out of scope for linking.
- An entry referenced by an alert has no attachment analysis to open (e.g. large expense
  *without* an attachment): the link still navigates to the entry on the right period and
  locates the row, but the detail dialog cannot show extracted values (there are none); the
  user still sees the entry in context.
- A shared NF that is an over-claim (siblings sum above the NF total) already emits the
  duplicate-billing alert; its affected entries must each be linkable.
- A deep link references an entry/period that the current data no longer contains (stale
  link): the entries page loads the period and the row simply isn't found — no crash.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analysis MUST emit a user-facing alert for each unresolved per-attachment
  mismatch of kind amount, vendor, or date, and for each page-error attachment.
- **FR-002**: Each per-attachment mismatch alert MUST carry, in its metadata, the affected
  entry identifier, the attachment identifier, the mismatch kind, the ledger value, and the
  extracted value.
- **FR-003**: Per-attachment mismatch alerts MUST be idempotent across re-runs — the same
  mismatch produces a single, stably-identified alert; re-analyzing a period replaces rather
  than accumulates its alerts.
- **FR-004**: The per-attachment mismatch detection used to generate alerts MUST share a single
  source of truth with the existing internal mismatch summary so the two cannot diverge.
- **FR-005**: Existing entry-level alerts (duplicate billing, duplicate entry, negative credit,
  large expense without attachment) MUST expose their affected entry identifiers (and
  attachment identifiers where applicable) to the user-facing alerts surface.
- **FR-006**: The alerts surface MUST present, for each entry-level alert, one clickable link
  per affected entry; alerts spanning multiple entries show a list of links.
- **FR-007**: Clicking an affected-entry link MUST open the entries view on that entry's period
  with the attachment-analysis detail dialog auto-opened for that entry (page images and
  extracted-vs-ledger values visible) when an analysis exists for the entry.
- **FR-008**: When an entry referenced by a link has no attachment analysis, following the link
  MUST still navigate to the correct period and locate the entry without error.
- **FR-009**: Period/category-level alerts that have no single affected entry MUST NOT render
  entry links (they remain informational).
- **FR-010**: Default severities: amount/vendor/date mismatch alerts are `warning`; page-error
  alerts are `info`.
- **FR-011**: A human resolving/dismissing an alert MUST remain independent of the
  self-improvement loop's verdict state — the two truth systems do not affect each other.
- **FR-012**: Per-attachment mismatch alerts MUST follow the existing shared-NF reconciliation
  behavior — a split that reconciles within tolerance produces no amount-mismatch alert.
- **FR-013**: Project documentation MUST be updated to describe the new alert type, the linkage
  metadata exposed to the UI, and the deep-link contract.

### Granularity & Link-Key Decisions (resolved from issue)

- **FR-014**: Per-attachment mismatch alerts are emitted at one alert per (attachment, kind)
  granularity, so each disagreeing field is individually resolvable.
- **FR-015**: The deep-link URL contract identifies the target by entry identifier (stable,
  user-facing); the period is included so the entries view can select the right period.

### Key Entities *(include if feature involves data)*

- **Alert**: A flagged condition for a period. Has a kind, severity, human-readable
  description, a stable identity, and structured metadata. For entry-level and per-attachment
  alerts, metadata carries the affected entry/attachment identifiers and (for mismatches) the
  kind plus ledger and extracted values.
- **Entry**: A single ledger line item for a period. The user-facing unit an alert links to.
- **Attachment**: The per-entry bundle of downloaded pages whose extracted values are compared
  against the entry; its analysis is what the detail dialog renders.
- **Deep link**: A reference to the entries view parameterized by period and entry identifier
  that auto-opens the attachment-analysis detail dialog for that entry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From any entry-level or per-attachment alert, an auditor can reach the page-image
  + extracted-vs-ledger validation view for a specific affected entry in a single click.
- **SC-002**: 100% of unresolved per-attachment amount/vendor/date mismatches and page-errors
  for an analyzed period appear as alerts on the alerts page.
- **SC-003**: Re-analyzing an unchanged period produces an identical alert set (zero duplicate
  alerts introduced by re-runs).
- **SC-004**: The per-attachment mismatch count shown to users equals the count produced by the
  existing internal mismatch summary for the same period (single source of truth verified).
- **SC-005**: Every entry-level alert that concerns specific entries renders at least one
  working affected-entry link; period/category-level alerts render none.
