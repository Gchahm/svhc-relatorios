---
name: speckit-issue-loop
description: >-
    Keep an automated implementation loop alive over the repo's open GitHub issues, working strictly
    ONE issue at a time. Each pass dispatches the next eligible issue (dependency-gated, priority,
    oldest first) to a single long-lived worker that runs the speckit full pipeline (spec → plan →
    tasks → implement → verify → PR) directly in the repo checkout — the full dev environment, local
    data included; on later passes the loop relays PR review events
    (changes requested, approval) into that same worker via SendMessage, so the worker keeps its
    context from first spec to final merge while the loop itself stays thin. The next issue starts
    only after the current one's PR merges. Designed to run
    as the recurring prompt of /loop, and to pair with pr-review-loop as the reviewer. Use for "work
    through our issue list with speckit", "start the issue implementation loop", or "implement open
    issues automatically".
argument-hint: "[--label <name>] [--once]"
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
gh issue list --state open --json number,title,labels,body
gh pr list --state open --json number,headRefName,body,reviewDecision
```

(`body` is needed for the dependency gate in step 2.)

- If `--label <name>` was given, keep only issues with that label.
- Load the state file. For every tracked issue: if its PR merged → mark `merged`, close out; if the
  issue was closed externally → drop it.
- An untracked open issue whose number already appears in an open PR body (`Closes #N`) is adopted as
  `in-review` (PR recorded, `worker: null`).

## 2. Dispatch the next issue (in order, strictly serial)

**One issue at a time.** If any tracked issue is in a non-terminal state (`building`, `in-review`,
`changes-requested`), dispatch **nothing** this pass — go to step 3 and service that issue. A new
issue is dispatched only when the previous one reached `merged` (or `error`, after surfacing it).
Sequential execution is the point: each feature lands on `main` before the next one builds on it, so
there are no parallel feature branches and no merge races.

**Order.** When dispatching, pick the FIRST unclaimed issue by, in priority order:

1. **Dependency gate** — an issue is *eligible* only when every issue it declares a dependency on is
   **closed** (i.e. its PR merged). Dependencies are declared in the issue body or a comment, one per
   line, case-insensitive: `Depends on #<n>` / `Blocked by #<n>` (also recognize a task-list line
   `- [ ] #<n>` as a blocker until checked/closed). An ineligible issue is never dispatched — report
   it as `waiting on #<n>` and re-check next pass; merging the blocker (which closes it via
   `Closes #<n>`) unblocks it automatically.
2. **Priority label** — `priority:1` before `priority:2`, etc.; unlabeled issues come after labeled
   ones.
3. **Ascending issue number** (oldest first) as the tiebreak — backlog order.

The rest of the backlog simply queues; it is reconsidered on the pass after the current issue merges.

For the dispatched issue, spawn ONE worker via the Agent tool with `model: opus`,
`run_in_background: true` — **no worktree isolation**: the loop is strictly serial and runs in a
dedicated container, so the worker owns the repo checkout directly and inherits the full dev
environment (local D1/R2 data in `.wrangler/`, `node_modules`, `.dev.vars`) for running and
verifying the app:

> You own GitHub issue #<n> ("<title>") from spec to merged PR, working directly in the repo
> checkout — it is yours alone for this issue's lifetime.
> 1. Read the issue: `gh issue view <n> --comments`.
> 2. Invoke the `speckit` skill with `full <one-line feature description derived from the issue>`
>    and follow it end-to-end (specify → clarify → plan → tasks → implement → pr). You are running
>    unattended: make reasonable assumptions instead of asking clarifying questions, and record them
>    in the spec. Include `Closes #<n>` in the PR body.
> 3. Before opening the PR, **verify the change in the running app against the local data** (the
>    `verify` / `ui-login` skills; the local D1 has prod-like data) and record what you verified in
>    the PR body, per the speckit pr phase.
> 4. After the PR is open, follow the speckit pr phase's **review follow-up protocol**: you will
>    receive follow-up messages in this same context when reviews arrive — address requested changes
>    here, and merge on approval (then return the checkout to `main` and pull). Keep all heavy
>    context (spec, diffs, review threads) in this context; never echo it back.
> 5. Your final message now must be ONLY: `{"issue": <n>, "branch": "...", "pr": <num>, "status": "in-review"}`.

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
  > verify issue #<n> closed, return the checkout to main (`git checkout main && git pull`) so the
  > next issue builds on the merged state, and return ONLY `{"pr": <pr>, "status": "merged"}`.

  Mark `merged` on confirmation. The merge happens only after the reviewer's explicit approval —
  never merge an unapproved PR yourself, and never merge from the loop.

- **Worker gone** (`SendMessage` fails — e.g. new session): spawn a replacement worker
  (`model: opus`, no isolation) with a catch-up prompt — check out the existing branch, read the
  issue, the spec under `specs/<branch>/`, and the full PR review thread, then handle the pending
  event as above. Update the worker id.

## 4. Report the pass

One header plus one line per tracked issue, e.g.:

```
pass complete — active: #15, queue: 2, done: 1
#17 merged     PR #39 ✅
#15 in-review  PR #41 — changes requested, relayed to worker
#18 waiting    on #15 (depends-on, not yet merged)
#19 queued     (next after #18 by issue order)
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
- **Strictly serial**: at most ONE issue in flight, ever. The next issue dispatches only after the
  current one's PR merges (or it is parked as `error`). Never spawn a second build worker because
  the current issue is "just waiting on review" — relaying its review events IS the work.
- Each pass terminates on its own; recurrence comes only from `/loop`.
