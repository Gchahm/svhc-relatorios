# Contract: entries deep-link view-state — `src/app/dashboard/entries/deeplinkView.ts`

Pure layer over the existing `resolveDeepLink` (unchanged). Maps a resolved deep link to the
view-state the entries client applies.

```ts
import { resolveDeepLink } from "./deepLink";
import type { DeepCatalogKey } from "@/lib/i18n/catalog";

export interface DeepLinkViewInput {
    entryId: string;            // raw ?entry= param
    paramPeriod: string | null; // raw ?period= param
    selectedPeriod: string | null;
    hasActiveFilter: boolean;
    presentUnfiltered: boolean;
    filteredIndex: number;      // index in the filtered list, or -1
    hasAnalysis: boolean;       // an analysis exists for this entry
}

export interface DeepLinkView {
    selectPeriod?: string;          // when paramPeriod differs from selectedPeriod
    highlightIndex?: number;        // row to scroll/highlight (found case)
    openDialog: boolean;            // auto-open the analysis dialog
    clearFilters?: boolean;         // recovered-from-filter transitional step
    noticeKey?: DeepCatalogKey;     // notice.* key (invalid / not-found), else undefined
}

export function deepLinkView(input: DeepLinkViewInput): DeepLinkView;
```

`noticeKey` resolves to the localized text via `catalog["pt-BR"].notice.*` in the UI.

## Pinned by `deeplinkView.test.mjs`
- **present + analysis** (`resolveDeepLink`→found): `{ highlightIndex, openDialog: true }`, no
  `noticeKey`.
- **present, no analysis**: `{ highlightIndex, openDialog: false }`, no `noticeKey`.
- **absent** (→not-found): `{ openDialog: false, noticeKey: <notice.deeplink_not_found_*> }`, no
  highlight.
- **invalid id** (→invalid): `{ openDialog: false, noticeKey: <notice.deeplink_invalid> }`, no
  lookup/highlight.
- **recovered-from-filter**: `{ clearFilters: true, openDialog: false }`, no notice.
- **paramPeriod !== selectedPeriod** → `selectPeriod` set to `paramPeriod`.
- The localized notice text is asserted from `catalog["pt-BR"].notice.*` (the exact catalog keys
  are read from the catalog at test time, not hardcoded English).

`EntriesClient.tsx` consumes `deepLinkView` so the test exercises the real production path.
