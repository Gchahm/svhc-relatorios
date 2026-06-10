# Feature Specification: Derive the classification plan from D1 (remove the extract-todo.json manifest)

**Feature Branch**: `016-derive-classify-plan-from-d1`
**Created**: 2026-06-10
**Status**: Draft
**Input**: GitHub issue #21 — "Remove extract-todo.json manifest — derive the classification plan from D1 (persist attachments.content_hash)"

## Overview

The scrape → classify → analyze pipeline currently writes an ephemeral per-period
work manifest (`.cache/analysis/<period>.extract-todo.json`). It is produced by the
`docs-plan` step and consumed by both the `classify-period` skill and
`apply-extractions`. The manifest is a redundant, stale-able intermediate: almost
everything in it is already derivable from the database. The one thing that today
forces a file is the **shared-NF grouping**, which is computed by hashing page-image
bytes at plan time — work that has to be redone every run because the grouping key is
not persisted anywhere.

This feature persists that grouping key on the attachment at scrape time and turns the
plan into a database query, eliminating the manifest entirely while preserving the
exact analysis behavior (same NF groups, same reconciliation outcomes, same
`attachment_analyses` and alerts).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the pipeline without a manifest file (Priority: P1)

A maintainer (or an orchestrating agent) runs the full classification flow for a
period — classify → apply-extractions → analyze → mismatches — and it produces the same
analyses and alerts as before, without any `extract-todo.json` file being written or
read at any point.

**Why this priority**: This is the headline goal — removing the stale-able intermediate
file. The whole pipeline must keep working with the plan derived from the database.

**Independent Test**: Run the classification flow against a period that already has
attachments and images. Confirm no `*.extract-todo.json` is created in the cache, and
that the resulting `attachment_analyses` rows and alerts are equivalent to a run made
before the change.

**Acceptance Scenarios**:

1. **Given** a period whose attachments and page images exist in the database/object
   store, **When** the classification plan is requested, **Then** the list of pending
   representative attachments and their page references is produced from the database
   with no manifest file written.
2. **Given** the per-page classifications exist, **When** apply-extractions runs,
   **Then** it derives each shared-NF group (representative, members, sibling sum, group
   size) from the database and writes `attachment_analyses` identical in shape and values
   to the pre-change flow — without reading a manifest file.
3. **Given** the classification flow has completed, **When** the cache directory is
   inspected, **Then** there is no `*.extract-todo.json` file (none was written or read).

---

### User Story 2 - The grouping key is persisted at capture time (Priority: P2)

When attachments are captured (scraped, or backfilled), the system records a stable
content fingerprint for each attachment's page images so that "which attachments share
the same Nota Fiscal" is a stored fact rather than something recomputed by re-hashing
files on every plan.

**Why this priority**: Persisting the key is what makes the plan a cheap database query
and removes the need to re-materialize and re-hash images just to group them. It is the
enabling change for Story 1.

**Independent Test**: Capture an attachment whose pages are byte-identical to another
attachment's pages; confirm both record the same fingerprint, and that an attachment with
a single distinct page records a fingerprint unique to it (a singleton group of one).

**Acceptance Scenarios**:

1. **Given** the system captures an attachment with downloadable page images, **When**
   capture completes, **Then** the attachment's stored content fingerprint is populated.
2. **Given** two attachments whose page images are byte-identical, **When** both are
   captured, **Then** they record the same fingerprint (so they group together).
3. **Given** the same period is captured again, **When** capture re-runs, **Then** the
   fingerprint for unchanged page bytes is identical to the previous run (stable across
   re-capture).
4. **Given** an attachment whose page images cannot be read or has no pages, **When**
   capture completes, **Then** it has no fingerprint and is treated as its own singleton
   group (never merged with another attachment).

---

### User Story 3 - Equivalent results on existing data (Priority: P2)

For data captured before this change (whose stored fingerprint is not yet populated), the
analysis still produces the same NF groups and reconciliation outcomes as before, so the
change can ship without forcing an immediate full re-capture of historical periods.

**Why this priority**: Backward compatibility — the local and production databases already
hold attachments without the new fingerprint. Equivalence on that data is required by the
acceptance criteria.

**Independent Test**: Against a period already in the database (no stored fingerprint),
run apply-extractions and confirm the NF groups and `amount_match` reconciliation outcomes
match the pre-change behavior.

**Acceptance Scenarios**:

1. **Given** attachments whose stored fingerprint is empty but whose page images are
   available, **When** the plan and apply-extractions run, **Then** grouping falls back to
   computing the fingerprint from the available page bytes and yields the same groups as
   before.
2. **Given** such attachments have been processed once, **When** they are processed
   again, **Then** the previously-empty fingerprint has been backfilled so subsequent runs
   group purely from the stored value.

---

### Edge Cases

- **Empty / unreadable pages**: an attachment with no pages, or whose page images are
  missing from the object store, has no fingerprint and forms a singleton group keyed by
  its own id — it is never merged with a different attachment.
- **Targeted re-classification**: requesting the plan for specific attachment/entry ids
  re-plans those even when already analyzed (targeting implies re-analysis), exactly as
  today — without any manifest.
- **Filtered siblings**: when a filter (min-amount, limit, id scope) drops some siblings of
  a shared-NF group, the full group's sibling sum and size are still used for
  reconciliation, exactly as today.
- **Partial classification**: a representative page whose per-page classification is missing
  is recorded as a per-page error and does not abort the attachment.
- **Stale manifest left on disk**: a leftover `*.extract-todo.json` from a prior version
  must have no effect (the code neither reads nor writes it).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist a per-attachment content fingerprint of the
  attachment's page images, populated when attachments are captured (both the primary
  capture flow and the backfill flow that fills in previously-missing images).
- **FR-002**: The content fingerprint MUST be stable across re-capture (byte-identical
  pages always produce the same fingerprint) and MUST match the grouping key the pipeline
  used previously (byte-identical page sets that grouped together before continue to group
  together).
- **FR-003**: The system MUST determine shared-NF groups, the representative attachment per
  group, each group's sibling sum, and each group's size from the database (using the
  stored fingerprint), without writing or reading a manifest file.
- **FR-004**: An attachment with no fingerprint (no pages, unreadable pages, or pre-change
  data) MUST form a singleton group keyed by its own id and MUST never be merged with a
  different attachment.
- **FR-005**: The classification plan (the list of pending representative attachments and
  their page references for the classify step) MUST be produced from the database. "Pending"
  MUST keep its current meaning — an attachment with no existing analysis is pending unless
  re-analysis is explicitly requested.
- **FR-006**: The apply-extractions step MUST derive each group's representative, member
  list, per-member context (attachment id, entry id, entry amount, vendor name), sibling
  sum, and group size from the database, and produce `attachment_analyses` (and flattened
  per-page records) identical in shape to the previous flow.
- **FR-007**: No code path MUST write or read any `*.extract-todo.json` file.
- **FR-008**: The system MUST continue to materialize page images from the object store into
  the local cache so the vision step can read them and (for pre-change data) the fingerprint
  can be computed; this step is retained unchanged in purpose.
- **FR-009**: For attachments whose stored fingerprint is empty but whose page images are
  available, the system MUST fall back to computing the fingerprint from the available page
  bytes so grouping remains equivalent, and SHOULD backfill the stored fingerprint so
  subsequent runs read it from the database.
- **FR-010**: A schema migration that adds the content-fingerprint column MUST be generated
  and committed.
- **FR-011**: The end-to-end flow (capture → classify → apply-extractions → analyze →
  mismatches) MUST yield `attachment_analyses` and alerts equivalent to the pre-change flow
  for the same inputs.
- **FR-012**: The `classify-period` skill and `analyze-docs` agent instructions MUST be
  updated to reflect the database-derived plan (no manifest), and the affected docs
  (`scripts/README.md`, `CLAUDE.md`, `scripts/pipeline-flow.md`) MUST be updated.

### Key Entities *(include if feature involves data)*

- **Attachment**: the per-entry multi-page bundle downloaded from the portal. Gains a stored
  **content fingerprint** attribute — a stable hash over its page-image bytes that identifies
  which attachments carry byte-identical pages (the same Nota Fiscal). Nullable: empty when
  pages are absent/unreadable or for data captured before this feature.
- **Shared-NF group**: the set of attachments sharing one content fingerprint. Has a
  representative (highest-amount member), a member list with per-member ledger context, a
  sibling sum (sum of member entry amounts over the full group), and a size. Derived, not
  stored — computed from attachments grouped by fingerprint joined to their entries/vendors.
- **Classification plan**: the derived, in-memory list of pending representative attachments
  and their page references that the classify step consumes. Replaces the manifest file.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a full classification run, zero `*.extract-todo.json` files exist in the
  cache, and no code references that filename.
- **SC-002**: Every attachment captured after the change has a populated content fingerprint;
  byte-identical page sets share one fingerprint and singletons get a unique one.
- **SC-003**: For a given period, the `attachment_analyses` rows and alerts produced after the
  change are equivalent (same groups, same amount/vendor/date match outcomes, same
  duplicate-billing alerts) to those produced before the change.
- **SC-004**: Running the plan no longer re-hashes page-image files when the stored
  fingerprint is present (grouping reads the database); re-hashing occurs only as the
  documented fallback for not-yet-backfilled data.
- **SC-005**: A schema migration adding the fingerprint column is present and applies cleanly
  locally.

## Assumptions

- **No new classification-status column.** The issue flags an optional
  `classification_status` / `classified_at` column as a "decision point." This feature does
  **not** add it: "pending = no `attachment_analyses` row" already works, and targeted
  re-classification already works by threading `--attachment-id`/`--entry-id` through the
  skills/agents. Adding a status column is out of scope here and can be revisited
  independently.
- **Fingerprint algorithm reuses today's content hash.** To guarantee identical grouping,
  the persisted fingerprint uses the same algorithm the pipeline already uses
  (`nf_groups.content_hash`: a length-delimited per-page byte hash in page order). The pure
  hashing helper is shared between the capture (scraper) and analysis subsystems via the
  existing `scripts/common` shared leaf, preserving their decoupling (both depend on
  `common`, not on each other).
- **Backfill of historical data is transitional, not a blocking migration step.** Existing
  rows keep working via the FR-009 fallback (compute-from-cache) and are backfilled lazily as
  they are processed; a full re-capture is not required to ship.
- **Out of scope**: removing the per-page `.classify.json` seam (tracked as a separate
  follow-on issue). This feature keeps the file-based classify→apply seam exactly as-is and
  only removes the *plan* manifest.
- **Object-key derivation and image materialization are unchanged** in mechanism; only the
  plan's source (database instead of a file) and the grouping key's source (stored column
  instead of re-hashing) change.
