# Contract: `deepLink.ts` pure helpers

Module: `src/app/dashboard/entries/deepLink.ts`. Pure, no React/DOM imports, so it is
unit-testable via the repo's `node --test "src/**/*.test.mjs"` runner (Node 22 strips TS types).

## `isValidEntryId(value: string): boolean`

Returns `true` iff `value` is a canonical UUID shape (case-insensitive), else `false`.

| Input                                      | Output  |
|--------------------------------------------|---------|
| `"3f1a2b3c-4d5e-6f70-8901-23456789abcd"`   | `true`  |
| `"3F1A2B3C-4D5E-6F70-8901-23456789ABCD"`   | `true`  |
| `""`                                       | `false` |
| `"not-a-uuid"`                             | `false` |
| `"3f1a2b3c4d5e6f70890123456789abcd"` (no dashes) | `false` |
| `"3f1a2b3c-4d5e-6f70-8901-23456789abc"` (short) | `false` |
| `" 3f1a2b3c-4d5e-6f70-8901-23456789abcd "` (whitespace) | `false` |

## `shortenEntryId(value: string): string`

| Input                                      | Output       |
|--------------------------------------------|--------------|
| `"3f1a2b3c-4d5e-6f70-8901-23456789abcd"`   | `"3f1a2b3c…"`|
| `"abc"`                                     | `"abc"`      |
| `""`                                        | `""`         |

## `resolveDeepLink(input: ResolveInput): DeepLinkResolution`

```ts
interface ResolveInput {
    entryId: string;
    hasActiveFilter: boolean;
    presentUnfiltered: boolean;
    filteredIndex: number;
}

type DeepLinkResolution =
    | { outcome: "invalid" }
    | { outcome: "found"; index: number }
    | { outcome: "recovered-from-filter" }
    | { outcome: "not-found" };
```

Decision order (exact): invalid → found → recovered-from-filter → not-found (see data-model).

| `entryId` valid? | `filteredIndex` | `presentUnfiltered` | `hasActiveFilter` | → `outcome`               |
|------------------|-----------------|---------------------|-------------------|---------------------------|
| no               | (any)           | (any)               | (any)             | `invalid`                 |
| yes              | `5`             | (any)               | (any)             | `found` (index 5)         |
| yes              | `-1`            | `true`              | `true`            | `recovered-from-filter`   |
| yes              | `-1`            | `true`              | `false`           | `not-found`               |
| yes              | `-1`            | `false`             | `true`            | `not-found`               |
| yes              | `-1`            | `false`             | `false`           | `not-found`               |

Properties under test:
- A visible row is `found` regardless of `hasActiveFilter` (step 2 precedes step 3).
- Recovery requires BOTH `presentUnfiltered` AND `hasActiveFilter` (FR-004/FR-005).
- A junk id never reaches a lookup outcome (`invalid` short-circuits, FR-006).
- No-recovery-loop: with `hasActiveFilter=false`, recovery is impossible, so re-running after a
  filter clear yields `found` or `not-found` only (terminal).

## Effect-side contract (in `EntriesClient`, not unit-tested — verified manually)

Given a `DeepLinkResolution`, the effect MUST:
- `invalid` → set notice `{kind:"invalid", entryId, period}`; stamp `deepLinkHandledRef`;
  strip URL params.
- `found` → `virtualizer.scrollToIndex(index, {align:"center"})`; `setHighlightedEntryId(entryId)`;
  open dialog iff `analysisByEntry.get(entryId)` exists; stamp ref; strip URL params.
- `recovered-from-filter` → reset all four filter states; do NOT stamp ref; do NOT strip URL
  (so the post-clear re-run resolves the now-visible row).
- `not-found` → set notice `{kind:"not-found", entryId, period}`; stamp ref; strip URL params.

URL stripping: `window.history.replaceState(null, "", <pathname without entry/period query>)`.
Notice cleared on: dismiss, manual `handlePeriodChange`, manual filter change (FR-009).
