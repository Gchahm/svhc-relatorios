# Implementation Plan: Dedicated Alert Detail Page

**Branch**: `022-alert-detail-page` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/022-alert-detail-page/spec.md`

## Summary

Mirror the documents detail-page pattern (feature 021) for alerts. Replace the alerts list's
click-to-toggle-resolved behavior with navigation to a dedicated, shareable detail page at
`/dashboard/alerts/[id]`. The page shows the alert's full core fields (title, severity, type, period,
created/resolved timestamps, full description, notes), its affected entries (deep-linked into the
entries view), a readable rendering of its type-specific metadata evidence, and — when the metadata
references a document — a cross-link to that document's detail page. Resolve/reopen (with optional
notes) moves onto the detail page. Implemented by adding `GET /api/alerts/[id]`, extending the list's
`metadata`-driven entry-link logic into a shared helper, adding one App Router page, and changing the
list row from toggle to navigate. No schema change; reuses the existing `PATCH /api/alerts/[id]`.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router)
**Primary Dependencies**: Drizzle ORM (Cloudflare D1), better-auth, shadcn/ui (card, badge, button,
textarea, popover), lucide-react, `@tanstack/react-virtual` (existing list). **No new npm
dependencies.** The shadcn `textarea` primitive is not yet in `components/ui`; it is added by hand
using shadcn's canonical source (a ~15-line wrapper over `<textarea>` + `cn()`) — no CLI/network, no
new dependency — keeping the notes input consistent with the other shadcn primitives.
**Storage**: Cloudflare D1 (SQLite). Tables read: `alerts`, plus `entries` + `accountability_reports`
+ `documents` only as link/label targets. All read-only except the existing `alerts` resolve update.
No migration.
**Testing**: No test framework configured (Constitution III) — manual verification via `ui-login` /
`verify` against the running dashboard.
**Target Platform**: Cloudflare Workers via `@opennextjs/cloudflare`.
**Project Type**: Web application (single Next.js app).
**Performance Goals**: Detail page loads the alert in one request; resolve/reopen is a single PATCH.
No regression vs. the current list.
**Constraints**: Auth-gated to roles `admin`/`member` (Constitution IV). Navigation must never mutate
state; resolve/reopen is explicit. Malformed metadata must degrade gracefully.
**Scale/Scope**: ~100 alerts; a handful of alert types each with small metadata objects.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS. Pure TypeScript; no schema change. Metadata is parsed
  defensively (unknown → typed narrowing), no unjustified `any`.
- **II. Cloudflare-Native Architecture**: PASS. All DB access via `await getDb()`. No new bindings.
- **III. Quality Gates Before Commit**: PASS. `pnpm lint` + `pnpm format` before commit; manual UI
  verification. Tests OPTIONAL and not requested.
- **IV. Security & Auth by Default**: PASS. New page under the auth-gated `/dashboard` layout; the new
  `GET /api/alerts/[id]` and the existing `PATCH` keep the role check.
- **V. Simplicity & Incremental Delivery**: PASS. Adds one read endpoint, one page; reuses the existing
  PATCH, the existing entry-link logic (promoted to a shared helper), the document detail page (021),
  and shadcn primitives. Delivered as prioritized slices (P1 page+resolve → P2 evidence/cross-links).

**No violations — Complexity Tracking left empty.**

## Project Structure

### Documentation (this feature)

```text
specs/022-alert-detail-page/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (read-only view model — no schema change)
├── quickstart.md        # Phase 1 output (manual verification)
├── contracts/
│   ├── alert-detail-get.md   # GET /api/alerts/[id] response contract (new)
│   └── alert-patch.md        # PATCH /api/alerts/[id] (existing; documented + metadata added)
└── checklists/
    └── requirements.md  # Spec quality checklist (from specify)
```

### Source Code (repository root)

```text
src/
├── app/
│   ├── api/
│   │   └── alerts/
│   │       ├── route.ts               # unchanged (list)
│   │       └── [id]/route.ts          # ADD GET (single alert incl. metadata, createdAt); PATCH
│   │                                   #   already exists — also return metadata for consistency
│   └── dashboard/
│       └── alerts/
│           ├── page.tsx               # unchanged (lists alerts)
│           ├── AlertsClient.tsx       # EDIT: row click navigates; remove toggle + window.prompt
│           ├── alerts.ts              # NEW: shared affectedEntryIds() + severity/status helpers
│           └── [id]/
│               ├── page.tsx           # NEW: server page → renders AlertDetailClient
│               └── AlertDetailClient.tsx  # NEW: core fields + entries + evidence + resolve/reopen
└── components/ui/textarea.tsx         # NEW: canonical shadcn Textarea (notes input)
```

**Structure Decision**: Single Next.js App Router app, identical shape to feature 021. The detail page
is a nested dynamic route `/dashboard/alerts/[id]` inheriting the `/dashboard` auth layout. Data: add
`GET /api/alerts/[id]` (the list returns all rows but the detail page is loaded by id for the
shareable-URL case and to avoid depending on list state); reuse the existing `PATCH /api/alerts/[id]`
for resolve/reopen (extended to also return `metadata` so the client has a complete object). The
`affectedEntryIds` parsing + the `SeverityBadge`/`StatusBadge` currently inline in `AlertsClient` are
promoted to a shared `alerts.ts` module so the list and detail page can't drift.

## Complexity Tracking

> No Constitution violations — section intentionally empty.
