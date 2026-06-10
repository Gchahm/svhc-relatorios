# Implementation Plan: Real Documents Entity

**Branch**: `020-documents-entity` | **Date**: 2026-06-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/020-documents-entity/spec.md`

## Summary

Make the **document** a persisted, globally-deduplicated entity keyed on (normalized document number, issuer CNPJ), linked N:N to ledger entries, with overpayment detection and a browse UI. Two new D1 tables (`documents`, `document_entries`) via a Drizzle migration; a stdlib-only Python build step that derives documents + links from `attachment_analyses` across **all** periods (global, idempotent upsert via deterministic ids); a global `document_overpayment` alert that supersedes `duplicate_billing`; and a `/dashboard/documents` page + `/api/documents` (+ `/[id]`) reusing the vendors-list template and the feature-018 alert→entry deep-link.

## Technical Context

**Language/Version**: Python 3.12 (analysis CLI, stdlib only, run via `uv`); TypeScript 5 / React 19 / Next.js 15 (App Router)  
**Primary Dependencies**: Drizzle ORM (D1), better-auth, shadcn/ui (`select`, `input`, `badge`, `popover`, `dialog`, `card`, `table`), lucide-react, `@tanstack/react-virtual`. D1/R2 access from Python via `scripts/common/d1.py` (wrangler-CLI wrapper). **No new npm or pip dependencies.**  
**Storage**: Cloudflare D1 (`DATABASE` → `fiscal-db`). New tables `documents`, `document_entries`. Existing tables `attachment_analyses`, `attachments`, `entries`, `accountability_reports`, `alerts` read-only here (alerts written via existing path).  
**Testing**: No test framework configured (constitution III); validation is `pnpm lint` + `pnpm format` + `pnpm build` (tsc) + manual pipeline run.  
**Target Platform**: Cloudflare Workers via `@opennextjs/cloudflare`.  
**Project Type**: Web (Next.js app + Python analysis CLI in the same repo).  
**Performance Goals**: N/A — batch analysis + a small admin listing (hundreds–thousands of documents). Listing query must aggregate link counts/sums server-side.  
**Constraints**: Documents are **global** (not period-scoped); the build + overpayment steps read D1 across all periods independent of any `--periodo` filter. Pipeline stays stdlib-only.  
**Scale/Scope**: One condominium's fiscal history (tens of periods, low thousands of entries/attachments).

## Constitution Check

*GATE: re-checked after Phase 1 design — still passing.*

- **I. Type Safety & Schema Discipline**: New tables added to `src/db/fiscal.schema.ts` and migrated via `pnpm db:generate` → committed `drizzle/0011_*.sql`. No hand-edited migrations. No `any` without justification. ✅
- **II. Cloudflare-Native Architecture**: API routes use `await getDb()`; Python writes go through `scripts/common/d1.py` (wrangler). No direct connections. ✅
- **III. Quality Gates**: `pnpm lint` + `pnpm format` before commit; `pnpm build` validates tsc. Tests not added (none configured). ✅
- **IV. Security & Auth by Default**: `/api/documents` + `/api/documents/[id]` reuse the exact `ALLOWED_ROLES` session guard from `/api/vendors`; the page sits under the auth-gated `/dashboard`. ✅
- **V. Simplicity & Incremental Delivery**: Reuses `nf_total_for_reconciliation` / `reconcile_group` / `group_attachments` (no new reconciliation math), the vendors list template, and the feature-018 deep-link. Three independently-shippable slices (schema+build, alert, UI). ✅

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/020-documents-entity/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions/rationale
├── data-model.md        # Phase 1 — tables, fields, keys, derivation rules
├── quickstart.md        # Phase 1 — run/verify steps
├── contracts/
│   ├── documents-api.md       # GET /api/documents, GET /api/documents/[id]
│   └── build-documents-cli.md # python -m analysis build-documents
├── checklists/
│   └── requirements.md  # spec quality checklist (from specify)
└── tasks.md             # Phase 2 (speckit tasks)
```

### Source Code (repository root)

```text
src/
├── db/
│   └── fiscal.schema.ts                      # +documents, +document_entries tables & relations
├── app/
│   ├── api/documents/
│   │   ├── route.ts                          # GET list (auth + Drizzle aggregate)
│   │   └── [id]/route.ts                     # GET one document + its linked entries
│   └── dashboard/
│       ├── layout.tsx                        # +Documents nav link
│       └── documents/
│           ├── page.tsx                      # server component (template: vendors/page.tsx)
│           └── DocumentsClient.tsx           # filter+search table, detail dialog, deep links
drizzle/
└── 0011_<name>.sql                           # generated migration (documents, document_entries)

scripts/
├── common/
│   └── d1.py                                 # TABLE_ORDER += documents, document_entries
└── analysis/
    ├── documents.py                          # NEW: normalize/key, build_documents(), check_document_overpayment()
    ├── __main__.py                           # +build-documents subcommand
    ├── __init__.py                           # run_analysis: build docs + global overpayment writeback
    └── checks/
        └── advanced.py                       # remove check_duplicate_billing call (+ retire fn)

CLAUDE.md, scripts/README.md, scripts/pipeline-flow.md   # docs: "Attachments vs. Documents" now built; new step
```

**Structure Decision**: Single repo, web + Python-CLI layout (matches features 014–019). New Python logic concentrated in one module `scripts/analysis/documents.py` (build + overpayment) to keep the seam small; the schema/migration, API trio, and page mirror existing conventions exactly.

## Key design decisions (detail in research.md)

1. **Global, not period-scoped.** `build_documents` and `check_document_overpayment` query D1 directly across all periods (joining `attachment_analyses → attachments → entries → accountability_reports`), so they are correct regardless of the `analyze --periodo` filter. They run **once** in `run_analysis`, not inside the per-period `run_all_checks` loop.
2. **Idempotency via deterministic ids.** `documents.id = det_id("document", normalized_number, cnpj)`; `document_entries.id = det_id("document_entry", document_id, entry_id)`. Combined with `INSERT OR REPLACE` and the unique indexes, re-runs neither duplicate nor drift. `total_value` is recomputed each run as the **max** confident total over the document's analyses (order-independent → deterministic, no read-modify-write).
3. **Confidence gate.** A document is created only when the analysis has a non-empty normalized document number AND an issuer CNPJ reducing to exactly 14 digits. Else: no document, no link.
4. **Overpayment alert.** Reuses `reconcile_group(sum_live_entry_amounts, total_value) == "over_claim"`. Alert `reference_period` = the **max** period among linked entries. Writeback is a global `DELETE FROM alerts WHERE type='document_overpayment'` then insert — idempotent across any period filter, sidestepping the per-period delete loop.
5. **duplicate_billing retired.** `check_duplicate_billing` is removed from `run_advanced` and deleted; `document_overpayment` is its entity-backed successor. The `amount_match` split-reconciliation in `apply-extractions` is untouched.
6. **UI reuse.** Page/client/API mirror `vendors/*`; type filter = `Select`, search = `Input`; status badge mirrors `AlertsClient` badge variants; detail dialog lists linked entries with the `entryHref(period, entryId)` deep-link (Popover not needed — full list in dialog).
