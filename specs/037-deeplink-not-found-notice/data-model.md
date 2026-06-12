# Data Model: Entries deep-link not-found notice

No persisted entities are added or changed — this is a client-side view change (A6). The
"model" here is the in-memory client state and the deep-link resolution value object.

## Existing entities (read-only, unchanged)

- **Entry** (`src/app/dashboard/entries/types.ts`): `{ id: string (UUID), date, description,
  amount, movementType, period, category, subcategory, vendor, unitCode, ... }`. The lookup
  target. `id` is the persisted text UUID.
- **AttachmentAnalysisRow**: one analysis per entry (via `analysisByEntry` map). Drives whether
  the success path opens the detail dialog.

## New client state (in `EntriesClient`)

- **deepLinkNotice**: `DeepLinkNotice | null`
  - `DeepLinkNotice = { kind: "not-found" | "invalid"; entryId: string; period: string }`
  - Set when resolution is terminal-and-unfound (`not-found` or `invalid`); `null` otherwise.
  - Cleared on: user dismiss, manual period change, manual filter change (FR-009).

(Existing state reused: `highlightedEntryId`, `selectedAnalysis`, `deepLinkHandledRef`,
`selectedPeriod`, and the four filter states.)

## Deep-link resolution value object (pure, in `deepLink.ts`)

`resolveDeepLink(input)` → `DeepLinkResolution`, a discriminated union:

| `outcome`                | Meaning                                                        | Effect applies |
|--------------------------|----------------------------------------------------------------|----------------|
| `"invalid"`              | `entryId` fails UUID-shape validation                          | show invalid notice; stamp consumed; strip URL |
| `"found"` + `index`      | entry present in `filtered` at `index`                         | scroll/highlight; open dialog if analysis; stamp consumed; strip URL |
| `"recovered-from-filter"`| entry absent from `filtered` but present in unfiltered `entries` AND at least one filter is active | clear all filters; do NOT stamp consumed (re-runs to `found`) |
| `"not-found"`            | entry absent from unfiltered `entries` (and no recovery possible) | show not-found notice; stamp consumed; strip URL |

### Input

```ts
interface ResolveInput {
    entryId: string;          // raw `entry` param (already non-empty when effect runs)
    hasActiveFilter: boolean; // any of subcategory/search/docType/matchStatus active
    presentUnfiltered: boolean; // entryId exists in the period's unfiltered entries
    filteredIndex: number;    // index of entryId in `filtered`, or -1
}
```

### Decision order (must be exact)

1. If `!isValidEntryId(entryId)` → `invalid`.
2. Else if `filteredIndex >= 0` → `found` (carry `filteredIndex`).
3. Else if `presentUnfiltered && hasActiveFilter` → `recovered-from-filter`.
4. Else → `not-found`.

Order matters: validity first (never look up junk); a row already visible is `found` even if a
filter is active (no need to clear); recovery only when the row exists unfiltered AND a filter
is the reason it's hidden (so an absent row with stray filters still resolves `not-found`,
FR-005). Once filters are cleared, `hasActiveFilter` is false, so step 3 cannot re-fire — the
re-run lands on `found` (step 2) or `not-found` (step 4); no recovery loop (Decision 4).

## Validation rules

- **isValidEntryId(s)**: `s` matches `^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`
  case-insensitive. (UUID shape; tolerant of det_id non-RFC4322 version bits — Decision 2.)
- **shortenEntryId(s)**: returns first 8 chars + `…` when `s.length > 8`, else `s` (A5).
