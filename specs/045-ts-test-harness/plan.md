# Implementation Plan: TypeScript component/unit test harness for the dashboard

**Branch**: `045-ts-test-harness` | **Date**: 2026-06-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/045-ts-test-harness/spec.md`

## Summary

Close the TypeScript test gap on the fiscal-auditing dashboard by pinning the
auditor-evidence-bearing behaviors — alerts metadata → affected-entry deep links + localized
type labels, document over/within/under status math + localized badge labels, the entries
deep-link view-state decision (present / absent / invalid), and the API routes' auth decision +
row-to-response shaping — with the repo's existing **zero-dependency** Node test path
(`node --test` + native TypeScript type-stripping). Logic that currently lives inside `"use
client"` `.tsx` components (which Node cannot type-strip) is **extracted into sibling pure `.ts`
modules** behavior-preservingly, then tested. Coverage for `src/` is reported and **ratcheted**
with Node's built-in `--experimental-test-coverage` threshold flags (no coverage dependency),
mirroring the Python `test:py:cov` policy. Everything runs from the existing `pnpm test:ts`
(extended) plus a new `pnpm test:ts:cov` gate, both wired into the TEST-001 CI workflow.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 / Next.js 15 (App Router). Test runner is Node 22
(confirmed v22.22.3 — native `.ts` type-stripping + `node:test` + `--experimental-test-coverage`).
**Primary Dependencies**: **Existing only** — Node built-in `node:test` / `node:assert`; the
I18N-001 catalog (`@/lib/i18n/catalog`) as the source of truth for expected labels. **No new npm
dependency** (FR-011). A DOM/component-test stack (`vitest`+`@testing-library/react`) was evaluated
and **rejected** (see research.md) — the highest-risk interactive flow is verifiable by pure
extraction.
**Storage**: N/A — test-only feature. Reads no data, writes nothing, no D1 schema/migration.
**Testing**: `node --test "src/**/*.test.mjs"` (the existing pattern); coverage via
`node --test --experimental-test-coverage --test-coverage-exclude='**/*.test.mjs'
--test-coverage-lines/branches/functions=<baseline>`.
**Target Platform**: Node 22 (developer + CI). The code under test ships to Cloudflare Workers,
but the **pure** extracted logic is runtime-agnostic and imports no Cloudflare/Next runtime.
**Project Type**: Web app (Next.js App Router) — tests are colocated next to the source under `src/`.
**Performance Goals**: Whole TS suite well under a minute on a dev machine (SC-001).
**Constraints**: No new deps (FR-011); no E2E / real browser (FR-012); no snapshot/markup-dump
assertions (FR-010); UI-string assertions reference the pt-BR catalog, never English literals
(FR-009); `.tsx` cannot be imported by `node:test` (Node raises `ERR_UNKNOWN_FILE_EXTENSION`) →
pure logic must live in `.ts`.
**Scale/Scope**: 3 named API route surfaces + the shared auth decision; 4 dashboard client
behaviors (alerts, documents, entries deep-link, plus the already-pinned reconciliation contract).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Type Safety & Schema Discipline** — PASS. No `any` introduced in extracted modules; no
  schema/migration change (test-only). Extractions preserve exported types.
- **II. Cloudflare-Native Architecture** — PASS. The extracted pure logic imports no Cloudflare
  runtime; `getDb()` / `initAuth()` plumbing stays in the route files and is **not** invoked by
  tests (the auth decision + shaping are extracted as pure functions the route still calls).
- **III. Quality Gates Before Commit** — PASS and directly advanced. This feature is the spec
  that "explicitly requests tests" per Principle III; `pnpm lint` + `pnpm format` still gate the
  diff. The new tests MUST pass before merge.
- **IV. Security & Auth by Default** — PASS and reinforced. Extracting the auth decision into a
  single tested `isAuthorized(session)` function makes the deny-by-default behavior a pinned,
  regression-guarded contract shared by all three routes (rather than copy-pasted, untested).
- **V. Simplicity & Incremental Delivery** — PASS. Zero new deps; reuses the established
  `node:test` + `.ts`-extraction pattern; the five user stories are independently shippable slices.

No violations → Complexity Tracking table omitted.

## Project Structure

### Documentation (this feature)

```text
specs/045-ts-test-harness/
├── plan.md              # This file
├── spec.md              # Feature spec (+ Clarifications)
├── research.md          # Phase 0 — harness/coverage decisions
├── data-model.md        # Phase 1 — the test "entities" (extracted module contracts)
├── quickstart.md        # Phase 1 — how to run + add tests
├── contracts/           # Phase 1 — the extracted-module signatures pinned by tests
│   ├── auth-decision.md
│   ├── alerts-helpers.md
│   ├── document-status-label.md
│   ├── entries-deeplink-viewstate.md
│   └── route-shaping.md
├── checklists/requirements.md
└── tasks.md             # Phase 2 (speckit tasks)
```

### Source Code (repository root)

New/edited test files colocate next to the source they test (the established pattern):

```text
src/
├── lib/
│   ├── auth-access.ts            # NEW — pure isAuthorized(session) + ALLOWED_ROLES + UNAUTHORIZED_STATUS
│   ├── auth-access.test.mjs      # NEW — auth decision (US5)
│   ├── alerts.ts                 # existing pure label map (unchanged)
│   ├── alerts.test.mjs           # existing (unchanged)
│   ├── documents.ts              # existing status math (unchanged)
│   ├── documents.test.mjs        # existing contract test (unchanged)
│   ├── documents-label.ts        # NEW — pure documentStatusLabelKey(status) (catalog-key mapping)
│   ├── documents-label.test.mjs  # NEW — status → pt-BR catalog label (US3)
│   └── i18n/
│       ├── catalog.ts            # existing (source of truth for expected labels)
│       └── alert-type-label.ts   # NEW — pure alertTypeLabelFor(type, locale) (extracted from useAlertTypeLabel)
├── app/
│   ├── api/
│   │   ├── alerts/
│   │   │   ├── route.ts          # EDIT — call isAuthorized() + shapeAlertRow() (behavior-preserving)
│   │   │   ├── shape.ts          # NEW — pure shapeAlertRow / row→response (US5)
│   │   │   └── shape.test.mjs    # NEW
│   │   ├── documents/
│   │   │   ├── route.ts          # EDIT — call isAuthorized() + shapeDocumentRow()
│   │   │   ├── shape.ts          # NEW — pure shapeDocumentRow (adds status via documentStatus)
│   │   │   └── shape.test.mjs    # NEW
│   │   └── attachment-analyses/
│   │       ├── route.ts          # EDIT — call isAuthorized() (+ shaping if non-trivial)
│   │       ├── shape.ts          # NEW — pure shapeAttachmentAnalysisRow / period-scope predicate
│   │       └── shape.test.mjs    # NEW
│   └── dashboard/
│       ├── alerts/
│       │   ├── alerts.tsx         # EDIT — re-export pure helpers from alerts-helpers.ts (no behavior change)
│       │   ├── alerts-helpers.ts  # NEW — affectedEntryIds / entryHref / referencedDocumentId (moved out of .tsx)
│       │   └── alerts-helpers.test.mjs  # NEW (US2)
│       └── entries/
│           ├── deepLink.ts        # existing pure decision core (unchanged)
│           ├── deepLink.test.mjs  # existing (unchanged)
│           ├── deeplinkView.ts    # NEW — pure deep-link → view-state (period/highlight/dialog/notice) (US4)
│           ├── deeplinkView.test.mjs # NEW
│           └── EntriesClient.tsx  # EDIT (only if needed) — consume deeplinkView to remove duplicated logic
package.json                       # EDIT — extend test:ts; add test:ts:cov (baseline+ratchet)
.github/workflows/ci.yml           # EDIT — add a "TypeScript coverage" step (test:ts:cov)
```

**Structure Decision**: Web-app, colocated tests (`*.test.mjs` next to source) — the existing,
proven convention. Pure logic that today lives in `.tsx` is moved into sibling `.ts` modules so
`node:test` can import it (Node strips `.ts` but rejects `.tsx`); the `.tsx` component re-exports
or imports those helpers, preserving its public surface and behavior. No new top-level `tests/`
tree — colocation matches the repo and keeps coverage attribution per-file.

## Phase 0 — Research

See `research.md`. Resolved decisions: (1) **no DOM/component-test dependency** — the entries
deep-link flow is verifiable by extracting a pure view-state module, so the minimal `node:test`
path covers all five stories with zero new deps; (2) **coverage via Node's built-in
`--experimental-test-coverage` + threshold flags** — recording the baseline as the threshold value
is the ratchet (verified: exit 0 at/above baseline, exit 1 below), no coverage package; (3)
**`.tsx` import blocker** confirmed empirically (Node `ERR_UNKNOWN_FILE_EXTENSION`) → extraction
to `.ts`; (4) auth tests pin the **decision + the status constant read from the code**, not an
independently-hardcoded number; (5) labels asserted against `catalog["pt-BR"]`.

## Phase 1 — Design & Contracts

- **data-model.md** — the "entities" are the extracted pure-module contracts (inputs/outputs) the
  tests pin, plus the coverage-baseline record.
- **contracts/** — one file per extracted module signature (auth decision, alerts helpers,
  document status label, entries deep-link view-state, route shaping). These are the regression
  contracts; a unilateral change to any flips a test.
- **quickstart.md** — run `pnpm test:ts` / `pnpm test:ts:cov`, how the ratchet baseline is set,
  how to add a colocated test.
- **Agent context** — run `update-agent-context.sh`.

Post-design Constitution re-check: still PASS (no new deps, no schema change, auth contract
strengthened).
