# Research: Correct `Entry.id` client type to UUID string

No open NEEDS CLARIFICATION items. The two design decisions are recorded below.

## Decision 1: Type `Entry.id` as `string` and remove call-site coercion

- **Decision**: Change `interface Entry { id: number; … }` to `id: string` and delete every
  `String(e.id)` / `String(entry.id)` wrapper.
- **Evidence (read from source)**: `src/db/fiscal.schema.ts` defines `entries.id` as a `text`
  primary key populated by a UUID generator; `GET /api/entries` selects that column unchanged
  and returns it as JSON (string). The client's `analysisByEntry` map is keyed by
  `AttachmentAnalysisRow.entryId` (already typed `string`) and the `attachment-analyses` API
  returns `entryId` as a string, so the map and the entry id are the same string space — the
  `String(e.id)` calls are pure no-ops at runtime today.
- **Rationale**: The type currently lies; a numeric assumption would compile and fail
  silently. The deep-link match (`String(e.id) === deepLinkEntry`, where `deepLinkEntry` is a
  `string` from `searchParams`) is the exact path most exposed.
- **Alternatives considered**: (a) Keep `number` and add a runtime `Number()` parse — wrong,
  the data is not numeric. (b) `string | number` union — keeps the lie and forces coercion
  forever. Rejected; the source is unambiguously a string.

## Decision 2: Extract shared row types into `types.ts` (A-003)

- **Decision**: Move `Entry` and `AttachmentAnalysisRow` into a new
  `src/app/dashboard/entries/types.ts`; re-point the two cross-module consumers
  (`AttachmentAnalysisDetailDialog.tsx`, `alerts/[id]/AlertDetailClient.tsx`) to import from
  it. `EntriesClient.tsx` imports its own row types from the new module too.
- **Evidence**: `AlertDetailClient.tsx` imports `AttachmentAnalysisRow` from
  `"../../entries/EntriesClient"` and `AttachmentAnalysisDetailDialog.tsx` from
  `"./EntriesClient"` — i.e. another feature's *component* module is imported solely for a
  type, which the issue explicitly flags.
- **Rationale**: Importing a `"use client"` component module only for a `type` couples the
  alerts feature to the entries component. `import type` from a types-only module removes the
  coupling and any risk of pulling the component into another feature's module graph.
- **Risk / fallback (per A-003)**: If the move surfaces an unexpected build/type issue, drop
  it and keep types in `EntriesClient.tsx` (re-exporting `Entry` if needed), leaving
  FR-001–FR-005 as the irreducible fix. `AttachmentAnalysisRow` is already `export`ed, so the
  move is mechanical.

## Verification approach

No new test framework (none configured). Verification = `pnpm lint` + type-check via build +
manual UI check (`verify` skill): entries page loads, an alert deep link highlights the right
row and opens its analysis dialog, and a doc-type filter still narrows rows.
