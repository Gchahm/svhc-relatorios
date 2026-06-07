# Quickstart: Decoupled analysis pipeline

After this refactor the analysis pipeline runs **without** the Playwright/scraping stack. The command
surface is unchanged (see `contracts/analysis-cli.md`); only the entrypoint and dependencies change.

## Running analysis (post-P1)

```bash
cd scripts
# No Playwright needed for these — they import only the stdlib analysis pipeline:
uv run python -m scraper docs-plan --periodo 2025-12
uv run python -m scraper apply-extractions --periodo 2025-12
uv run python -m scraper analyze --periodo 2025-12
uv run python -m scraper mismatches --periodo 2025-12
```

After P2/P3 the same operations are also available via the dedicated analysis entrypoint
(`uv run apply-extractions …` / `python -m analysis apply-extractions …`).

## Verification (behavior-preserving)

### 1. Analysis imports without Playwright (SC-001)

```bash
cd scripts
# Should succeed even if Playwright is not installed:
python3 -c "import scraper.analise.extractions, scraper.analise.documentos, scraper.analise.checks.advanced; print('OK: no Playwright needed')"
# (post-P3) python3 -c "import analysis.extractions; print('OK')"
```

Before P1, importing the CLI (`python3 -c "import scraper.__main__"`) fails without Playwright; after
P1 the analysis commands run regardless.

### 2. `det_id` byte-stability (FR-004 / SC-003)

```bash
cd scripts
python3 -c "
from scraper.utils import det_id, NAMESPACE   # (post-P3: from common import det_id, NAMESPACE)
assert det_id('doc_analysis', 'abc') == det_id('doc_analysis', 'abc')
print('NAMESPACE', NAMESPACE)
print('sample', det_id('doc_analysis', 'abc'))
"
```

Record the sample ids before the `utils`→`common` move and re-run after — they MUST be identical.

### 3. Output equality on a sample period (SC-002)

Re-run the existing synthetic harness, which feeds fixed `.classify.json` values through the
deterministic merge + checks and asserts the resulting `document_analyses` / reconciliation /
`duplicate_billing`:

```bash
cd scripts
uv run python ../specs/006-analyze-docs-agent/fixtures/build_and_verify.py   # all assertions pass
```

For a real period, diff `document_analyses`/`alerts` and the `mismatches` output before vs. after the
refactor — they MUST be byte-equivalent for identical inputs.

### 4. Scraper + import unaffected (SC-004)

```bash
cd scripts && uv run python -m scraper scrape -h           # imports cleanly (Playwright present)
cd .. && node scripts/import-to-d1.mjs --dry-run            # unchanged SQL for a sample
```

## Confirm no stale references (SC-006)

After P2/P3, every skill / agent / doc references the analysis entrypoint, not the scraper CLI:

```bash
grep -rn "scraper docs-plan\|scraper apply-extractions\|scraper analyze\|scraper mismatches" \
  .claude/ scripts/README.md CLAUDE.md   # expect: none (all point at the analysis entrypoint)
```
