# Tasks: Surface per-page document-analysis detail in the UI

**Feature**: 004-doc-analysis-detail | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**Tests**: None requested (no test framework configured per Constitution III). No test tasks generated.

## Conventions

- File paths are repo-relative.
- `[P]` = parallelizable (different files, no incomplete dependency).
- Story labels: [US1] roll-up detail, [US2] per-page records, [US3] reconciliation indicator.

---

## Phase 1: Setup

- [x] T001 Confirm reusable building blocks exist (no new deps): verify `src/components/ui/dialog.tsx`, `src/components/ui/badge.tsx`, `src/components/ui/card.tsx` are present and that `src/app/api/alerts/[id]/route.ts` is the dynamic-route pattern to mirror.

## Phase 2: Foundational (blocking prerequisites)

- [x] T002 Create the detail API route file `src/app/api/document-analyses/[id]/route.ts` exporting an async `GET(request, { params }: { params: Promise<{ id: string }> })`, copying the exact auth guard (`initAuth` → `getSession` → `ALLOWED_ROLES = ["admin","member"]` → 403) from `src/app/api/document-analyses/route.ts`.
- [x] T003 In `src/app/api/document-analyses/[id]/route.ts`, query `documentAnalysisRecords` (from `@/db/fiscal.schema`) via `await getDb()` filtered by `eq(documentAnalysisRecords.documentAnalysisId, id)`, selecting `id, analysisType, pageIndex, pageLabel, artifactRole, response, rawText, parseError`, ordered by `pageIndex` ascending (nulls last); return the rows as JSON (`[]` when none). Match the contract in `contracts/document-analysis-detail.md`.

## Phase 3: User Story 1 — Inspect roll-up detail (Priority: P1) 🎯 MVP

**Goal**: Clicking a list row opens a dialog showing the roll-up fields already in the list payload.

**Independent test**: Open any analysis row → issuer, CNPJ, document number, service description,
document type, and error render (or show a "not extracted" indicator); error shown prominently.

- [x] T004 [US1] Create `src/app/dashboard/document-analyses/DocumentAnalysisDetailDialog.tsx` (client component) accepting an `analysis: DocAnalysisRow | null` prop and `onOpenChange`; render a shadcn `Dialog`/`DialogContent` with a `DialogHeader`/`DialogTitle`. Add a small `Field` helper that shows a label + value, and renders a muted "not extracted" indicator when the value is null/empty (FR-002, FR-009).
- [x] T005 [US1] In `DocumentAnalysisDetailDialog.tsx`, render a roll-up section showing `issuerName`, `extractedCnpj`, `documentNumber`, `serviceDescription`, `documentType`, the compared amounts (`entryAmount` vs `extractedAmount`, currency-formatted), and the three match flags reusing the existing badge style; render the roll-up `error` prominently (e.g. destructive styling) when present (FR-002, FR-003).
- [x] T006 [US1] In `src/app/dashboard/document-analyses/DocumentAnalysesClient.tsx`, add `selectedAnalysis` state, make each virtualized row clickable (cursor-pointer + `onClick` to set it) without breaking fixed 40px row height/virtualization, and render `<DocumentAnalysisDetailDialog>` controlled by that state (FR-001, FR-010).

**Checkpoint**: Roll-up detail is viewable for every analysis — US1 independently shippable.

## Phase 4: User Story 2 — Per-page records breakdown (Priority: P1)

**Goal**: The dialog fetches and lists every per-page record with label, role, parsed values,
and parse error.

**Independent test**: Open a multi-page analysis → each page listed with label, artifact role,
parsed amounts; failed page shows parse error; no-records analysis shows empty state.

- [x] T007 [US2] In `DocumentAnalysisDetailDialog.tsx`, define a `DocAnalysisRecord` type and a `parseResponse(response, rawText, parseError)` helper that `JSON.parse`s `response` inside try/catch and returns `{ values, fallback }` — on failure `values` is empty and `fallback` carries `rawText`/`parseError` (FR-009).
- [x] T008 [US2] In `DocumentAnalysisDetailDialog.tsx`, on open (analysis id present) fetch `GET /api/document-analyses/${id}`; track loading/error/records state; reset/refetch when the analysis id changes; show loading and error states (research Decision 6).
- [x] T009 [US2] In `DocumentAnalysisDetailDialog.tsx`, render the records list: per record show `pageLabel` (fallback `page {pageIndex+1}` / `?`), an `artifactRole` badge, the well-known parsed values with friendly labels (Gross `valor_total`, Net `valor_liquido`, Paid `valor_pago` currency-formatted; CNPJ, Issuer, Issue date, Document №, Service, Doc type), and any remaining keys generically; show the `parseError`/`rawText` fallback when parsing failed; show an empty-state message when records is `[]` (FR-004, FR-005, FR-009, Story 2 AC-4).

**Checkpoint**: Full per-page breakdown visible; US1 + US2 deliver the issue's core gap.

## Phase 5: User Story 3 — Reconciliation indicator (Priority: P2)

**Goal**: Distinguish a payment-artifact-reconciled amount from a plain invoice amount.

**Independent test**: Open an analysis with a payment_proof/boleto record → reconciliation badge
shown; invoice-only analysis → no badge.

- [x] T010 [US3] In `DocumentAnalysisDetailDialog.tsx`, derive `reconciledAgainstPayment` = any record `artifactRole ∈ {payment_proof, boleto}`; when true, render a badge/note near the roll-up amount stating the amount was reconciled against a payment artifact; render nothing extra otherwise (FR-007, research Decision 4).

## Phase 6: Polish & Cross-Cutting

- [x] T011 [P] Verify graceful degradation: analysis with `error` and no records, malformed `response`, null `pageLabel`, and long record lists (scrollable dialog) all render without crashing (FR-009, edge cases).
- [x] T012 Run `pnpm lint` and `pnpm format`; fix any findings (Constitution III).
- [x] T013 Manual verification per `quickstart.md` steps 1–4 (incl. unauthenticated `curl` → 403).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T003)** → user stories.
- **US1 (T004–T006)** depends only on Foundational; this is the MVP.
- **US2 (T007–T009)** depends on the dialog existing (T004) and the detail route (T002–T003).
- **US3 (T010)** depends on US2 (needs the fetched records).
- **Polish (T011–T013)** last.

## Parallel Opportunities

- T002–T003 (API route) can proceed in parallel with T004–T005 (dialog roll-up shell) — different
  files — then T006 wires the dialog into the client and T008 wires the fetch.
- T011 is independent verification and can run alongside final review.

## Implementation Strategy

- **MVP = Phase 1 + 2 + 3 (US1)**: roll-up detail dialog backed by data already in the list payload.
- Add **US2** for the per-page records (the core forensic value), then **US3** for the
  reconciliation cue. Each phase is an independently demoable increment.
