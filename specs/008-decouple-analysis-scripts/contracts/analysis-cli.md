# Contract: Analysis command surface

These four operations are the analysis CLI. The refactor moves **how they're invoked** (entrypoint),
not **what they do or their arguments**. Any caller (the `classify-period` skill, the `analyze-docs`
agent, docs, CI) depends only on this surface.

## Invocation forms

- **Today (pre-P2):** `uv run python -m scraper <command> [flags]` (from `scripts/`).
- **After P2/P3:** the dedicated analysis entrypoint — per-command console scripts
  (`uv run <command> [flags]`) plus a `python -m scraper.analise <command>` (P2) /
  `python -m analysis <command>` (P3) dispatcher. Same command names, same flags.

## Commands

### `docs-plan`

Writes the work manifest `data/scrape/<period>.extract-todo.json` (selection + NF grouping).

| Flag | Meaning |
|------|---------|
| `--periodo <p…>` | period(s), `YYYY-MM` |
| `--data-dir, -d <path>` | period-JSON directory (default `../data/scrape`) |
| `--min-amount <float>` | only entries ≥ this amount |
| `--limit <int>` | max documents to plan |
| `--reanalyze` | re-plan already-analyzed documents |
| `--document-id <id…>` | only these documents (implies re-analysis of them) |
| `--entry-id <id…>` | only documents for these entries (implies re-analysis) |

### `apply-extractions`

Reads each page's `<image>.classify.json`, runs the deterministic roll-up / reconciliation / fan-out
/ validation, writes `document_analyses` into the period JSON.

| Flag | Meaning |
|------|---------|
| `--periodo <p…>` | period(s) (default: all periods with a manifest) |
| `--data-dir, -d <path>` | period-JSON directory |

### `analyze`

Runs the financial / consistency / fraud checks; writes `alerts` into the period JSON.

| Flag | Meaning |
|------|---------|
| `--periodo <p…>` | period(s) |
| `--data-dir, -d <path>` | period-JSON directory |

### `mismatches`

Prints (stdout) a terse JSON list of classification mismatches; read-only.

| Flag | Meaning |
|------|---------|
| `--periodo <p…>` | period(s) |
| `--data-dir, -d <path>` | period-JSON directory |
| `--document-id <id…>` | scope to these documents |
| `--entry-id <id…>` | scope to these entries |

Mismatch item shape: `{ period, document_id, entry_id, kind, … }` where `kind` ∈
`amount | vendor | date | page-error | duplicate_billing`, plus the ledger-vs-extracted values for
that kind (e.g. `ledger_amount`/`extracted_amount`).

## Invariant

The command names, flags, and behavior above are **stable across the entrypoint move** (P2/P3). The
only thing changing is that analysis no longer requires the scraper/Playwright environment to invoke
these. The scraping commands (`scrape`, `download-docs`) remain on the scraper CLI and are out of
this surface.
