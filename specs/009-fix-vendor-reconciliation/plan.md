# Implementation Plan: Vendor reconciliation & issuer roll-up

**Branch**: `fix-vendor-reconciliation-cnpj-rollup` | **Spec**: ./spec.md

## Summary

Replace the fragile near-exact substring vendor comparison in `scripts/analysis/documentos.py`
with a normalization-aware, cross-page reconciliation, and make the issuer roll-up prefer the
payment-artifact beneficiary while excluding the condominium payer. Stdlib-only Python; no D1 schema
change, no TypeScript.

## Constitution Check

- **III Quality gates**: Python analysis code; no TS touched, so `pnpm lint/format` not applicable.
  Keep change self-contained and readable.
- **V Simplicity / minimal change**: one new small helper module + targeted edits to the two seams
  (`build_document_analysis`, `_rollup_document_fields`, `_fanout_result`). No new dependencies.

## Design

### New module: `scripts/analysis/vendor_match.py` (stdlib only)

- `normalize_company_name(s) -> str`: accent-strip, upper, collapse whitespace, join single-letter
  spacing (`M G 2` → `MG2`-style canonical), strip punctuation, expand abbreviation map, drop
  trailing legal/size suffix tokens (`LTDA`, `ME`, `EPP`, `EIRELI`, `SA`).
- `PAYER_DENYLIST`: normalized condominium payer names (default `SAO VICENTE HOME CLUB`).
- `is_payer_name(name) -> bool`: true if the normalized name matches a denylist entry.
- `names_match(a, b) -> bool`: normalized comparison; substring containment for sufficiently long
  normalized strings, token-superset/equality for short ones (FR-007 over-match guard); false if
  either is empty/payer.
- `reconcile_vendor(ledger_vendor, issuer_names) -> bool | None`: returns None if no ledger vendor or
  no non-payer issuer names; else true if ANY non-payer issuer name matches the ledger vendor.

### Edits in `documentos.py`

- `_rollup_document_fields`: when choosing `issuer_name`, prefer a payment-artifact / boleto record's
  `nome_emitente`, skip payer names, fall back to invoice/nfse then any. (Keeps existing precedence
  for other identity fields.)
- `build_document_analysis`: collect all per-page `nome_emitente` values; set `vendor_match` via
  `reconcile_vendor(vendor_name, issuer_names)`.
- `_fanout_result`: same `reconcile_vendor` over the copied records' issuer names (sibling path).

## Verification

Re-run scoped chain for the 63 affected documents:
`docs-plan` (already planned; reading unchanged so no re-classify needed) → `apply-extractions` →
`analyze` → `mismatches`, confirm the 63 false vendor mismatches are gone and the 5 true ones remain.
