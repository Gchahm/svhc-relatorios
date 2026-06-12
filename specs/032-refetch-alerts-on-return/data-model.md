# Data Model: Refetch alerts list after resolve/reopen on the detail page

**N/A — no data model change.**

This feature is a client-side data-freshness fix. It introduces no new persisted entity, no schema
change, and no migration. The only entity involved is the existing **Alert** (table `alerts`),
read unchanged via `GET /api/alerts`:

- `id`, `type`, `severity`, `title`, `description`, `referencePeriod`, `resolved` (Active/Resolved
  status), `resolvedAt`, `notes`, `metadata` — all already returned by the endpoint and consumed by
  `AlertsClient`'s `AlertRow` interface.

The fix changes only **when** the client re-reads these rows, not their shape.
