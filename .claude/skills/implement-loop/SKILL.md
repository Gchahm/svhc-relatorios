---
name: implement-loop
description: >-
    Self-starting automated implementation loop over the repo's open GitHub issues, ONE at a time.
    Unlike the older speckit-issue-loop you do NOT wrap it in `/loop` — this skill arms its own
    recurring schedule (CronCreate) on first run and disarms it (CronDelete) when the queue drains.
    A deterministic decision script (`scripts/loop_state.py`) reconciles with GitHub and returns the
    single action to take each pass; the skill just executes it — dispatch the next eligible issue
    (dependency-gated, priority, oldest first) to a long-lived `developer` agent that runs speckit
    full → verify → PR → watch → merge, or resume a worker that died. The prompts it hands the
    worker live in `templates/`. Use for "start the implement loop", "work through our issues
    automatically", or "implement open issues".
argument-hint: "[issue-numbers in work order…] [--label <name>] [--once] [--every <Nm>]"
allowed-tools: Bash, Agent, Read, CronCreate, CronList, CronDelete, TaskStop, SendMessage
model: haiku
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-deny.py" --profile issue-orchestrator'
---

# Purpose

Be the thin, always-cheap executor of a deterministic decision. You never write a spec, read a diff,
touch code, reconcile state by hand, or track review state: a script (`scripts/loop_state.py`) owns
all the bookkeeping and decides the ONE action each pass, and every issue is owned end-to-end by ONE
context-isolated `developer` agent that watches and merges its own PR. Your whole job per pass: make
sure the recurring schedule is armed, ask the script what to do, and do exactly that. Your context
must stay flat enough to run for days.

Two things make this different from the old `speckit-issue-loop`:

1. **Self-starting** — you arm a recurring `CronCreate` job yourself, so the user runs
   `/implement-loop` once, not `/loop … /speckit-issue-loop`.
2. **Self-healing** — when a worker dies/hangs (the script returns `resume`) you reap it with
   `TaskStop` and respawn a catch-up `developer` from durable state; when a worker finishes but hangs
   without replying (the script returns `stop_agent`) you `TaskStop` the zombie and proceed. Both use
   the agent id the script already tracks — no agent-teams flag needed. (An optional `SendMessage`
   fast-path can resume a live worker in place when teams are enabled.)

# Variables

- `DECISION_SCRIPT`: `.claude/skills/implement-loop/scripts/loop_state.py` — the brain. It reconciles
  with GitHub, owns `STATE_FILE` (its only writer), and prints the action JSON. It is stdlib-only and
  lives outside the `scripts/` uv project, so always run it via uv with `--no-project`:
  `uv run --no-project python "$CLAUDE_PROJECT_DIR/$DECISION_SCRIPT" <subcommand> …` (never bare
  `python`/`python3` — repo convention).
- `STATE_FILE`: `.cache/implement-loop/state.json` — written ONLY by the script; you never edit it.
- `HEARTBEAT`: `.cache/implement-loop/heartbeat-<issue>` — **per-issue**; the `developer` worker
  touches its own file ~every 60s for its whole life, and the script reads its age to tell whether
  that worker is alive (see step 2 `resume`). Per-issue (not one shared file) so a finished-but-stuck
  worker can't keep the next issue's worker looking alive.
- `INTERVAL`: cron expression for the recurring pass. Default `*/14 * * * *` (~every 14 min).
  `--every <Nm>` overrides (e.g. `--every 10m` → `*/10 * * * *`).
- `WORKER_PROMPT`: `templates/dispatch-prompt.md` — the per-issue task handed to a fresh worker.
- `CATCHUP_PROMPT`: `templates/catchup-prompt.md` — the task handed to a resumed/respawned worker.
- `STATE_SHAPE`: `templates/state.json` — documents the shape the script writes: a `scope` list, a
  per-issue `status` (`queued | building | in-review | merged | closed | error`), and `current_work`
  (`{issue, agent, spawned_at, branch, pr, restarts}`) — the active worker.

GitHub is the source of truth; the script reads it read-only (issue/PR state only — never review
state, which is the worker's business and the `issue-orchestrator` Bash guard forbids).

# Instructions

- **Execute the decision; never second-guess it.** The script returns one action per pass — your job
  is to carry it out and report. Do not reconcile, re-order, or read GitHub yourself.
- **One worker per issue, strictly serial.** At most ONE issue in flight, ever — the script enforces
  this (it only returns `dispatch` when no `current_work` exists). No parallel branches, no races.
- **Merging is approval-gated** by the global merge hook; the worker merges only after an APPROVED
  (or `VERDICT: approve`) review at the current head. Run `/pr-review-loop` alongside this loop so
  reviews actually get posted — together: implement → review → fix → approve → merge.
- **Prompts come from `templates/`** — read the template file, substitute its `{{…}}` placeholders
  from the action's fields, and pass the result as the worker's prompt. Never inline a worker prompt.
- **Never edit `STATE_FILE` or build a `sleep` loop** — the script owns state, the cron is the timer.

# Workflow

One pass per invocation. Each pass:

## 0. Arm the schedule (unless `--once`)

Ensure the recurring job exists — idempotent, so this both starts the loop on the first run and
renews it before the 7-day cron expiry:

- `CronList`. If no job whose prompt is `/implement-loop …` exists, `CronCreate` with
  `{ cron: INTERVAL, prompt: "/implement-loop <original args minus --once>", recurring: true,
  durable: true }`, and tell the user the loop is armed (recurring crons auto-expire after 7 days,
  but each pass re-arms, so it renews while issues remain).
- With `--once`: do NOT arm — run a single pass, then remind the user they can start the standing
  loop with `/implement-loop`.

## 1. Ask the script what to do

```bash
uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/skills/implement-loop/scripts/loop_state.py" next $ARGUMENTS
```

It prints one JSON object: `{ "action": …, "report": [lines…], …fields }`. **Print the `report`
lines** as the pass report. Then act on `action`:

**First, honor `stop_agent` if present** (it can appear on `dispatch`/`wait`/`done`): a previous
worker's issue is closed (its work merged) but it still looks alive — it finished but is stuck and
never replied. STOP that zombie before doing anything else with **`TaskStop`** — a background
`developer` spawn is a `local_agent` task whose `task_id` IS the agent id the script returns, so:
`TaskStop(task_id=<stop_agent>)`. This is a hard kill, needs no permission and no agent-teams flag
(verified). Killing it also stops its heartbeat loop. This is the fix for "the worker finished but
the loop didn't proceed."

## 2. Execute the action

- **`dispatch`** (fields `issue`, `title`): read `templates/dispatch-prompt.md`, substitute
  `{{ISSUE_NUMBER}}`=`issue` and `{{ISSUE_TITLE}}`=`title`. Spawn ONE worker with the **Agent** tool:
  `subagent_type: "developer"`, `run_in_background: true` (no worktree isolation — serial loop,
  dedicated container, the worker owns the checkout). Capture the returned agent id and record it:
  `uv run --no-project python "$CLAUDE_PROJECT_DIR/$DECISION_SCRIPT" dispatched --issue <issue> --agent <id>`.
- **`resume`** (fields `issue`, `title`, `branch`, `pr`, `agent`): the worker is not running but the
  issue is still open — it died (or hung). Read `templates/catchup-prompt.md`, substitute
  `{{ISSUE_NUMBER}}` / `{{ISSUE_TITLE}}` / `{{BRANCH}}` / `{{PR}}`. Then:
  - **First reap the old worker**: `TaskStop(task_id=<agent>)` (harmless no-op if it's already gone)
    so a hung-but-not-fully-dead worker can't linger or keep touching its heartbeat.
  - **Resume fast-path** (optional) — if `agent` is from THIS session and `SendMessage` is available
    (agent teams, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), `SendMessage` the substituted body to
    `agent` to continue in place (preserves its full context — a stopped subagent auto-resumes).
    Record `… resumed --agent <agent>`. (Skip the `TaskStop` above when taking this path.)
  - **Respawn (default)** — spawn a fresh `developer` (Agent, `run_in_background: true`) with the
    substituted catch-up prompt; capture the new id and record
    `uv run --no-project python "$CLAUDE_PROJECT_DIR/$DECISION_SCRIPT" resumed --agent <new-id>`.
- **`wait`**: a worker is alive, or the next issue is dependency-blocked. Do nothing — the report
  already says why.
- **`error`** (field `issue`): the issue exceeded the restart cap; the script already parked it and
  cleared `current_work`. Surface `reason` to the user; the next pass moves on.
- **`done`**: every scoped issue is terminal. `CronList` → `CronDelete` the loop's job(s), and report
  the loop complete.

# Examples

- `/implement-loop 41 40 44 46 45` — arm the loop and work exactly those issues, in that order.
- `/implement-loop --label backlog --every 10m` — work all open `backlog` issues, pass every 10 min.
- `/implement-loop --once` — run a single pass without arming the recurring schedule.

# Report

Echo the script's `report` lines, prefixed with the loop status. Example:

```
loop armed (every ~14m, durable) · scope 5: in-review 1, queued 3, merged 1
#41 in-review PR #58 (active)
#40 queued
#44 queued
#46 queued
#45 merged PR #57
```

When the queue drains: `every scoped issue terminal — loop disarmed (CronDelete).`
