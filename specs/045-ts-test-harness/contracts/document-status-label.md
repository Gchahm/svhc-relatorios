# Contract: document status label + alert type label (localized)

## `src/lib/documents-label.ts`
```ts
import type { DocumentStatus } from "./documents";
import type { DeepCatalogKey } from "./i18n/catalog";
export function documentStatusLabelKey(status: DocumentStatus): DeepCatalogKey;
// over→"status.over", within→"status.within", under→"status.under", unknown→"status.unknown"
```
`DocumentsClient`/`StatusBadge` render the badge label via `t(documentStatusLabelKey(status))`.

### Pinned by `documents-label.test.mjs`
- For each status, `catalog["pt-BR"].status[<status>]` equals the rendered label
  (over→"Acima", within→"Conforme", under→"Abaixo", unknown→"Desconhecido"), asserted via the
  key the function returns — no English literal.
- `documents.test.mjs` (existing) retains the status-math contract; not duplicated here.

## `src/lib/i18n/alert-type-label.ts`
```ts
import type { SupportedLocale } from "./catalog";
export function alertTypeLabelFor(type: string, locale: SupportedLocale): string;
```
Catalog `alert.types.<type>` when present; else humanized `snake_case → Sentence case`; `""`→`""`;
never raw snake_case. `useAlertTypeLabel` (in `client.tsx`) is refactored to call this.

### Pinned by `alert-type-label.test.mjs`
- Every `type` in `catalog["pt-BR"].alert.types` → its pt-BR catalog value (asserted from catalog).
- An unknown type (e.g. `"some_future_check"`) → `"Some future check"`, contains no `_`.
- `""` → `""`; `assert.doesNotThrow` over a battery of inputs; result always a string.
