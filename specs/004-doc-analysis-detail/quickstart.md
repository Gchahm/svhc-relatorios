# Quickstart: Document Analysis Detail

**Feature**: 004-doc-analysis-detail

## What this adds

A detail view on `/dashboard/document-analyses`. Click any analysis row to open a dialog showing:

- Roll-up fields: issuer name, CNPJ, document number, service description, document type, error.
- The three match flags (amount / vendor / date) and the compared amounts.
- A payment-reconciliation badge when the roll-up amount came from a payment_proof / boleto.
- Every per-page record: page label, artifact role, parsed values (gross / net / paid + others),
  and any parse error (falls back to raw text when parsing failed).

## Run locally

```bash
pnpm dev        # http://localhost:3000
```

Sign in as a user with role `admin` or `member`, go to **Dashboard → Document Analyses**, and
click a row.

## Manual verification

1. **Roll-up (Story 1)**: Open a row with a MISMATCH badge → confirm issuer, CNPJ, document
   number, service description render; empty fields show a "not extracted" indicator; an analysis
   with an `error` shows the error prominently.
2. **Per-page (Story 2)**: Open a multi-page analysis → confirm one entry per page with label,
   artifact role, and parsed amounts; a failed page shows its parse error; an analysis with no
   records shows the empty state.
3. **Reconciliation (Story 3)**: Open an analysis with a payment_proof/boleto page → confirm the
   payment-reconciliation badge; open an invoice-only analysis → confirm no such badge.
4. **Auth (FR-006)**: `curl -i http://localhost:3000/api/document-analyses/<id>` without a session
   → `403`.

## Pre-commit gates

```bash
pnpm lint
pnpm format
```
