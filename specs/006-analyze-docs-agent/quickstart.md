# Quickstart: Document analysis with the Claude vision agent

The VLM (`mlx_vlm`) flow is retired. Document analysis is now a three-step flow: **plan → extract
(agent) → apply**.

## Normal run (inside Claude Code)

```bash
# 1. Plan the work for a period (deterministic; groups shared NFs, applies filters).
cd scripts
uv run python -m scraper docs-plan --periodo 2025-12
#   → writes ../data/scrape/2025-12.extract-todo.json
```

```text
# 2. Extract — invoke the agent in Claude Code:
"Use the analyze-docs agent to extract document fields for 2025-12"
#   → the agent reads each page image and writes ../data/scrape/2025-12.extractions.json
#   (the agent can also run step 1 for you if no manifest exists yet)
```

```bash
# 3. Apply — merge the extractions into the period JSON (deterministic; roll-up + reconcile + write).
cd scripts
uv run python -m scraper apply-extractions --periodo 2025-12
#   → writes document_analyses (+ analysis_records) into ../data/scrape/2025-12.json
#   → run the financial analysis to emit duplicate_billing etc.:
uv run python -m scraper analyze --periodo 2025-12
```

Selection flags on `docs-plan` mirror the old `analyze-docs`: `--min-amount`, `--limit`,
`--reanalyze`, `--document-id`, `--entry-id`, `--data-dir`.

## Verification without a VLM (SC-002, runs in the sandbox)

The vision model can't run here, so behavior preservation is verified with **synthetic
extractions** — hand-authored values fed through the real deterministic pipeline.

1. Generate a manifest for a period (or hand-write a tiny one).
2. Author a `<period>.extractions.json` covering, at minimum:
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
