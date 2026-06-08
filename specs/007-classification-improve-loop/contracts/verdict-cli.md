# Contract: `record-verdict` & `loop-state` CLI commands

Two new deterministic subcommands of `python -m analysis` (registered in `scripts/analysis/__main__.py`,
implemented in `scripts/analysis/verdicts.py`). Stdlib only. They are the **only** writers of
`<period>.verdicts.json`. No model calls, no network — pure file IO + arithmetic, so the loop's
bookkeeping is reproducible (SC-003) and termination is provable (SC-005).

## `record-verdict`

Upsert one verdict (produced by the `review-mismatch` agent) into the verdicts file.

```bash
cd scripts && uv run python -m analysis record-verdict --periodo <p> --iteration <n> --json '<verdict-json>'
# optionally attach a fix reference after the fix worker runs:
cd scripts && uv run python -m analysis record-verdict --periodo <p> --iteration <n> \
    --json '{"mismatch_key":"…"}' --fix-branch <b> --fix-pr <url> --fix-status pr-open --fix-summary "…"
```

| Arg | Required | Meaning |
|-----|----------|---------|
| `--periodo` | yes | period `YYYY-MM` |
| `--iteration` | yes | loop iteration (≥1) the verdict belongs to |
| `--json` | yes | the verdict object from the review agent (`mismatch_key`, `verdict`, `root_cause?`, `confidence`); the full `mismatch` row may be included for audit |
| `--data-dir` / `-d` | no | default `../data/scrape` |
| `--fix-*` | no | attach a `FixProposal` reference to an existing verdict (status ∈ `pr-open`/`failed`, never `merged`) |

**Behavior**: stamps `reviewed_at`; validates `verdict` ∈ enum and that `root_cause` is present iff
`verdict=false`; upserts latest-wins by `mismatch_key`; idempotent within an iteration. Exits non-zero
on schema violation (e.g. `false` without `root_cause`, or `--fix-status merged`).

## `loop-state`

Recompute the deterministic `loop_state` block by joining current `mismatches` with stored verdicts,
write it back, and print it as JSON for the orchestrator.

```bash
cd scripts && uv run python -m analysis loop-state --periodo <p> \
    [--iteration <n>] [--max-iterations 3] [--no-progress-window 2] \
    [--document-id <ids…>] [--entry-id <ids…>]
```

| Arg | Required | Meaning |
|-----|----------|---------|
| `--periodo` | yes | period |
| `--iteration` | no | record/advance to this iteration (default: infer next) |
| `--max-iterations` | no | cap (default 3) |
| `--no-progress-window` | no | consecutive-iteration window for the no-progress guard (default 2) |
| `--document-id` / `--entry-id` | no | restrict the join to a subset (matches `mismatches` scoping) |
| `--data-dir` / `-d` | no | default `../data/scrape` |

**Output** (stdout, also persisted into the file): the `LoopState` object from `data-model.md`,
including `open`, `findings`, `data_quality`, `affected_document_ids`, `history`, and `terminate`.

**Determinism / termination** (the whole point):
- `affected_document_ids` = documents referenced by still-`open` mismatches **only**, used to scope
  the next `analyze-docs` re-run (SC-006). Converged documents drop out; transient verdicts keep their
  mismatch open, so their documents stay included until resolved.
- `terminate` is set when: no `open` `false`/`transient`-unresolved items remain (`converged`);
  `iteration >= max_iterations` (`max-iterations`); or over the last `no_progress_window` iterations
  the `open_keys` set did not shrink or a key flipped verdict / recurred (`no-progress`).
- Given identical `<period>.json` + `verdicts.json`, output is byte-stable.

## Backward compatibility

Purely additive: new subcommands and a new module; `docs-plan`/`apply-extractions`/`analyze`/
`mismatches` are unchanged. Absent verdicts file ⇒ treated as a fresh loop.
