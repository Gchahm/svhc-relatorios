# Quickstart: Document analysis with the Claude vision skills

The VLM (`mlx_vlm`) flow is retired. Document analysis is now: **plan → classify (skills) → apply →
check → summarize**. The `analyze-docs` agent orchestrates these and hands back a terse mismatch
summary; you can also run the steps directly.

## Normal run (inside Claude Code)

```bash
# 1. Plan the work for a period (deterministic; groups shared NFs, applies filters/subset).
cd scripts
uv run python -m scraper docs-plan --periodo 2025-12   # or add --document-id <ids…> for a subset
#   → writes ../data/scrape/2025-12.extract-todo.json
```

```text
# 2. Classify — invoke the skills in Claude Code:
"Use the classify-period skill for 2025-12"
#   → classify-period fans each page out to classify-doc-page, which writes
#     <image>.classify.json next to every page image.
```

```bash
# 3. Apply — merge the per-page classifications (deterministic; roll-up + reconcile + write).
cd scripts
uv run python -m scraper apply-extractions --periodo 2025-12
#   → writes document_analyses (+ analysis_records) into ../data/scrape/2025-12.json

# 4. Check — emit alerts (duplicate_billing etc.).
uv run python -m scraper analyze --periodo 2025-12

# 5. Summarize — terse machine-readable mismatch list (the agent returns this).
uv run python -m scraper mismatches --periodo 2025-12   # or --document-id <ids…> to scope
```

Or delegate the whole thing: invoke the **`analyze-docs` agent** ("analyze the documents for
2025-12", or a `--document-id` subset) — it runs steps 1–5 in its own context and returns only the
mismatch summary.

Selection flags on `docs-plan`: `--min-amount`, `--limit`, `--reanalyze`, `--document-id`,
`--entry-id`, `--data-dir`.

## Verification without a VLM (SC-002, runs in the sandbox)

The vision model can't run here, so behavior preservation is verified with **synthetic
classifications** — hand-authored values fed through the real deterministic pipeline
(`fixtures/build_and_verify.py` writes one `<image>.classify.json` per page).

1. Generate a manifest for a period (or hand-write a tiny one).
2. Author the per-page `<image>.classify.json` files covering, at minimum:
    - a single-entry document (per-entry amount match),
    - a shared-NF group whose sibling sum **reconciles** with the NF gross total,
    - a shared-NF group whose sibling sum **exceeds** the NF total (expect `over_claim` →
      `duplicate_billing` alert after `analyze`),
    - a heterogeneous document (invoice + boleto + payment_proof pages) to exercise the
      amount-precedence roll-up,
    - a page with `{ "error": ... }` and a document with no usable page.
3. Run `apply-extractions` then `analyze`, and assert:
    - `document_analyses` / `document_analysis_records` shapes import cleanly via
      `node scripts/import-to-d1.mjs` against a scratch DB (SC-003),
    - reconciliation classifications and `amount_match`/`vendor_match`/`date_match` match the
      expected values for the synthetic inputs (SC-002),
    - the expected `duplicate_billing` alert is present for the over-claim group (FR-008).

A small synthetic fixture + assertions can live under `specs/006-analyze-docs-agent/` or be run
ad-hoc; no test framework is added (constitution Principle III).

## Confirm the VLM is gone (SC-006)

```bash
grep -rn "mlx_vlm\|_load_model\|_analyze_page\|EXTRACT_PROMPT" scripts/   # expect: no hits
grep -rn "mlx" scripts/pyproject.toml scripts/requirements*.txt 2>/dev/null  # expect: no hits
```
