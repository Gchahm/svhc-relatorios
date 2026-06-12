# Implementation Plan: Refetch alerts list after a resolve/reopen action on the detail page

**Branch**: `032-refetch-alerts-on-return` | **Date**: 2026-06-12 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/032-refetch-alerts-on-return/spec.md`

## Summary

The alerts list (`AlertsClient.tsx`) fetches `/api/alerts` on mount and refetches only on the
`window` `focus` event. Resolving/reopening an alert on its detail page (`AlertDetailClient.tsx`,
PATCH `/api/alerts/[id]`) and returning to the list via in-app (same-tab) navigation does not fire
a `focus` event, so the list shows a stale Active/Resolved status until the user switches tabs or
hard-refreshes (IMP-009 / issue #46).

**Approach** (issue Suggestion 1, the cheapest viable): add a `document` `visibilitychange`
listener alongside the existing `window` `focus` listener so the list also refetches when the page
becomes visible again on the same tab. Add a small in-flight guard so a slower earlier response can
never overwrite a newer one (FR-005). No API, schema, or pipeline change.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 (Next.js 15 App Router, client component)
**Primary Dependencies**: Existing only — React (`useEffect`/`useRef`), the browser `document`
`visibilitychange` event and `window` `focus` event, the existing `/api/alerts` fetch. No new npm
dependency.
**Storage**: N/A (read-only `GET /api/alerts`; no schema/migration change)
**Testing**: Manual verification via the running app (`verify` / `ui-login` skills) — the repo has
no test framework (constitution Principle III; tests OPTIONAL). No automated test added.
**Target Platform**: Cloudflare Workers (OpenNext) / modern browsers
**Project Type**: Web application (Next.js App Router) — single client component change
**Performance Goals**: A redundant refetch on return is acceptable (small payload, cheap endpoint);
no measurable performance concern.
**Constraints**: Must preserve current filter selections and the existing tab-`focus` refetch; must
not let a stale in-flight response overwrite newer data.
**Scale/Scope**: One file changed (`src/app/dashboard/alerts/AlertsClient.tsx`); ~15 lines.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline**: PASS — TypeScript-only change, no `any`, no schema change
  (no `pnpm db:generate`). The `/api/alerts` contract is unchanged.
- **II. Cloudflare-Native Architecture**: PASS — no DB access added; this is a client-side data
  freshness fix. The existing route already uses `getDb()`.
- **III. Quality Gates Before Commit**: PASS — will run `pnpm lint` and `pnpm format` before commit.
  No tests mandated; manual verification of the running app will be done and recorded in the PR.
- **IV. Security & Auth by Default**: PASS — no new route or data exposure; the existing auth-gated
  `/api/alerts` is reused.
- **V. Simplicity & Incremental Delivery**: PASS — the smallest change that fixes the defect (one
  extra event listener + an in-flight guard), reusing the existing `fetchData` flow rather than
  introducing shared state, a broadcast channel, or a new dependency.

No violations. Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/032-refetch-alerts-on-return/
├── plan.md              # This file
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (N/A — no data model change; documents why)
├── quickstart.md        # Phase 1 output (manual verification steps)
├── contracts/           # Phase 1 output (N/A — no API change; documents why)
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/app/dashboard/alerts/
├── AlertsClient.tsx          # CHANGED — add visibilitychange refetch + in-flight guard
├── alerts.tsx                # unchanged (StatusBadge etc.)
└── [id]/
    ├── AlertDetailClient.tsx # unchanged (resolve/reopen PATCH already correct)
    └── page.tsx              # unchanged
```

**Structure Decision**: Web application (Next.js App Router). The change is confined to the single
client component `src/app/dashboard/alerts/AlertsClient.tsx`. The detail page already performs the
PATCH correctly and updates its own state; the only gap is the list's data freshness on return, so
no other file changes.

## Complexity Tracking

No constitution violations — section intentionally empty.
