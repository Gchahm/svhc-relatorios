# Data Model: Correct `Entry.id` client type to UUID string

No persisted data model change. This documents only the **client-side TypeScript row types**
being corrected/relocated. The Cloudflare D1 schema, migrations, and API contracts are
untouched.

## Entry (client row type)

Rendered ledger line in the entries client. Source: `GET /api/entries?period=<YYYY-MM>`.

| Field        | Type             | Change                                   |
|--------------|------------------|------------------------------------------|
| `id`         | `string`         | **CHANGED** from `number` → `string` (text UUID, matches `entries.id`) |
| `date`       | `string`         | unchanged                                |
| `description`| `string`         | unchanged                                |
| `amount`     | `number`         | unchanged                                |
| `movementType`| `string`        | unchanged                                |
| `sourceUrl`  | `string`         | unchanged                                |
| `period`     | `string`         | unchanged                                |
| `category`   | `string`         | unchanged                                |
| `subcategory`| `string`         | unchanged                                |
| `vendor`     | `string \| null` | unchanged                                |
| `unitCode`   | `string \| null` | unchanged                                |

**Relationships**: keyed to `AttachmentAnalysisRow` via `Entry.id === AttachmentAnalysisRow.entryId`
(both `string`). The deep-link param `entry` (a `string`) matches against `Entry.id` directly.

## AttachmentAnalysisRow (client row type)

Unchanged in shape; **relocated** from `EntriesClient.tsx` to `entries/types.ts`. `entryId`
remains `string`. Consumed by `AttachmentAnalysisDetailDialog` and `AlertDetailClient`.

## Location move

| Type                  | Old home (component module) | New home (types module)            |
|-----------------------|-----------------------------|------------------------------------|
| `Entry`               | `entries/EntriesClient.tsx` | `entries/types.ts`                 |
| `AttachmentAnalysisRow`| `entries/EntriesClient.tsx`| `entries/types.ts`                 |
