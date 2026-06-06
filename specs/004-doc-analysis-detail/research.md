# Research: Surface per-page document-analysis detail

**Feature**: 004-doc-analysis-detail | **Date**: 2026-06-06

No NEEDS CLARIFICATION markers remained after specify. This document records the design decisions
that resolve the "how" left open by the spec's documented assumptions.

## Decision 1: Detail surface — dialog vs expandable row vs side panel

- **Decision**: Use a shadcn/ui `Dialog`, opened by clicking a list row.
- **Rationale**: The list is virtualized with fixed 40px row heights (`useVirtualizer`,
  `estimateSize: () => 40`). An expandable inline row would require variable row measurement and
  fight the virtualizer. A dialog leaves the list rendering path untouched (satisfies FR-010) and
  the `dialog.tsx` component already exists (Constitution V — reuse before adding).
- **Alternatives considered**: (a) Expandable rows — rejected, breaks fixed-height virtualization.
  (b) New `Sheet`/side panel — rejected, component not present; dialog covers the need.

## Decision 2: Where the per-page records come from

- **Decision**: A new route `GET /api/document-analyses/[id]` returns the
  `document_analysis_records` for that analysis id. The roll-up fields stay in the existing list
  payload (already returned); the dialog reads them from the already-loaded row and fetches only
  the records on open.
- **Rationale**: The list route already returns every roll-up field the dialog needs (issuer, CNPJ,
  document number, service description, type, error). Fetching records on demand keeps the list
  payload small and avoids an N×pages join across all analyses up front. Mirrors the existing
  `api/alerts/[id]/route.ts` dynamic-segment pattern.
- **Alternatives considered**: (a) Extend the list route to embed records for every analysis —
  rejected, inflates the list payload for data only needed when a row is opened. (b) Separate
  endpoint by query param — rejected, the `[id]` segment is the idiomatic App Router shape here.

## Decision 3: Rendering the per-page `response` JSON

- **Decision**: Parse `response` (a JSON string) into an object. Render the well-known fiscal keys
  with friendly labels — `valor_total` (gross), `valor_liquido` (net), `valor_pago` (paid),
  `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`, `descricao_servico`,
  `tipo_documento` — and show any remaining keys generically. If `response` is absent or fails to
  parse, fall back to `rawText` and/or `parseError` (FR-009).
- **Rationale**: The VLM prompt (`scripts/scraper/analise/documentos.py`) emits a stable set of
  Portuguese keys; labeling them aids the reviewer, while the generic pass keeps the view
  forward-compatible if the prompt gains fields (spec Assumptions). Amounts are the most important
  fields (FR-005), so they get prominent, currency-formatted display.
- **Alternatives considered**: Raw JSON dump only — rejected, fails the "parsed per-page values
  with labels" requirement and is hard to scan. Strict typed-only parse — rejected, would crash on
  malformed/extra keys, violating FR-009.

## Decision 4: Payment-artifact reconciliation indicator (Story 3 / FR-007)

- **Decision**: Derive the indicator on the client from the fetched records: if any record's
  `artifactRole` is `payment_proof` or `boleto`, show a badge stating the roll-up amount was
  reconciled against a payment artifact.
- **Rationale**: This exactly matches the pipeline's documented amount precedence
  (payment_proof paid → boleto → invoice net → invoice gross). No new field or computation is
  persisted — it is presentation derived from data already returned (FR-008).
- **Alternatives considered**: Adding a stored "reconciled" flag — rejected, would be a schema
  change the spec forbids. Inferring from amount comparison heuristics — rejected, less reliable
  than the explicit artifact role already recorded per page.

## Decision 5: Auth on the new route

- **Decision**: Copy the exact guard from `src/app/api/document-analyses/route.ts`:
  `initAuth()` → `getSession` → check `role ∈ ALLOWED_ROLES = ["admin", "member"]`, else 403.
- **Rationale**: FR-006 and Constitution IV require identical protection to the list route.
- **Alternatives considered**: Shared middleware helper — out of scope; the inline guard is the
  established repo pattern across every route under `src/app/api`.

## Decision 6: Fetch lifecycle in the dialog

- **Decision**: Fetch records when the dialog opens for a given analysis id; show a loading state,
  an error state, and cache nothing beyond the current open (simple per-open fetch). Empty records
  → explicit empty state (Story 2 AC-4).
- **Rationale**: Per-analysis record counts are tiny; a plain on-open fetch is simplest (YAGNI,
  Constitution V) and avoids stale-cache complexity.
- **Alternatives considered**: Prefetch on hover / global cache — rejected as premature
  optimization for small payloads.
