---
description: >-
    The thin orchestrator for the self-improving document-classification loop. Runs analyze → review each mismatch (true/false/transient/page-error) → for each false, delegate a human-gated speckit fix that opens a PR → mark the affected attachments pending in D1 and re-run the period → repeat until convergence, a max-iteration cap, or a no-progress guard halts it. It coordinates only: every heavy step (vision, review, fix) is a separate context-isolated worker, and all loop bookkeeping lives in the deterministic `loop-state` CLI — so this skill never holds page images, diffs, or large state. Use it for "run the classification improvement loop for 2025-12".
argument-hint: "[period] [--max-iterations N] [--remote]"
allowed-tools: Task, Bash, Read, Glob, Skill
---

# Purpose

Drive the classification improvement loop and **coordinate only**. You delegate every heavy step to a
context-isolated worker and read back only terse JSON; you read the deterministic loop state from the
`loop-state` CLI rather than tracking it yourself. You **never** open page images, read diffs, run the
classification yourself, or merge a fix. Keeping your own context flat is a hard requirement (SC-002).

# Input

`$ARGUMENTS`: a period in `YYYY-MM` form (first token), optionally followed by:

- `--max-iterations N` — override the iteration cap (default 3). `--no-progress-window` (default 2)
  may also be forwarded to `loop-state`.
- `--remote` — run the whole loop against the production D1 + R2 (default local). Forward it to the
  `analyze-docs` delegation, `mark-pending`, and every `loop-state` command. (`record-verdict` writes
  only the local cache file and takes no `--remote`.)

There is **no id-scoping argument**: which attachments get (re)classified is controlled in the
database (the pending set, `attachments.classified_at IS NULL`). You re-queue work between iterations
by marking attachments pending via `mark-pending` (step 5), not by passing id lists.

Pipeline commands run from the repo's `scripts/` directory. The period data lives in Cloudflare D1
and images in R2; the verdicts/loop-state working file lives in the local cache (`../.cache/analysis/`).

# Loop

Track only the current `iteration` (starts at 1). Everything else comes from `loop-state` and D1 state.

### 1. Analyze (delegate)

Delegate to the **`analyze-docs`** agent (via the Task tool) for the **period** (pass `--remote` if
applicable; never id flags). It classifies the period's *pending* attachments, merges, runs checks, and
returns ONLY a terse mismatch summary. Keep that summary; do not expand it. (On iteration 1 the pending
set is everything; on later iterations it is exactly the attachments you re-queued in step 5.)

### 2. Loop state

```bash
cd scripts && uv run python -m analysis loop-state --periodo <period> --iteration <iteration> \
    [--max-iterations N] [--remote]
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
- **transient** → its mismatch stays open, so its attachment is already in
  `affected_attachment_ids` and will be re-queued in step 5 for **one** re-classification attempt; do
  **not** delegate a fix.
- **false** → delegate the **`fix-mismatch`** worker (via the Task tool) with the mismatch + its
  `root_cause`. It opens a PR and **never merges**. Record the PR reference:

  ```bash
  cd scripts && uv run python -m analysis record-verdict --periodo <period> --iteration <iteration> \
      --json '{"mismatch_key":"<key>"}' --fix-branch <b> --fix-pr <url> --fix-status pr-open --fix-summary "<one line>"
  ```

### 5. Re-queue and continue

```bash
cd scripts && uv run python -m analysis loop-state --periodo <period> [--remote]
```

If `terminate` is now non-null → Report. Otherwise **mark the affected attachments pending in D1** so
the next iteration re-classifies exactly them (re-runs after the first iteration are scoped via DB
state, not id flags — FR-009/SC-006):

```bash
cd scripts && uv run python -m analysis mark-pending --periodo <period> \
    --attachment-id <affected_attachment_ids…> [--remote]
```

Then `iteration ← iteration + 1` and go back to step 1. (If `affected_attachment_ids` is empty,
`terminate` will already be set, so you will have gone to Report.)

### Report (on termination)

Print, concisely: the `terminate.reason` (`converged` / `max-iterations` / `no-progress`) and detail,
the iteration count, the **findings** (true mismatches — the real audit results), the **data-quality**
items (page errors), and any still-open **false** mismatches with their fix PR urls. Never merge
anything.

# Boundaries (non-negotiable)

- **Delegation only**: vision, review, and fix each run in their own worker (Task tool). You handle
  ids + terse JSON; you never read page images, run `classify-*`/`apply-extractions`, or inspect
  diffs yourself.
- **Scoped re-runs via D1**: after iteration 1, re-queue only `affected_attachment_ids` with
  `mark-pending`, then re-run the period; never widen the scope by re-classifying already-classified
  attachments. The pending set in D1 is the scope.
- **Findings preserved**: every `true` mismatch is reported each iteration and never fixed.
- **Human-gated**: fixes may open PRs; you NEVER merge or push to `main`.
- **Always terminates**: stop the instant `loop-state` reports `terminate`. Do not invent your own
  stop logic — obey the deterministic signal.
- **Minimal state**: keep only `iteration` in mind; re-read everything else from `loop-state` and D1.
