# Scripts

The scraper and analysis pipeline read and write **Cloudflare D1 + R2 directly** — there is no
`data/scrape/<period>.json` and no separate import step. Pick the target per run: default **local**,
or `--remote` for production (mirrors the project's `wrangler --local/--remote` convention). All D1/R2
access from Python goes through `scripts/common/d1.py` (a thin `wrangler`-CLI wrapper). All entities
use deterministic UUIDs — the same data always produces the same IDs, so re-scraping a period safely
upserts via `INSERT OR REPLACE`. An ephemeral, git-ignored cache (`.cache/analysis/`) holds
materialized page images and the loop's verdicts working file — per-page classifications live in
D1 (the `page_classifications` table), not in the cache.

## Scraper

Scrapes accountability data from BRCondos portal.

### Setup

```bash
cd scripts

# Install dependencies
uv sync

# Install playwright browser (one-time)
uv run playwright install chromium
```

Requires env vars in `scripts/.env`:

```
BRCONDOS_URL=https://ssl.brcondos.com.br
BRCONDOS_USER=...
BRCONDOS_PASSWORD=...
HEADLESS=true
```

### Usage

```bash
cd scripts

# Scrape all new periods into local D1 (skips periods already in the DB)
uv run python -m scraper scrape

# Scrape specific periods
uv run python -m scraper scrape --periodo 2026-01 2025-12

# Also download document images (uploaded to R2 during the run)
uv run python -m scraper scrape --download-docs

# Write to the remote (production) D1 + R2 instead of local
uv run python -m scraper scrape --periodo 2026-01 --download-docs --remote

# Download images for attachments missing them in R2 (updates attachments.file_path in D1)
uv run python -m scraper download-docs
uv run python -m scraper download-docs --periodo 2024-12 --remote
```

## Document analysis

Turns the document page images (materialized from R2) into structured records, validates them
against the ledger, and surfaces mismatches / fraud signals. It writes the results
(`attachment_analyses`, `attachment_analysis_records`, `alerts`) back into D1. Every command takes
`--remote` (default local). The flow is five steps:

```
scrape / download-docs  →  [1] docs-plan  →  [2] classify  →  [3] apply-extractions  →  [4] analyze  →  [5] mismatches
```

All five steps are plain CLI commands run from the shell — no browser, no interactive skill. Steps 1,
3, 4 and 5 are deterministic (stdlib only). Step 2 (`classify`) is the only vision step: it is headless,
shelling out to `doc_transcribe` (which calls `claude -p` or the Anthropic API) per page. The old local
VLM (`mlx_vlm`) and the interactive `classify-period`/`classify-doc-page` skills are retired.

### 1. `docs-plan` — pick the work and group shared invoices

```bash
cd scripts
uv run python -m analysis docs-plan --periodo 2025-12 [--min-amount N] [--limit N]
```

Reads the period from D1, materializes the **pending** attachments' page images from R2 into the cache,
and groups **byte-identical Nota Fiscal copies** so each unique invoice is read only once. Grouping
reads the persisted `attachments.content_hash` (computed at scrape time); for rows captured before that
column existed it falls back to hashing the materialized page files. **Prints the plan as JSON to
stdout** — the representative page images to read (local cache `read_path`s) plus the ledger context for
reconciliation — and writes **no manifest file**. The work set is whatever is _pending_
(`classified_at IS NULL`); there are no id flags — to (re)classify a subset, mark it pending in D1 with
`mark-pending` (below).

### 2. `classify` — read each page image into structured fields (headless vision)

```bash
cd scripts
uv run python -m analysis classify --periodo 2025-12 [--min-amount N] [--limit N] [--backend cli|api] [--model …]
```

A single headless CLI command. It builds the same **pending** plan `docs-plan` produces, materializes
the images from R2, and for each pending non-`recorded` page runs `tools/doc_transcribe` **as a
subprocess** (`python -m doc_transcribe --image <read_path> --type auto`), takes the typed
**EXTRACT-001** `fields` object it returns, and records it to the `page_classifications` staging table
via `record-classification` (one row per page). Pages are processed **serially**. The `--backend`
selects how `doc_transcribe` reaches a model: `cli` (default — shells out to `claude -p`, needs the
`claude` binary on PATH) or `api` (the Anthropic SDK); `--model` overrides the model.

**Error handling.** A **config** error — the subprocess exits non-zero (e.g. `claude` not on PATH) —
**stops** the run with a clear message (no silent fallback). A per-page **transcription** failure
(subprocess exits 0 but returns `parse_errors` / no usable fields) records an `{"error": …}` row for
that page and **continues**. This is the only non-deterministic step; it replaces the retired
interactive `classify-period`/`classify-doc-page` skills and the `analyze-docs` agent.

### 3. `apply-extractions` — merge classifications into the ledger data

```bash
cd scripts
uv run python -m analysis apply-extractions --periodo 2025-12 [--min-amount N] [--limit N]
```

Re-derives the same pending-set plan from D1 (no manifest — same `content_hash` grouping `docs-plan`
used), reads each page's recorded extraction from D1 (`page_classifications`), rolls each document up (heterogeneity-aware: a document
bundling an invoice, a boleto, and a payment proof resolves to one amount by precedence), reconciles
shared-NF groups (sum of sibling entries vs. the NF total), fans the result out to the sibling entries,
validates amount / vendor / date against the ledger entry, and writes `attachment_analyses` (with
per-page `analysis_records`) into D1. It **stamps `attachments.classified_at`** on each processed
attachment (so it leaves the pending set).

Apply reads **no page-image bytes** itself — per-page extractions come from D1 (`page_classifications`),
page labels are parsed from `file_path` tokens, and grouping prefers the persisted
`attachments.content_hash` column. So it materializes from R2 **only** to hash + backfill the
attachments whose `content_hash` is still NULL (legacy/edge rows); when every page-bearing attachment
is already keyed (the normal case post-scrape), it makes **no R2 image reads**. A page-less attachment
(empty `file_path`) legitimately has no hash and is never materialized. (The classify `docs-plan` and
review `mismatches` steps still materialize their images — the vision/review workers need them.)

To re-classify specific attachments (e.g. after merging a classifier fix), mark them pending first:

```bash
cd scripts
uv run python -m analysis mark-pending --periodo 2025-12 --attachment-id <ids…> [--entry-id <ids…>]
```

`mark-pending` clears `classified_at` (`UPDATE attachments SET classified_at = NULL …`) so the next
`docs-plan`/`apply-extractions` re-processes exactly those. This is how scope is controlled — by D1
state, deterministically — instead of passing id flags through the classify pipeline.

### 3b. `build-documents` — build the global documents entity

```bash
cd scripts
uv run python -m analysis build-documents        # global — no --periodo; add --remote for prod
```

Derives the **documents** entity from `attachment_analyses` (feature 020): one `documents` row per
unique fiscal document keyed by **(normalized `document_number`, 14-digit `issuer_cnpj`)** and one
`document_entries` link per referencing entry, **globally** (deduped across all periods; links
accrue as more periods are analyzed). An analysis missing a confident number or CNPJ creates
nothing. Idempotent (deterministic ids + unique indexes). `analyze` runs this automatically at its
start, so you only call it directly for backfill.

### 4. `analyze` — run the checks

```bash
cd scripts
uv run python -m analysis analyze --periodo 2025-12
```

Runs the financial / consistency / fraud checks over the period JSON and writes `alerts` — e.g.
**`document_overpayment`** (critical) when a real document's linked entries' amounts sum above its
total value (the entity-backed successor to the retired `duplicate_billing` over-claim check; built
and checked globally so it spans periods, with `metadata.entry_ids` driving per-entry deep links),
vendor concentration, new vendors, delinquency, etc. It also emits **per-attachment mismatch
alerts** — one per (attachment, kind): `attachment_amount_mismatch` / `attachment_vendor_mismatch` /
`attachment_date_mismatch` (severity `warning`) and `attachment_page_error` (`info`) — so a human
can drill into each from the alerts page (feature 018). Their detection is shared with `mismatches`
(`analysis/mismatches.py:detect_attachment_mismatches`) so the two can't drift, and each alert's
`metadata` carries `{attachment_id, entry_id, kind, ledger_value, extracted_value}` for the UI's
deep link. Ids are deterministic (`det_id("alert", period, type, attachment_id)`) and `analyze`
delete-then-inserts per `reference_period`, so re-runs are idempotent.

### 5. `mismatches` — terse summary of what disagrees

```bash
cd scripts
uv run python -m analysis mismatches --periodo 2025-12 [--attachment-id <ids…>] [--entry-id <ids…>]
```

Prints a compact JSON list of classification mismatches — `amount` / `vendor` / `date` /
`page-error` / `document_overpayment` — each joined with the ledger-vs-extracted values. Read-only (no
writes). This is the terse summary that closes out a `classify → apply-extractions → analyze →
mismatches` run. The per-attachment detection here is the **same** `detect_attachment_mismatches` the
`analyze` step uses for its per-attachment alerts (single source of truth).

Per-page classifications are stored in D1 (`page_classifications`), not in the cache; the
`.cache/analysis/` dir holds only materialized page images + the loop's verdicts file (gitignored,
reproducible from D1+R2). The extraction plan is derived from D1 each run (no manifest file).
**Cloudflare D1 is the source of truth** and the analysis commands write their results straight there.

## Typical workflow

```bash
cd scripts

# 1. Scrape a period straight into local D1 + upload its images to local R2
uv run python -m scraper scrape --periodo 2025-12 --download-docs

#    (production: add --remote to write the remote D1 + R2)
uv run python -m scraper scrape --periodo 2025-12 --download-docs --remote
```

### With document analysis

```bash
cd scripts

# 1. Classify the attachments (steps 1-2 in one headless command). It builds the
#    pending plan, materializes images from R2, and shells out to doc_transcribe per
#    page, recording each typed extraction to D1 (page_classifications). (To analyze a
#    subset, `mark-pending` those attachments first.)
uv run python -m analysis classify --periodo 2025-12

# 2. Merge classifications, run checks, get the summary (steps 3-5) — all write to D1
uv run python -m analysis apply-extractions --periodo 2025-12
uv run python -m analysis analyze --periodo 2025-12
uv run python -m analysis mismatches --periodo 2025-12

#    Run the whole analysis against production by adding --remote to each command.
```
