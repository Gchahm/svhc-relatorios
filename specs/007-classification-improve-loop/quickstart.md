# Quickstart: Self-Improving Document-Classification Loop

Run the loop end-to-end on one period. Assumes a scraped period exists under `data/scrape/` with
downloaded page images (as `analyze-docs` already requires). All Python commands run from `scripts/`.

## 0. Prerequisites

- The US1 vision step works: `cd scripts && uv run python -m analysis mismatches --periodo 2025-12`
  returns a JSON list (after a prior classify + apply-extractions + analyze).
- `gh` is authenticated (only needed to exercise the fix worker's PR step).

## 1. One full pass, by hand (verifies US2 + the CLI)

```bash
# 1. Analyze (US1 — delegate to the analyze-docs agent, or run the chain directly):
cd scripts && uv run python -m analysis apply-extractions --periodo 2025-12
cd scripts && uv run python -m analysis analyze --periodo 2025-12
cd scripts && uv run python -m analysis mismatches --periodo 2025-12   # the working set

# 2. Initialise / inspect loop state:
cd scripts && uv run python -m analysis loop-state --periodo 2025-12 --iteration 1
#   → prints LoopState: open[], findings[], affected_document_ids[], terminate(null first pass)

# 3. Review one mismatch (US2): invoke the review-mismatch agent with a single mismatch row.
#    It returns e.g. {"mismatch_key":"…","verdict":"false","root_cause":{"area":"reading",…},"confidence":"high"}

# 4. Record the verdict (deterministic writer):
cd scripts && uv run python -m analysis record-verdict --periodo 2025-12 --iteration 1 \
    --json '{"mismatch_key":"2025-12|amount|<doc>|<entry>","verdict":"false","root_cause":{"area":"reading","hypothesis":"…"},"confidence":"high"}'

# 5. Recompute loop state — open set now reflects the verdict:
cd scripts && uv run python -m analysis loop-state --periodo 2025-12
```

**Expected**: `<period>.verdicts.json` now exists with the verdict and a refreshed `loop_state`; a
`true` verdict lands in `findings` (never fixed); a `false` lands in `open` with a root cause; a
`page-error` lands in `data_quality`.

## 2. The whole loop (US3)

```
/improve-classification 2025-12
```

**Expected flow**: analyze → loop-state → review each open mismatch (parallel `review-mismatch`) →
record verdicts → for each `false`, a `fix-mismatch` worker opens a PR (never merges) → re-run
`analyze-docs` **scoped to `affected_document_ids`** → repeat until `loop-state.terminate` is set.
The orchestrator prints findings, data-quality items, open false mismatches with their fix PR urls,
and the termination reason (`converged` / `max-iterations` / `no-progress`).

## 3. Acceptance checks (map to spec Success Criteria)

| Check | How | SC |
|-------|-----|----|
| Subset re-run is scoped | After iteration 1, confirm the re-run `docs-plan`/analyze only touches `affected_document_ids`, not the whole period | SC-001, SC-006 |
| Orchestrator context stays flat | The orchestrator only ever handles ids + terse JSON; no page images/diffs appear in its turns | SC-002 |
| Deterministic working set | Run `loop-state` twice on unchanged inputs → byte-identical output | SC-003 |
| Findings preserved | A known `true` mismatch is still reported at the end; never queued for a fix | SC-004 |
| Always terminates, never merges | Seed a false mismatch; confirm the loop opens a PR, never merges, and halts on convergence or the guard | SC-005 |

## 4. Reset

```bash
rm data/scrape/2025-12.verdicts.json   # start the loop fresh for the period
```
