# Data Model: test "entities" (extracted module contracts)

This is a test-only feature; there is **no D1 schema or migration**. The "entities" below are the
pure-logic contracts the tests pin and the coverage-baseline record.

## E1. Auth decision (`src/lib/auth-access.ts`)

- `ALLOWED_ROLES: readonly string[]` — `["admin", "member"]` (single source; routes import it).
- `UNAUTHORIZED_STATUS: number` — `403` (the code the routes return; tests assert routes use it).
- `isAuthorized(session: SessionLike | null | undefined): boolean` —
  `true` iff session exists AND `session.user.role` is in `ALLOWED_ROLES`; `false` otherwise.
  `SessionLike` is a minimal shape `{ user?: { role?: string } }` (no Cloudflare/better-auth import).
- **Pinned**: deny for `null`/`undefined`/missing-role/disallowed-role; allow for each allowed role.

## E2. Alerts helpers (`src/app/dashboard/alerts/alerts-helpers.ts`)

Moved verbatim out of `alerts.tsx` (behavior-preserving; `alerts.tsx` imports them):
- `affectedEntryIds(metadata: string | null): string[]` — `entry_ids[]` (string-filtered) wins,
  else single `entry_id`, else `[]`; malformed/null → `[]`, never throws.
- `entryHref(period: string, entryId: string): string` — `/dashboard/entries?period=…&entry=…`
  with both params URL-encoded.
- `referencedDocumentId(metadata: string | null): string | null` — `document_id` string or `null`.
- **Pinned**: single id, array, mixed-type array (non-strings dropped), malformed, null, encoding.

## E3. Alert type label (`src/lib/i18n/alert-type-label.ts`)

Extracted from `useAlertTypeLabel` (`src/lib/i18n/client.tsx`) as a pure, locale-aware function:
- `alertTypeLabelFor(type: string, locale: SupportedLocale): string` — catalog `alert.types.<type>`
  when present, else humanized `snake_case → Sentence case`; `""` → `""`; never raw snake_case.
- `client.tsx`'s `useAlertTypeLabel` is refactored to call this (no behavior change).
- **Pinned**: every curated catalog type → its pt-BR label; an unknown type → no-underscore
  fallback; empty → empty; total/never-throws.

## E4. Document status label (`src/lib/documents-label.ts`)

- `documentStatusLabelKey(status: DocumentStatus): DeepCatalogKey` — maps `over/within/under/unknown`
  to `status.over/within/under/unknown`. (`documentStatus` math stays in `documents.ts`, already
  contract-tested.)
- **Pinned**: each status → the catalog key whose pt-BR value is the rendered badge label
  (asserted via `catalog["pt-BR"].status[*]`).

## E5. Entries deep-link view-state (`src/app/dashboard/entries/deeplinkView.ts`)

A pure function turning a resolved deep link into the view-state the client applies:
- `deepLinkView(input): DeepLinkView` where `input` carries the params + the
  already-computed `resolveDeepLink` inputs (period match, present/filtered flags, analysis-exists)
  and `DeepLinkView` is `{ selectPeriod?: string; highlightIndex?: number; openDialog: boolean;
  notice?: "invalid" | "not-found"; clearFilters?: boolean }`.
- Builds on the existing `resolveDeepLink` (unchanged) for the core decision; this layer maps each
  outcome to user-visible consequences and selects the localized notice **key** (the rendered text
  is `catalog["pt-BR"].notice.*`).
- `EntriesClient.tsx` consumes it (replacing inline branching) so the test pins the real path.
- **Pinned**: present+analysis → highlight + openDialog, no notice; absent → `notice:"not-found"`,
  no dialog; invalid → `notice:"invalid"`, no lookup/dialog; recovered-from-filter → `clearFilters`.

## E6. Route shaping

- `src/app/api/alerts/shape.ts` — `ALERT_RESPONSE_FIELDS` / `shapeAlertRow(row)`: the response
  projection (id, type, severity, title, description, referencePeriod, resolved, resolvedAt, notes,
  metadata). **Pinned**: shape/keys preserved.
- `src/app/api/documents/shape.ts` — `shapeDocumentRow(row)`: spreads the row and adds
  `status: documentStatus(sumEntries, totalValue)`. **Pinned**: status computed correctly per the
  shared contract; all listed fields present.
- `src/app/api/attachment-analyses/shape.ts` — `attachmentAnalysesPeriodScoped(period): boolean`
  (period present ⇒ scoped) + `ATTACHMENT_ANALYSIS_RESPONSE_FIELDS` projection list.
  **Pinned**: period present ⇒ scoped, absent/empty ⇒ unscoped; projection field set.

## E7. Coverage baseline record

- Recorded as the threshold numbers in the `test:ts:cov` package script (lines/branches/functions),
  established from the measured coverage of the tested module set at implementation time.
- **Ratchet**: `test:ts:cov` exits nonzero if measured coverage drops below the recorded baseline.
