# Contract: `data/scrape/<period>.verdicts.json`

The per-period working file holding all verdicts and the deterministic loop state. Written ONLY by
the analysis CLI (`record-verdict`, `loop-state`); read by the orchestrator and (for evidence) never
by the workers. No D1 schema — this is a sibling of `<period>.json` / `<period>.extract-todo.json`.

## Shape

```jsonc
{
  "period": "2025-12",

  // Verdict records — latest-wins per mismatch_key; prior verdicts kept for history/no-progress.
  "verdicts": [
    {
      "mismatch_key": "2025-12|amount|<doc>|<entry>",
      "mismatch": { /* the Mismatch row copied verbatim from `mismatches` */ },
      "verdict": "false",                       // true | false | transient | page-error
      "root_cause": {                            // present iff verdict=false
        "area": "reading",                       // reading|rollup-precedence|grouping|reconciliation-tolerance|other
        "hypothesis": "…"
      },
      "confidence": "high",                      // high | medium | low
      "iteration": 1,
      "reviewed_at": "2026-06-08T00:00:00Z",     // stamped by record-verdict
      "fix": {                                    // present iff a fix worker ran for this key
        "branch": "008-fix-amount-rollup",
        "pr_url": "https://github.com/…/pull/42",
        "summary": "Prefer invoice valor_total over line subtotal in roll-up",
        "status": "pr-open"                       // pr-open | failed  (never "merged")
      }
    }
  ],

  // Deterministic loop bookkeeping — fully recomputed by `loop-state` (see data-model LoopState).
  "loop_state": {
    "period": "2025-12",
    "iteration": 2,
    "max_iterations": 3,
    "no_progress_window": 2,
    "open": ["2025-12|amount|<doc>|<entry>"],
    "findings": ["2025-12|vendor|<doc2>|<entry2>"],
    "data_quality": [],
    "affected_document_ids": ["<doc>"],
    "history": [
      { "iteration": 1, "open_count": 3, "open_keys": ["…","…","…"], "false_count": 2,
        "fixes": [ { "mismatch_key": "…", "pr_url": "…", "status": "pr-open" } ] }
    ],
    "terminate": null    // or { "reason": "converged|max-iterations|no-progress", "detail": "…" }
  }
}
```

## Rules

- **Single writer**: only `record-verdict` (appends/updates a verdict) and `loop-state` (recomputes
  `loop_state`) write this file. Agents never edit it.
- **Latest-wins, history-preserving**: `record-verdict` upserts by `mismatch_key` for the current
  iteration; earlier iterations' verdicts remain discoverable (kept in `history`/prior records) so
  the no-progress guard can see verdict flips.
- **Idempotent**: recording the same verdict twice in one iteration is a no-op; re-running
  `loop-state` on unchanged inputs yields the same `loop_state` (SC-003).
- **Absent file** ⇒ fresh loop: iteration 1, empty `verdicts`, `terminate: null`.
- **`status` is never `merged`** — the loop never merges (FR-008/SC-005).
