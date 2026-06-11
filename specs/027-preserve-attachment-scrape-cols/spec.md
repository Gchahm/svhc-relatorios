# Feature Specification: Preserve scraper-owned attachment columns across re-scrapes

**Feature Branch**: `027-preserve-attachment-scrape-cols`
**Created**: 2026-06-11
**Status**: Draft
**Input**: User description: "Scraper re-scrape must preserve existing attachment file_path and content_hash instead of nulling them via INSERT OR REPLACE (BUG-001)"

## Context & Background

This addresses GitHub issue #32 (BUG-001). Re-running the scraper on a period that has already
been scraped silently destroys data on the `attachments` rows for that period. The scraper writes
each attachment row via an `INSERT OR REPLACE` upsert, and `INSERT OR REPLACE` first deletes the
existing row, then inserts the new one — so any column **not present** in the new row dict reverts
to its schema default (NULL).

A related bug, BUG-002 (issue #33), already moved the classification-state column `classified_at`
off the mirror table `attachments` into the analysis-owned `attachment_state` table. Because the
scraper never writes `attachment_state`, re-scraping no longer clobbers classification state — that
half of BUG-001 is **already resolved**. The damage that **remains** is to the two scraper-owned
columns that carry expensive-to-recompute linkage:

- **`file_path`** — the `;`-joined R2 object-key tokens (`<period>/<basename>`) that link the
  attachment to its page images already uploaded to R2.
- **`content_hash`** — the shared-Nota-Fiscal grouping key (a content hash over the page-image
  bytes) that lets the analysis pipeline group byte-identical attachments.

Both are populated only when page images are downloaded in the **same** scrape run (the scraper
emits the new attachment row with `file_path=NULL, content_hash=NULL` and fills them in-run only on
a successful download). Therefore a routine "refresh this period" run that omits the download step
(or hits a download failure) overwrites both back to NULL even though the page images still exist in
R2 and nothing about the attachment actually changed.

These columns are legitimately **scraper-owned** (the scraper is their sole writer), so the fix is
not to move them to another table; it is to make the scraper's upsert **preserve** the existing
values when the current run has produced nothing newer for them.

## Clarifications

### Session 2026-06-11

- Q: Where should the preservation happen — at the generic SQL upsert layer (change `INSERT OR
  REPLACE` semantics for every table) or in the scraper's attachment write path only? → A: In the
  scraper's attachment write path only (read existing `file_path`/`content_hash` from D1 for the
  period and carry them into the freshly scraped row when the run produced NULL). This keeps the
  shared `INSERT OR REPLACE` generator untouched, so no other table's write semantics change, and
  confines the blast radius to the one buggy path. (Recorded as an assumption; unattended run.)
- Q: Should preservation also guard against an existing NON-NULL value being overwritten by a NULL
  from a failed download mid-run, when other attachments in the same period downloaded fine? → A:
  Yes — preservation is decided per attachment id from the existing D1 value, independent of whether
  other attachments in the run downloaded successfully (FR-004).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Refresh a period without re-downloading images (Priority: P1)

An operator re-scrapes a single already-classified period to pick up corrected portal ledger data,
running the scraper **without** the image-download step (the common case, since the images rarely
change and downloading is slow). After the run, the attachments in that period must still resolve
their page images and still group correctly for analysis — exactly as they did before the re-scrape.

**Why this priority**: This is the exact routine operation that triggers the silent data loss today;
fixing it removes the critical bug and restores trust in re-scraping.

**Independent Test**: Seed a period's attachments with non-NULL `file_path` and `content_hash`
(simulating a prior download), re-scrape the same period without the download step, then confirm the
`file_path` and `content_hash` values are unchanged for attachments that still exist.

**Acceptance Scenarios**:

1. **Given** an attachment already has non-NULL `file_path` and `content_hash` in the database,
   **When** the period is re-scraped without downloading images,
   **Then** that attachment's `file_path` and `content_hash` retain their existing values (not NULL).
2. **Given** an attachment already has non-NULL `file_path` and `content_hash`,
   **When** the period is re-scraped and the image download for that attachment fails,
   **Then** that attachment's `file_path` and `content_hash` retain their existing values (not NULL).
3. **Given** a period that has been classified (rows exist in `attachment_state`),
   **When** the period is re-scraped,
   **Then** the classification state in `attachment_state` is untouched (already true after issue #33;
   asserted here as a regression guard).

---

### User Story 2 - Re-download supplies fresh values (Priority: P2)

An operator re-scrapes a period **with** the image-download step enabled (e.g. the portal replaced a
document). The scrape produces fresh `file_path`/`content_hash` values for the attachments it
successfully downloaded, and those fresh values must take effect.

**Why this priority**: Preserving old values must not block legitimate updates — the scraper must
still be able to overwrite the linkage when it actually has a newer one.

**Independent Test**: Seed an attachment with old `file_path`/`content_hash`, re-scrape the period
with a successful download that produces different values, and confirm the new values win.

**Acceptance Scenarios**:

1. **Given** an attachment with existing `file_path`/`content_hash`,
   **When** the period is re-scraped with a successful image download that yields new values,
   **Then** the attachment's `file_path` and `content_hash` are updated to the new values.

---

### User Story 3 - First scrape of a fresh period is unaffected (Priority: P3)

The first scrape of a period that has never been scraped behaves exactly as today: attachments are
created with `file_path`/`content_hash` either NULL (no download) or populated (download succeeded).

**Why this priority**: The preservation logic must be a no-op when there is nothing pre-existing to
preserve, so first-scrape behavior is guaranteed unchanged.

**Independent Test**: Scrape a period with no pre-existing rows and confirm attachment rows are
created with the same values as before this change.

**Acceptance Scenarios**:

1. **Given** a period with no existing attachment rows,
   **When** it is scraped for the first time without downloading images,
   **Then** attachments are created with NULL `file_path` and NULL `content_hash`.
2. **Given** a period with no existing attachment rows,
   **When** it is scraped with a successful download,
   **Then** attachments are created with populated `file_path` and `content_hash`.

---

### Edge Cases

- **Attachment removed from the portal on re-scrape**: An attachment id present before but absent
  from the new scrape is simply not written by the new run; this feature does not delete it (mirror
  drift / orphan removal is the separate concern tracked by BUG-004 / issue #35) and does not
  resurrect it. No preservation applies because no row is written.
- **New attachment appears on re-scrape**: An attachment id not previously present is created fresh;
  there is nothing to preserve, so it follows first-scrape behavior.
- **Existing row has NULL values**: If the prior `file_path`/`content_hash` were already NULL and the
  current run also produces NULL, the result stays NULL (preservation of NULL is a no-op).
- **Partial download within a period**: Some attachments download successfully (fresh values) and
  others fail (preserve existing) within the same run — preservation is decided per attachment, not
  per period.
- **Other scraper-owned attachment columns**: `entry_id` and `external_document_id` are always
  produced fresh by every scrape (they are part of the portal mirror), so they are always written and
  need no preservation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the scraper writes an attachment row for a period that already has a row with the
  same attachment id, the system MUST preserve the existing `file_path` value if the current scrape
  run produced no `file_path` for that attachment (i.e. did not successfully download its images).
- **FR-002**: When the scraper writes an attachment row that already exists, the system MUST preserve
  the existing `content_hash` value if the current scrape run produced no `content_hash` for that
  attachment.
- **FR-003**: When the current scrape run DOES produce a `file_path`/`content_hash` for an attachment
  (a successful in-run download), the system MUST write those fresh values, overwriting any prior
  values.
- **FR-004**: The preservation MUST be decided per attachment id, so a partially-downloaded period
  preserves the existing values for the un-downloaded attachments while updating the downloaded ones.
- **FR-005**: The fix MUST NOT alter, write to, or depend on the analysis-owned `attachment_state`
  table; classification state remains untouched by any scrape (regression guard for issue #33).
- **FR-006**: The fix MUST NOT change the values written for the always-produced mirror columns
  (`id`, `entry_id`, `external_document_id`) — those continue to reflect the latest portal data.
- **FR-007**: First-scrape behavior (no pre-existing row) MUST be unchanged: attachments are created
  with NULL `file_path`/`content_hash` when not downloaded, populated when downloaded.
- **FR-008**: The `attachments` table MUST remain an exact mirror of the portal data plus its
  scraper-owned linkage columns; the fix MUST NOT introduce any analysis-owned column onto it.

### Key Entities *(include if feature involves data)*

- **Attachment**: The per-entry bundle of page images downloaded from the portal. Scraper-owned
  columns: `id`, `entry_id`, `external_document_id`, `file_path` (R2 object-key tokens),
  `content_hash` (shared-NF grouping key). The first three are always produced by every scrape;
  the last two are produced only on a successful in-run image download and are the values this
  feature preserves when absent.
- **Attachment State** (`attachment_state`): The analysis-owned classification-state table keyed by
  attachment id (added by issue #33). Out of scope here except as a regression guard — no scrape ever
  touches it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After re-scraping an already-classified period without downloading images, 100% of the
  attachments that existed before retain their prior `file_path` and `content_hash` values (zero
  reset to NULL).
- **SC-002**: After re-scraping a period with a successful image download, attachments that were
  downloaded reflect the freshly computed `file_path`/`content_hash` (updates are not blocked).
- **SC-003**: After any re-scrape, the classification state recorded in `attachment_state` for the
  period's attachments is identical to before the re-scrape (no re-classification is triggered by a
  refresh).
- **SC-004**: A first scrape of a never-scraped period produces attachment rows identical to the
  pre-fix behavior (no regression for new periods).

## Assumptions

- The two scraper-owned linkage columns that need preservation are exactly `file_path` and
  `content_hash`. `classified_at` already moved to `attachment_state` (issue #33) and is not on
  `attachments`, so it is not in scope.
- "Produced nothing newer" is interpreted as: the in-run download did not yield a value for that
  attachment, leaving the scraped row's `file_path`/`content_hash` as their initial NULL. A NULL in
  the freshly scraped row is the signal to preserve; a non-NULL is the signal to overwrite.
- Removing rows for attachments deleted on the portal (mirror drift) is explicitly out of scope and
  tracked separately by BUG-004 (issue #35). This feature only governs rows the scrape writes.
- The fix is confined to the scraper / D1-write path (the attachment upsert); it does not change the
  analysis pipeline, the schema, the frontend, or the portal scraping logic.
- The `attachments.entry_id` unique constraint and the deterministic attachment id mean an
  attachment's identity is stable across re-scrapes, so matching the existing row by id is reliable.
- The scraper already queries D1 for existing periods at the start of a run, so reading existing
  attachment column values from D1 during a scrape is consistent with the established access pattern.
