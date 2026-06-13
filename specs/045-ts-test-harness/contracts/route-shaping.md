# Contract: route row→response shaping

Each shaping module is a pure `.ts` the route imports; the route keeps the Cloudflare/Drizzle
plumbing (`initAuth`, `getDb`, the `db.select(...)` query) and calls the shaper on the rows.

## `src/app/api/alerts/shape.ts`
```ts
export type AlertRow = { id; type; severity; title; description; referencePeriod;
    resolved; resolvedAt; notes; metadata };
export function shapeAlertRow(row: AlertRow): AlertRow; // identity projection (stable key set)
```
**Pinned**: output preserves exactly the documented keys (no extra/missing); array map preserves order.

## `src/app/api/documents/shape.ts`
```ts
import { documentStatus, type DocumentStatus } from "@/lib/documents";
export type DocumentRow = { id; documentNumber; issuerCnpj; issuerName; documentType;
    totalValue: number | null; linkedCount: number; sumEntries: number };
export function shapeDocumentRow(row: DocumentRow): DocumentRow & { status: DocumentStatus };
```
**Pinned**: `status === documentStatus(sumEntries, totalValue)`; over/within/under/unknown cases
(sum>total over tolerance → "over"; within tolerance → "within"; null total → "unknown"); all
input fields preserved.

## `src/app/api/attachment-analyses/shape.ts`
```ts
export function attachmentAnalysesPeriodScoped(period: string | null): boolean; // truthy non-empty
export const ATTACHMENT_ANALYSIS_RESPONSE_FIELDS: readonly string[]; // the projected column names
```
**Pinned**: `attachmentAnalysesPeriodScoped("2025-12") === true`; `(null)` / `("")` → `false`
(route applies `where(period ? eq(...) : undefined)` consistently); the response field set matches
the documented projection.

> Note: shaping functions are pure and contain no `getDb`/`initAuth`/Cloudflare import, so the
> tests never stand up the Workers runtime (spec FR-007 / Constitution II).
