# Phase 1 Data Model: Analysis-owned attachment state table

## New entity: `attachment_state` (analysis-owned)

Per-attachment classification state. Created/updated by the analysis pipeline only.
The mirror table `attachments` is no longer written by analysis.

| Column          | Type    | Constraints                                             | Meaning |
|-----------------|---------|---------------------------------------------------------|---------|
| `attachment_id` | TEXT    | PRIMARY KEY, REFERENCES `attachments(id)`               | The attachment this state belongs to (1:1). |
| `classified_at` | INTEGER | nullable (epoch ms; Drizzle `timestamp_ms`)             | When the attachment's roll-up analysis was last written. NULL or **no row** ⇒ **pending**. |

- **Pending semantics**: an attachment is pending iff it has no `attachment_state` row OR its row's
  `classified_at IS NULL`. Freshly scraped attachments have no state row and are therefore pending
  (FR-003).
- **Lifecycle independence**: the row's existence is independent of the `attachments` row being
  replaced by a re-scrape (the scraper never touches `attachment_state`). An orphaned state row
  (its attachment removed) simply has nothing to join to and is ignored by the plan (edge case).
- **No new index needed**: lookups are by PK (`attachment_id`); the plan reads via LEFT JOIN from
  `attachments`.

### Drizzle definition (in `src/db/fiscal.schema.ts`)

```ts
export const attachmentState = sqliteTable("attachment_state", {
    attachmentId: text("attachment_id")
        .primaryKey()
        .references(() => attachments.id),
    // Analysis-owned classification stamp. Moved off the mirror table `attachments`
    // (BUG-002 / issue #33): the pipeline writes here; the scraper never does.
    // NULL or no row ⇒ pending (re-queued by mark-pending → classified_at = NULL).
    classifiedAt: integer("classified_at", { mode: "timestamp_ms" }),
});
```

## Modified entity: `attachments` (mirror) — `classified_at` removed

| Column          | Change  | Notes |
|-----------------|---------|-------|
| `classified_at` | REMOVED | Moved to `attachment_state`. Values copied in the migration before drop. |
| `content_hash`  | UNCHANGED | Stays here; scraper-owned (written at scrape time + by the scraper's image-download path). Analysis no longer backfills it. |

After this change, every column on `attachments` is scraper-written → the table is again an
exact mirror of the brcondos portal (US1 / SC-001).

## State transitions (classification)

```
            scrape (no state row)
                  │
                  ▼
            [ PENDING ]  ◀─────────────────┐
                  │                         │ mark-pending
                  │ apply-extractions       │ (classified_at = NULL)
                  │ writes roll-up analysis │
                  ▼                         │
            [ CLASSIFIED ] ─────────────────┘
            (attachment_state.classified_at = <now>)
```

- The PENDING → CLASSIFIED transition is **atomic** with the analysis-rows insert (one D1 batch);
  a failed insert leaves the attachment PENDING (FR-004, no stamped-but-empty).
- CLASSIFIED → PENDING is the explicit re-queue (`mark-pending`).

## Migration data flow (one file, `drizzle/0012_*.sql`)

1. `CREATE TABLE attachment_state (attachment_id PK → attachments.id, classified_at INTEGER)`.
2. `INSERT INTO attachment_state (attachment_id, classified_at)
    SELECT id, classified_at FROM attachments WHERE classified_at IS NOT NULL;` (SC-003).
3. Drop `attachments.classified_at` (SQLite table rebuild as emitted by drizzle-kit). `content_hash`
   and all other columns are preserved (SC-004).
