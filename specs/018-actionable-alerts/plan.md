# Implementation Plan: Actionable Alerts — Drill-Down to Entry/Attachment Validation

**Branch**: `018-actionable-alerts` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-actionable-alerts/spec.md`

## Summary

Turn aggregate, inert alerts into one-click investigations. Two seams:

1. **Analysis (Python).** Factor the per-attachment mismatch detection out of
   `summarize_mismatches` into a shared, stdlib-only module so the loop's `mismatches` CLI
   and a new user-facing check (`check_attachment_mismatches`) derive mismatches from the
   **same** function (FR-004). The new check emits one idempotent alert per
   (attachment, kind) — amount / vendor / date / page-error — with linkage metadata
   (`attachment_id`, `entry_id`, `kind`, `ledger_value`, `extracted_value`). Existing
   entry-level alerts already carry `entry_ids` / `attachment_ids`; they just need to be
   surfaced.

2. **Web (TypeScript/Next.js).** Expose `alerts.metadata` from `/api/alerts`. `AlertsClient`
   parses it and renders affected-entry deep links (single link for 1:1 mismatch alerts; a
   popover list for multi-entry alerts). `EntriesClient` reads `?period=&entry=` search
   params, selects the period, scrolls/highlights the row, and auto-opens the existing
   `AttachmentAnalysisDetailDialog` for that entry via the existing `analysisByEntry` map.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI, stdlib only); TypeScript 5 / React 19 / Next.js 15 (App Router)  
**Primary Dependencies**: Drizzle ORM (D1), better-auth, shadcn/ui (`popover`, `badge`, `card`), `@tanstack/react-virtual`, lucide-react. **No new npm or pip dependencies.**  
**Storage**: Cloudflare D1 (`alerts`, `attachment_analyses`, `attachments`, `entries`) — `alerts.metadata` (JSON text) **already exists**; no schema change. Page images in R2 (`DOCUMENTS`).  
**Testing**: No test framework configured (Constitution III) — verification is manual + a re-run idempotency check via the CLI.  
**Target Platform**: Cloudflare Workers (web) + local `wrangler`/Miniflare and `uv`-run Python CLI.  
**Project Type**: Web application (Next.js frontend + Python analysis pipeline).  
**Performance Goals**: Alerts list stays responsive (virtualized); deep-link navigation feels instant (client-side route + already-fetched period data).  
**Constraints**: No D1 schema migration; reuse existing reconciliation/match flags; alert idempotency via deterministic ids.  
**Scale/Scope**: ~hundreds of alerts/period; a shared-NF group is typically 2 entries, occasionally more.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No schema change (`alerts.metadata` exists);
  no migration. New TS types are explicit; metadata parsed defensively (untyped JSON → typed
  shape with guards). No `any` without justification.
- **II. Cloudflare-Native Architecture** — PASS. API uses `await getDb()`; no new bindings.
  Python writes via the existing `common/d1.py` wrapper (delete-then-insert per period).
- **III. Quality Gates Before Commit** — PASS. `pnpm lint` + `pnpm format` before commit;
  Python stays stdlib-only and import-cycle-free. No tests mandated.
- **IV. Security & Auth by Default** — PASS. `/api/alerts` keeps the existing role gate;
  metadata exposed is already-derived, non-sensitive linkage data. Deep link carries only a
  period + entry id; the entries route is already auth-gated.
- **V. Simplicity & Incremental Delivery** — PASS. Reuses the `_alert(..., discriminator=…)`
  pattern, the `analysisByEntry` map, and the existing detail dialog. The three user stories
  are independently shippable (links for existing alerts; new mismatch alerts; idempotency).

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/018-actionable-alerts/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (alert-metadata + deep-link + CLI contracts)
└── tasks.md             # Phase 2 output (speckit tasks)
```

### Source Code (repository root)

```text
scripts/analysis/
├── mismatches.py                 # NEW — shared per-attachment mismatch detection (single source of truth)
├── extractions.py                # EDIT — summarize_mismatches() calls mismatches.detect_attachment_mismatches()
└── checks/
    ├── attachments.py            # NEW — check_attachment_mismatches() → per-(attachment,kind) alerts
    └── __init__.py               # EDIT — run_all_checks wires in the new attachment check

src/app/
├── api/alerts/route.ts           # EDIT — add `metadata` to the select
└── dashboard/
    ├── alerts/AlertsClient.tsx   # EDIT — parse metadata, render affected-entry deep links
    └── entries/EntriesClient.tsx # EDIT — read ?period=&entry=, select period, scroll/highlight, auto-open dialog

docs / CLAUDE.md / scripts/README.md / scripts/pipeline-flow.md  # EDIT — document the new alert + link contract
```

**Structure Decision**: Web application with a Python analysis pipeline. The new
mismatch-detection logic lives in a new stdlib-only module `scripts/analysis/mismatches.py`
imported by both the loop's `summarize_mismatches` (in `extractions.py`) and the new
user-facing check (`checks/attachments.py`) — this is the single source of truth and avoids
an import cycle (the new module imports only model/ref types). The frontend changes are
contained to the alerts API route and the two existing dashboard clients; no new routes,
no new components beyond reusing the shadcn `popover`.

## Complexity Tracking

> No constitution violations — section intentionally empty.
