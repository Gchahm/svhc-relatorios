# Research: Preserve Raw Portal Values on Mirror Rows

No open `NEEDS CLARIFICATION` markers remained after specify/clarify. This file records the design
decisions and the codebase facts they rest on.

## Decision 1 — Two nullable TEXT columns on `entries`, not a JSON blob

- **Decision**: Add `raw_amount` (text, nullable) and `raw_description` (text, nullable) to the
  `entries` mirror table.
- **Rationale**: Queryable with plain SQL (`SELECT raw_amount …`), one-to-one with the audit-relevant
  derived fields (`amount`, `description`), and a clean Drizzle column mapping. A JSON `raw_row` blob
  would need parsing for every audit query and invites schema-less drift.
- **Alternatives considered**: single JSON `raw_row` column (rejected — not queryable, weaker
  contract); reuse `source_url` (rejected — different purpose). Subtotals/approvers raw text rejected
  as out of scope — the dispute-settling value concentrates on entry amount + description.

## Decision 2 — Keep `amount` REAL; defer integer centavos

- **Decision**: Do not change `entries.amount` (REAL). The raw text column is the audit anchor.
- **Rationale**: Migrating to integer centavos ripples through analysis Python (`scripts/analysis/*`),
  the TS/UI tolerance math (`src/lib/documents.ts`), reconciliation tolerances
  (`scripts/analysis/nf_groups.py`), and multiple read paths — a far larger, riskier change for no
  added audit fidelity once the verbatim string is stored. Centavos pairs with IMP-006 as a separate
  follow-up.

## Decision 3 — Tolerant `parse_brl`, row-skip failure policy

- **Decision**: `parse_brl(text) -> float | None`. Wrap the cleaning/`float()` in try/except; reject
  `NaN`/`±inf` via `math.isfinite`; return `None` on any failure. Callers decide severity:
  - **Entry rows** (`lancamentos.py` / `runner.py`): `None` ⇒ **skip the row**, log a warning quoting
    the raw text, and collect a non-fatal note.
  - **Demonstrativo report totals** (`demonstrativo.py`): `None` ⇒ **fatal** for that period (the
    report's 5 summary values are required — the existing "Missing financial data" guard already aborts
    a period that can't produce them; a None here raises a clear error, preserving today's behavior for
    a genuinely broken summary).
- **Rationale**: FR-005 wants a malformed *ledger cell* to fail only its row, not the period; the
  demonstrativo summary is a different, required artifact, so its hardening is "reject bogus values"
  (NaN/inf) rather than "skip". This keeps the mirror an exact mirror of *parseable* ledger rows.
- **Alternatives considered**: storing a sentinel `0.0` (rejected — silent data loss, SC-004); aborting
  the period (rejected — the bug being fixed).

## Decision 4 — Surface row-skips via the existing non-fatal run-note channel (IMP-002)

- **Decision**: `_scrape_periodo` collects per-row parse-skip notes and returns them; `run_scrape`
  appends them to `consistency_notes`, which `finally` already merges into `scrape_run.errors` WITHOUT
  flipping `status` to `error`.
- **Rationale**: Reuses the exact convention introduced by IMP-002 / issue #39 (`runner.py:323-327`):
  notes are queryable on the run row but do not fail an otherwise-successful period (FR-006). No new
  table or column for the notes.
- **Codebase fact**: `consistency_notes` is a plain list joined into `scrape_run["errors"]` in the
  `finally` block; adding parse-skip notes to it is a one-line append per period.

## Decision 5 — Raw description is pre-normalization, pre-prefix-strip

- **Decision**: `raw_description` = the cell text as extracted (`(await tds[1].inner_text()).strip()`),
  before `_normalize_whitespace` (runner.py:506) and before `_strip_fornecedor_prefix` (runner.py:540).
- **Rationale**: Most original recoverable form. The lancamento dict already holds `descricao`
  pre-normalization at extraction time; normalization happens later in `_scrape_periodo`. We capture
  the raw value at the point of extraction (or before the normalize loop overwrites it) into a new
  `descricao_raw` key, then map it to the entry row's `raw_description`.

## Codebase facts that constrain the implementation

- `parse_brl` lives in `scripts/scraper/extractors/demonstrativo.py:11-15` and is imported by
  `extractors/lancamentos.py:8` (used at lines 82, 119 for subtotals + entries).
- `_normalize_whitespace` is `runner.py:83`; the entry normalize loop is `runner.py:505-508`;
  `_strip_fornecedor_prefix` is `runner.py:540`.
- The entry row dict is assembled at `runner.py:556-570`; adding `raw_amount`/`raw_description` keys
  there is enough — `scripts/common/d1.py:upsert_sql` derives the column list from `rows[0].keys()`
  (d1.py:89), so a present key is inserted (the column must exist in D1).
- Re-scrape preservation (`scripts/scraper/preserve.py`, feature 027) only touches `file_path` +
  `content_hash` on `attachments`; it does not interact with the new `entries` columns. Reconciliation
  (`scripts/scraper/reconcile.py`, feature 028) diffs id sets only; a skipped row is simply absent from
  the fresh set — naturally handled.
- The mirror invariant (feature 026) requires that analysis never writes `entries`; the analysis
  pipeline already issues zero writes to `entries`, so adding columns it neither reads nor writes is
  safe.
- Migration generation: `pnpm db:generate` fails in the sandbox (ignored-build pnpm bug, MEMORY) —
  call `node_modules/.bin/drizzle-kit generate` directly. Next migration number is `0013`.
