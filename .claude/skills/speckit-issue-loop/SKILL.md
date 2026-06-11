---
name: speckit-issue-loop
description: >-
    Keep an automated implementation loop alive over the repo's open GitHub issues. Each pass picks up
    unclaimed issues and spawns one long-lived worker per issue that runs the speckit full pipeline
    (spec → plan → tasks → implement → PR) in its own git worktree; on later passes the loop relays PR
    review events (changes requested, approval) into that same worker via SendMessage, so the worker
    keeps its context from first spec to final merge while the loop itself stays thin. Designed to run
    as the recurring prompt of /loop, and to pair with pr-review-loop as the reviewer. Use for "work
    through our issue list with speckit", "start the issue implementation loop", or "implement open
    issues automatically".
argument-hint: "[--label <name>] [--max-workers N] [--once]"
allowed-tools: Bash, Agent, Read, Write
model: haiku
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-deny.py" --profile issue-orchestrator'
    - matcher: "Write"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/write-allow-state-dir.py"'
---

# Purpose

Be the thin, always-cheap dispatcher between GitHub state and per-issue workers. You never write a
spec, read a diff, or touch code — every issue is owned end-to-end (speckit full → PR → review
fixes → merge) by ONE context-isolated worker agent, and you only relay terse events to it. Your
context must stay flat enough to run for days.

# Keeping the loop alive

One pass per invocation; recurrence comes from `/loop`:

- **Standing loop:** `/loop 15m /speckit-issue-loop`. Stop by cancelling the loop.
- **Single pass:** invoke directly or with `--once`; after the pass, remind the user about
  `/loop 15m /speckit-issue-loop`. Never build your own sleep loop in Bash.
- Run **`/pr-review-loop` alongside it** — that loop posts the reviews this loop reacts to. The two
  together form the full cycle: implement → review → fix → approve → merge.

# State

Keep a small state file at `.cache/speckit-issue-loop/state.json` (create the directory if needed):

```json
{ "<issue-number>": { "status": "building|in-review|changes-requested|merged|error",
                      "pr": <pr-number|null>, "branch": "<branch|null>", "worker": "<agent-id|null>" } }
```

GitHub is the source of truth for issue/PR/review state; the file exists for two things only:
**dedupe** (never dispatch the same issue twice) and the **worker mapping**. Worker agent ids are
session-scoped — after a session restart they are stale; clear them and use the fallback in step 3.

# One pass

## 1. Reconcile state with GitHub

```bash
gh issue list --state open --json number,title,labels
gh pr list --state open --json number,headRefName,body,reviewDecision
```

- If `--label <name>` was given, keep only issues with that label.
- Load the state file. For every tracked issue: if its PR merged → mark `merged`, close out; if the
  issue was closed externally → drop it.
- An untracked open issue whose number already appears in an open PR body (`Closes #N`) is adopted as
  `in-review` (PR recorded, `worker: null`).

## 2. Dispatch new issues (bounded)

Concurrency cap: `--max-workers` (default **2**) issues in non-terminal state at once — workers share
the repo's remote, and more parallel feature branches than that invites conflicts.

For each unclaimed issue while under the cap, spawn ONE worker via the Agent tool with
`model: opus`, `isolation: "worktree"`, `run_in_background: true`:

> You own GitHub issue #<n> ("<title>") from spec to merged PR, in this dedicated worktree.
> 1. Read the issue: `gh issue view <n> --comments`.
> 2. Invoke the `speckit` skill with `full <one-line feature description derived from the issue>`
>    and follow it end-to-end (specify → clarify → plan → tasks → implement → pr). You are running
>    unattended: make reasonable assumptions instead of asking clarifying questions, and record them
>    in the spec. Include `Closes #<n>` in the PR body.
> 3. After the PR is open, follow the speckit pr phase's **review follow-up protocol**: you will
>    receive follow-up messages in this same context when reviews arrive — address requested changes
>    here, and merge on approval. Keep all heavy context (spec, diffs, review threads) in this
>    context; never echo it back.
> 4. Your final message now must be ONLY: `{"issue": <n>, "branch": "...", "pr": <num>, "status": "in-review"}`.

Record `status: building` + the worker id. When a worker's background result arrives, record its
`pr`/`branch` and move it to `in-review`.

## 3. Relay review events to existing workers

For each tracked PR in `in-review` or `changes-requested`, check the latest review state
(`gh pr view <pr> --json reviewDecision,reviews`). Then:

- **CHANGES_REQUESTED** (new since last pass) → `SendMessage` to the issue's worker:

  > Your PR #<pr> received a review requesting changes. Fetch the review body and inline comments
  > (`gh api repos/{owner}/{repo}/pulls/<pr>/reviews` and `/comments`), address every blocking
  > comment with commits on your branch, push, reply to each comment with what you changed, and
  > return ONLY `{"pr": <pr>, "status": "changes-pushed"}`.

  Mark `changes-requested` → back to `in-review` once it reports.

- **APPROVED** (the go-ahead) → `SendMessage` to the worker:

  > Your PR #<pr> was approved. Squash-merge it (`gh pr merge <pr> --squash --delete-branch`),
  > verify issue #<n> closed, and return ONLY `{"pr": <pr>, "status": "merged"}`.

  Mark `merged` on confirmation. The merge happens only after the reviewer's explicit approval —
  never merge an unapproved PR yourself, and never merge from the loop.

- **Worker gone** (`SendMessage` fails — e.g. new session): spawn a replacement worker
  (`model: opus`, `isolation: "worktree"`) with a catch-up prompt — check out the existing branch,
  read the issue, the spec under `specs/<branch>/`, and the full PR review thread, then handle the
  pending event as above. Update the worker id.

## 4. Report the pass

One header plus one line per tracked issue, e.g.:

```
pass complete — 4 tracked: 1 building, 2 in-review, 1 merged
#12 building   (worker w_abc, branch pending)
#15 in-review  PR #41 — changes requested, relayed to worker
#17 merged     PR #39 ✅
```

If a worker errors, mark `error` with the reason and report it; do not silently respawn more than
once per issue without surfacing the failure to the user.

# Boundaries

- **Dispatch and relay only**: never run speckit phases, read diffs, edit code, or post PR comments
  yourself — that is worker context.
- **One worker per issue, for life**: re-use the same worker via `SendMessage` for every event on
  that issue; spawn fresh only when the worker is unreachable.
- **Merging is approval-gated**: a PR merges only after a reviewer's APPROVED verdict, and only by
  its own worker.
- **Bounded concurrency**: respect `--max-workers`; queue the rest for future passes.
- Each pass terminates on its own; recurrence comes only from `/loop`.
