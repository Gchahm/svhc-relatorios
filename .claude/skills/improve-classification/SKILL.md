---
description: >-
    The thin orchestrator for the self-improving document-classification loop. Runs analyze → review each mismatch (true/false/transient/page-error) → for each false, delegate a human-gated speckit fix that opens a PR → re-run scoped to the affected documents → repeat until convergence, a max-iteration cap, or a no-progress guard halts it. It coordinates only: every heavy step (vision, review, fix) is a separate context-isolated worker, and all loop bookkeeping lives in the deterministic `loop-state` CLI — so this skill never holds page images, diffs, or large state. Use it for "run the classification improvement loop for 2025-12" or to drive the loop over a subset of attachments.
argument-hint: "[period] [--attachment-id <ids…>] [--entry-id <ids…>] [--max-iterations N] [--remote]"
allowed-tools: Task, Bash, Read, Glob, Skill
---

# Purpose

Drive the classification improvement loop and **coordinate only**. You delegate every heavy step to a
context-isolated worker and read back only terse JSON; you read the deterministic loop state from the
`loop-state` CLI rather than tracking it yourself. You **never** open page images, read diffs, run the
classification yourself, or merge a fix. Keeping your own context flat is a hard requirement (SC-002).

# Input

`$ARGUMENTS`: a period in `YYYY-MM` form (first token), optionally followed by:

- `--attachment-id <id…>` / `--entry-id <id…>` — restrict the **initial** scope to a subset.
- `--max-iterations N` — override the iteration cap (default 3). `--no-progress-window` (default 2)
  may also be forwarded to `loop-state`.
- `--remote` — run the whole loop against the production D1 + R2 (default local). Forward it to the
  `analyze-docs` delegation and to every `loop-state` command. (`record-verdict` writes only the local
  cache file and takes no `--remote`.)

Pipeline commands run from the repo's `scripts/` directory. The period data lives in Cloudflare D1
and images in R2; the verdicts/loop-state working file lives in the local cache (`../.cache/analysis/`).

# Loop

Track only two things across iterations: the current `iteration` (starts at 1) and the current
`scope` (initial subset, or the whole period). Everything else comes from `loop-state`.

### 1. Analyze (delegate)

Delegate to the **`analyze-docs`** agent (via the Task tool) for the current `scope` — pass the period
and any `--attachment-id`/`--entry-id`. It classifies, merges, runs checks, and returns ONLY a terse
mismatch summary. Keep that summary; do not expand it.

### 2. Loop state

```bash
cd scripts && uv run python -m analysis loop-state --periodo <period> --iteration <iteration> \
    [--max-iterations N] [--attachment-id <scope ids…>] [--entry-id <scope ids…>] [--remote]
```

Read `open`, `findings`, `data_quality`, `affected_attachment_ids`, and `terminate`. **If `terminate`
is non-null → go to Report.**

### 3. Review each open mismatch (delegate, in parallel)

For each mismatch in `open` that has no verdict yet this iteration, delegate the **`review-mismatch`**
agent (via the Task tool), **one mismatch per call**, dispatching many at once. Each returns a terse
verdict. Record each immediately:

```bash
cd scripts && uv run python -m analysis record-verdict --periodo <period> --iteration <iteration> --json '<verdict-json>'
```

### 4. Act on the verdicts

- **true** → leave as a finding. Never fix, never suppress (FR-010).
- **page-error** → leave as a data-quality item. Never fix.
- **transient** → add its document to the next iteration's `scope` for **one** re-classification
  attempt; do **not** delegate a fix.
- **false** → delegate the **`fix-mismatch`** worker (via the Task tool) with the mismatch + its
  `root_cause`. It opens a PR and **never merges**. Record the PR reference:

  ```bash
  cd scripts && uv run python -m analysis record-verdict --periodo <period> --iteration <iteration> \
      --json '{"mismatch_key":"<key>"}' --fix-branch <b> --fix-pr <url> --fix-status pr-open --fix-summary "<one line>"
  ```

### 5. Rescope and continue

```bash
cd scripts && uv run python -m analysis loop-state --periodo <period> [--remote]
```

Set `scope ← --attachment-id <affected_attachment_ids>` (re-runs after the first iteration are scoped —
FR-009/SC-006). If `terminate` is now non-null → Report. Otherwise `iteration ← iteration + 1` and go
back to step 1.

### Report (on termination)

Print, concisely: the `terminate.reason` (`converged` / `max-iterations` / `no-progress`) and detail,
the iteration count, the **findings** (true mismatches — the real audit results), the **data-quality**
items (page errors), and any still-open **false** mismatches with their fix PR urls. Never merge
anything.

# Boundaries (non-negotiable)

- **Delegation only**: vision, review, and fix each run in their own worker (Task tool). You handle
  ids + terse JSON; you never read page images, run `classify-*`/`apply-extractions`, or inspect
  diffs yourself.
- **Scoped re-runs**: after iteration 1, always pass `--attachment-id <affected_attachment_ids>`, never
  re-run the whole period.
- **Findings preserved**: every `true` mismatch is reported each iteration and never fixed.
- **Human-gated**: fixes may open PRs; you NEVER merge or push to `main`.
- **Always terminates**: stop the instant `loop-state` reports `terminate`. Do not invent your own
  stop logic — obey the deterministic signal.
- **Minimal state**: keep only `iteration` and `scope` in mind; re-read everything else from
  `loop-state`.
