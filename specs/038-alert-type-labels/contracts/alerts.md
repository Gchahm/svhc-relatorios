# Contract: `src/lib/alerts.ts`

## Exports

### `ALERT_TYPE_LABELS: Record<string, string>`

A frozen-by-convention object mapping each curated alert type identifier to its human-readable label
(see data-model.md). Exported so callers (and tests) can enumerate curated entries if needed.

### `alertTypeLabel(type: string): string`

Returns the human-readable label for an alert type.

**Behavior contract**:

1. If `type` is a key of `ALERT_TYPE_LABELS`, returns the curated label exactly.
2. Otherwise returns a generic transform: underscores replaced with spaces, first character of the
   result upper-cased (sentence case), e.g. `some_new_check` → `"Some new check"`.
3. `alertTypeLabel("")` returns `""`.
4. Total: never throws for any string input (including non-`snake_case`, single word, already
   spaced). A single word like `"orphan"` → `"Orphan"`; an already-spaced value is returned with its
   first character capitalized.

**Purity**: no side effects, no I/O, no React/DOM access — importable in a plain Node test.

## Consumers (must route through `alertTypeLabel`)

- `src/app/dashboard/alerts/AlertsClient.tsx` — `typeOptions` builds `{ value: v, label: alertTypeLabel(v) }`.
- `src/app/dashboard/alerts/[id]/AlertDetailClient.tsx` — Type field value `alertTypeLabel(alert.type)`.
- Any future alerts surface that renders a type label.

## Test contract (`src/lib/alerts.test.mjs`)

- Every key in `ALERT_TYPE_LABELS` maps to its curated label.
- An uncurated `snake_case` input → sentence-cased, space-separated label (no underscores).
- `""` → `""`.
- A non-snake single word → capitalized.
- No input throws.
