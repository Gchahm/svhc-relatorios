# Phase 0 Research: Dedicated Alert Detail Page

No `[NEEDS CLARIFICATION]` markers in the spec. This records the design decisions against the existing
codebase.

## Decision 1 — Route shape mirrors feature 021

- **Decision**: Add `/dashboard/alerts/[id]` (`page.tsx` → `AlertDetailClient`). Alert rows in
  `AlertsClient` navigate there; the existing click-to-toggle-resolved (a `window.prompt` for notes)
  is removed.
- **Rationale**: The user asked for "the same behavior as docs" — the documents detail page from 021
  is exactly this shape (nested dynamic segment under the auth-gated dashboard, shareable URL, list
  row → navigate). Consistency + reuse (Constitution V).
- **Alternatives considered**: Keep toggle-on-click and add a separate "details" affordance — rejected:
  the user wants the row click itself to open details, and the accidental-status-flip risk of
  toggle-on-click is precisely what moving resolution to the detail page fixes.

## Decision 2 — Data: add `GET /api/alerts/[id]`, reuse the existing `PATCH`

- **Decision**: Add a `GET` to the existing `src/app/api/alerts/[id]/route.ts` returning the full
  alert (all `alerts` columns incl. `metadata` and `createdAt`). Keep the existing `PATCH` for
  resolve/reopen and extend its returned object to also include `metadata` (it currently omits it) so
  the client always holds a complete alert after a mutation.
- **Rationale**: The detail page must load by id for shareable URLs and direct visits, independent of
  whether the list was loaded (`GET /api/alerts` returns the whole list, not one row). One read
  endpoint + the existing write endpoint is the minimal surface (Principle V). The role check is
  copied from the sibling handlers (Constitution IV).
- **Alternatives considered**: Have the client filter the list payload for the one alert — rejected:
  breaks direct/shareable URLs and couples the page to list state.

## Decision 3 — Affected entries + badges: promote to a shared module

- **Decision**: Move `affectedEntryIds(metadata)`, `entryHref(period, id)`, `SeverityBadge`, and
  `StatusBadge` from `AlertsClient.tsx` into a new `src/app/dashboard/alerts/alerts.ts` (helpers) and
  small shared badge components, imported by both the list and the detail page.
- **Rationale**: The detail page needs the same entry-link parsing and badges; sharing prevents drift
  (the same concern that put document status math in `src/lib/documents.ts`). The metadata shapes are
  known (feature 018 single `entry_id`; entry-level alerts use `entry_ids[]`).
- **Alternatives considered**: Duplicate the helpers — rejected (drift risk).

## Decision 4 — Structured metadata rendering

- **Decision**: Render the alert's metadata as labeled key/value fields. Recognized keys get friendly
  labels and formatting (currency for `total_value`/`sum_entries`/`over_amount`/`total`/`vendor_total`/
  `ledger_value`/`extracted_value` when numeric, percentage for `pct`/`rate_pct`, counts for
  `count`/`paying`/`delinquent`/`total`); `entry_ids`/`entry_id` are rendered as entry deep links (not
  raw ids) and excluded from the generic field grid; unknown keys fall back to a readable
  string/JSON. A `document_id` becomes a link to `/dashboard/documents/<id>`.
- **Rationale**: The metadata is heterogeneous across types (over-payment totals, mismatch
  ledger-vs-extracted, vendor concentration `pct`, duplicate `count`, delinquency rates — confirmed by
  querying local D1). A label map + sensible fallback covers all current types and any future one
  without per-type branching (Principle V). Mismatch alerts get an explicit "ledger vs extracted"
  pairing because that comparison is the point of the alert.
- **Alternatives considered**: Per-type bespoke components — rejected as over-built for the value; a
  generic labeled renderer with a few formatting rules is enough and future-proof.

## Decision 5 — Resolve/reopen UX on the detail page

- **Decision**: A primary action button — "Resolve" (active) / "Reopen" (resolved) — plus an optional
  notes `textarea` shown when resolving. Calls the existing `PATCH /api/alerts/[id]`; on success the
  page updates in place; on failure it shows an inline error and leaves the prior status untouched
  (FR-012). The list re-fetches on focus/navigation so a returning user sees the new status (FR-009).
- **Rationale**: Replaces the `window.prompt` with a proper inline control that has room for notes and
  doesn't fire on navigation. The PATCH contract (`{resolved, notes}`) already exists.
- **List freshness**: `AlertsClient` already fetches on mount; to satisfy FR-009 after returning from
  the detail page, re-fetch when the window/tab regains focus (cheap, no new dependency). This avoids a
  stale list without threading shared state across routes.

## Resolved unknowns

All Technical Context fields are concrete; no remaining NEEDS CLARIFICATION.
