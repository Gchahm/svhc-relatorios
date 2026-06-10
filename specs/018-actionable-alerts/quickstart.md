# Quickstart: Actionable Alerts

## Verify the analysis side (Python)

```bash
cd scripts
# Run the checks for a period (writes alerts to local D1, delete-then-insert).
uv run python -m analysis analyze --periodo 2025-12

# Per-attachment mismatch alerts now exist; confirm they agree with the loop CLI:
uv run python -m analysis mismatches --periodo 2025-12 \
  | python -c "import json,sys; rows=json.load(sys.stdin); \
print('mismatch kinds:', sorted(r['kind'] for r in rows if r['kind']!='duplicate_billing'))"

# Idempotency (FR-003 / SC-003): run analyze twice, alert set is identical.
uv run python -m analysis analyze --periodo 2025-12
# (re-run) → same ids, no duplicates.
```

Expected: every `amount`/`vendor`/`date`/`page-error` row from `mismatches` corresponds to an
`attachment_amount_mismatch` / `attachment_vendor_mismatch` / `attachment_date_mismatch` /
`attachment_page_error` alert from `analyze` (SC-004).

## Verify the web side

```bash
pnpm dev   # or pnpm preview for the Cloudflare runtime
```

1. Open `/dashboard/alerts`.
2. A per-attachment mismatch alert (e.g. "amount mismatch") shows an affected-entry link in
   the new **Entries** column. A `duplicate_billing` alert shows a **popover** listing each
   sibling entry.
3. Click an entry link → lands on `/dashboard/entries?period=<YYYY-MM>&entry=<id>` with the
   correct period selected, the row highlighted, and the attachment-analysis detail dialog
   open (page images + extracted-vs-ledger). (SC-001)
4. Close the dialog → still on the entries page, same period (US1.3).
5. A period/category-level alert (e.g. balance/subtotal) shows **no** link (FR-009).

## Lint/format gate (Constitution III)

```bash
pnpm lint && pnpm format
```

Python stays stdlib-only; confirm no import cycle:
```bash
cd scripts && uv run python -c "import analysis; import analysis.extractions; import analysis.checks; import analysis.mismatches; print('imports OK')"
```
