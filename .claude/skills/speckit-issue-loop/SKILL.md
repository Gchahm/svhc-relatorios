---
name: speckit-issue-loop
description: >-
    Keep an automated implementation loop alive over the repo's open GitHub issues, working strictly
    ONE issue at a time. Each pass dispatches the next eligible issue (dependency-gated, priority,
    oldest first) to a single long-lived worker that runs the speckit full pipeline (spec → plan →
    tasks → implement → verify → PR) directly in the repo checkout — the full dev environment, local
    data included — and watches its own PR via a background watcher, addressing reviews and merging
    on approval in its own context. The loop never relays review events: each pass it only checks
    that a worker is alive on the active issue (respawning a catch-up worker if not) and dispatches
    the next issue once the current one merges. Designed to run
    as the recurring prompt of /loop, and to pair with pr-review-loop as the reviewer. Use for "work
    through our issue list with speckit", "start the issue implementation loop", or "implement open
    issues automatically".
argument-hint: "[issue-numbers in work order…] [--label <name>] [--once]"
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

Be the thin, always-cheap dispatcher and babysitter. You never write a spec, read a diff, touch
code, or track review state — every issue is owned end-to-end (speckit full → PR → review fixes →
merge) by ONE context-isolated worker agent that **watches its own PR** (the speckit pr phase's
background watcher). Your whole job per pass: reconcile with GitHub, make sure a worker is alive on
the active issue, dispatch the next issue when the previous one merged. Your context must stay flat
enough to run for days.

# Keeping the loop alive

One pass per invocation; recurrence comes from `/loop`:

- **Standing loop:** `/loop 15m /speckit-issue-loop`. Stop by cancelling the loop.
- **Single pass:** invoke directly or with `--once`; after the pass, remind the user about
  `/loop 15m /speckit-issue-loop`. Never build your own sleep loop in Bash.
- Run **`/pr-review-loop` alongside it** — that loop posts the reviews this loop reacts to. The two
  together form the full cycle: implement → review → fix → approve → merge.

# Scope (the issue list)

`$ARGUMENTS` may carry an explicit, **ordered** list of issue numbers (space- or comma-separated,
e.g. `41 40 44 46 45` or `41, 40, 44, 46, 45`): work EXACTLY these issues, in EXACTLY this order —
the list replaces the label filter and the priority/number ordering (the dependency gate still
applies: a listed issue whose declared blocker is open is held as `waiting`). Persist the list as
`scope` in the state file on the first pass so every later pass works the same queue. No arguments →
scope is all open issues (or `--label`-filtered), ordered by the default rules in step 2.

**Nothing in scope is ever silently dropped**: every scoped issue appears in every pass report with
a status (`active` / `queued` / `waiting` / `merged` / `error` / `closed-externally`), and the counts
in the report header must add up to the scope size.

# State

Keep a small state file at `.cache/speckit-issue-loop/state.json` (create the directory if needed):

```json
{ "scope": [41, 40, 44, 46, 45],
  "issues": { "<issue-number>": { "status": "building|in-review|merged|error",
                                  "pr": <pr-number|null>, "branch": "<branch|null>", "worker": "<agent-id|null>" } } }
```

GitHub is the source of truth for issue/PR/review state; the file exists for two things only:
**dedupe** (never dispatch the same issue twice) and the **worker mapping**. Worker agent ids are
session-scoped — after a session restart they are stale; clear them and use the fallback in step 3.

# One pass

## 1. Reconcile state with GitHub

```bash
gh issue list --state open --json number,title,labels,body
gh pr list --state open --json number,headRefName,body
```

(Open/merged is all you may know about a PR — review state is the worker's business, and the guard
hook blocks you from reading it.)

(`body` is needed for the dependency gate in step 2.)

- If `--label <name>` was given, keep only issues with that label.
- Load the state file. For every tracked issue: if its PR merged → mark `merged`, close out; if the
  issue was closed externally → drop it.
- An untracked open issue whose number already appears in an open PR body (`Closes #N`) is adopted as
  `in-review` (PR recorded, `worker: null`).

## 2. Dispatch the next issue (in order, strictly serial)

**One issue at a time.** If any tracked issue is in a non-terminal state (`building`, `in-review`),
dispatch **nothing** this pass — go to step 3 and check on that issue's worker. A new
issue is dispatched only when the previous one reached `merged` (or `error`, after surfacing it).
Sequential execution is the point: each feature lands on `main` before the next one builds on it, so
there are no parallel feature branches and no merge races.

**Order.** When dispatching, pick the FIRST unclaimed issue from the scope. With an explicit scope
list, the list order IS the order (only the dependency gate below can hold an issue back). Without
one, sort by, in priority order:

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
> 4. After the PR is open, follow the speckit pr phase's **Step 7 watcher protocol**: arm the
>    background PR watcher and service it yourself — address requested changes, push, re-arm; on
>    approval squash-merge, return the checkout to `main` and pull. Nobody relays review events to
>    you; the watcher is how you wait. Keep all heavy context (spec, diffs, review threads) in this
>    context; never echo it back.
> 5. Your final message — sent only when the PR merged or you are unrecoverably stuck — must be
>    ONLY: `{"issue": <n>, "pr": <num>, "status": "merged"}` (or `"status": "error", "reason": "..."`).

Record `status: building` + the worker id. The PR number is learned from GitHub on a later pass
(step 1 adopts the open PR carrying `Closes #<n>`); the worker stays silent until merge.

## 3. Babysit the active worker (heartbeat liveness — never review state)

The worker watches its own PR (speckit pr Step 7 watcher) — the loop does NOT read reviews, relay
events, or chase `reviewDecision`. Its only concern: **is the active PR actually being watched?**
Never assume it; **check the heartbeat** the worker's watcher touches every ~90s:

```bash
HB=".cache/pr-watcher/pr-<pr>.heartbeat"
AGE=$(( $(date +%s) - $(stat -c %Y "$HB" 2>/dev/null || echo 0) ))
```

- **Worker reported in** (its background completion arrived since last pass): `status: merged` →
  close out, the next pass dispatches the next issue. `status: error` → mark `error`, surface it in
  the pass report, do not auto-respawn more than once.
- **Heartbeat fresh** (age < ~10 min): worker alive and watching — leave it alone; a quiet worker
  is the normal state. Report `worker alive (heartbeat <age>s)`.
- **Heartbeat stale or missing** (and the PR is still open): the PR is **unwatched** — a pending
  approval would sit unmerged forever. This is the failure mode this step exists for; do NOT report
  "worker watching" on faith. Respawn immediately: spawn a catch-up worker (`model: opus`, no
  isolation, `run_in_background: true`) — check out the existing feature branch, read the issue,
  the spec under `specs/<branch>/`, and the full PR review thread (anything already addressed),
  then **resume the speckit pr Step 7 watcher protocol**. Step 7's "settle the existing thread"
  rule is critical for catch-up: classify reviews **body-first** — a self-authored `COMMENTED`
  review starting `VERDICT: approve` IS the formal approval in this single-account setup (GitHub
  forbids self-approval, so a state of `APPROVED` may never appear) — and a waiting approval at the
  current head means merge immediately, before arming any watcher. Update the worker id.
  (Grace: skip the staleness check for the first ~5 min after spawning a worker — it is still
  building/arming.)
- **Active issue has no PR yet** (`building`): the heartbeat doesn't exist yet; rely on the worker's
  completion notification, and if the worker completed without ever opening a PR, respawn with the
  catch-up prompt.

## 4. Report the pass

One header plus one line per tracked issue, e.g.:

One line for EVERY issue in scope — never omit one — and a header whose counts sum to the scope
size, e.g. (scope `41 40 44 46 45`):

```
pass complete — scope 5: active 1, queued 3, merged 1
#41 in-review  PR #58 — worker alive (heartbeat 45s)
#40 queued     (next, by scope order)
#44 queued
#46 queued
#45 merged     PR #57 ✅
```

If a worker errors, mark `error` with the reason and report it; do not silently respawn more than
once per issue without surfacing the failure to the user.

# Boundaries

- **Dispatch and babysit only**: never run speckit phases, read diffs, read review state, edit code,
  or post PR comments yourself — the worker watches and services its own PR.
- **One worker per issue, for life**: the worker runs from spec to merge in one context. SendMessage
  is for liveness nudges only; spawn a catch-up replacement only when the worker is dead.
- **Merging is approval-gated**: a PR merges only after a reviewer's APPROVED verdict, and only by
  its own worker.
- **Strictly serial**: at most ONE issue in flight, ever. The next issue dispatches only after the
  current one's PR merges (or it is parked as `error`). Never spawn a second build worker because
  the current issue is "just waiting on review" — relaying its review events IS the work.
- Each pass terminates on its own; recurrence comes only from `/loop`.
