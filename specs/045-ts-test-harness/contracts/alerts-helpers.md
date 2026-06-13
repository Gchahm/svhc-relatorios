# Contract: alerts helpers — `src/app/dashboard/alerts/alerts-helpers.ts`

Moved verbatim out of `alerts.tsx`; `alerts.tsx` imports them (public surface unchanged).

```ts
export function affectedEntryIds(metadata: string | null): string[];
export function entryHref(period: string, entryId: string): string;
export function referencedDocumentId(metadata: string | null): string | null;
```

## Pinned by `alerts-helpers.test.mjs`
- `affectedEntryIds('{"entry_id":"<uuid>"}')` → `["<uuid>"]`.
- `affectedEntryIds('{"entry_ids":["a","b"]}')` → `["a","b"]` (array form honored).
- `affectedEntryIds('{"entry_ids":["a",1,null,"b"]}')` → `["a","b"]` (non-strings dropped).
- `affectedEntryIds(null)` / `affectedEntryIds("{ not json")` / `affectedEntryIds("{}")` → `[]`,
  never throws.
- `entryHref("2025-12", "id with space")` → `/dashboard/entries?period=2025-12&entry=id%20with%20space`.
- `referencedDocumentId('{"document_id":"d1"}')` → `"d1"`; null / malformed / absent → `null`.
