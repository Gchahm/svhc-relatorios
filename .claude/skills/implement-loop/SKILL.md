---
name: implement-loop
description: >-
    Self-starting automated implementation loop over the repo's open GitHub issues, ONE at a time.
    Unlike the older speckit-issue-loop you do NOT wrap it in `/loop` — this skill arms its own
    recurring schedule (CronCreate) on first run and disarms it (CronDelete) when the queue drains.
    A deterministic decision script (`scripts/loop_state.py`) reconciles with GitHub and returns the
    single action to take each pass; the skill just executes it — dispatch the next eligible issue
    (dependency-gated, priority, oldest first) to a long-lived `developer` agent that runs speckit
    full → verify → PR → watch → merge, resume a worker that died, AND — once a PR is open — spawn a
    `reviewer` agent to review it at each head commit (this replaces the separate pr-review-loop).
    The prompts it hands the workers live in `templates/`. Use for "start the implement loop", "work
    through our issues automatically", or "implement open issues".
argument-hint: "[issue-numbers in work order…] [--label <name>] [--once] [--every <Nm>]"
allowed-tools: Bash, Agent, Read, CronCreate, CronList, CronDelete, TaskStop, SendMessage
model: haiku
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-deny.py" --profile implement-orchestrator'
---

# Purpose

Be the thin, always-cheap executor of a deterministic decision. You never write a spec, read a diff,
reconcile state, or post a review by hand: a script (`scripts/loop_state.py`) owns all the
bookkeeping and decides what each pass needs, and the heavy work is owned by context-isolated agents
— a `developer` that builds/verifies/opens/watches/merges its issue's PR, and a `reviewer` that
reviews that PR at each head. Your whole job per pass: make sure the recurring schedule is armed, ask
the script what to do, and do exactly that. Your context must stay flat enough to run for days.

What makes this different from the old `speckit-issue-loop` + `pr-review-loop`:

1. **Self-starting** — you arm a recurring `CronCreate` job yourself, so the user runs
   `/implement-loop` once, not `/loop … /speckit-issue-loop`.
2. **Self-reviewing** — once a developer opens a PR, the script tells you (via a `review` directive)
   to spawn a `reviewer` agent for each head commit that hasn't been reviewed yet. This folds in the
   whole pr-review-loop: you no longer run it separately.
3. **Self-healing** — when a worker dies/hangs (the script returns `resume`) you reap it with
   `TaskStop` and respawn from durable state; when a worker finishes but hangs without replying
   (`stop_agent` / `stop_reviewer`) you `TaskStop` the zombie and proceed. All use the agent id the
   script already tracks — no agent-teams flag needed. (An optional `SendMessage` fast-path can
   resume a live developer in place when teams are enabled.)

# Variables

- `DECISION_SCRIPT`: `.claude/skills/implement-loop/scripts/loop_state.py` — the brain. It reconciles
  with GitHub, owns `STATE_FILE` (its only writer), and prints the action JSON. It is stdlib-only and
  lives outside the `scripts/` uv project, so always run it via uv with `--no-project`:
  `uv run --no-project python "$CLAUDE_PROJECT_DIR/$DECISION_SCRIPT" <subcommand> …` (never bare
  `python`/`python3` — repo convention).
- `STATE_FILE`: `.cache/implement-loop/state.json` — written ONLY by the script; you never edit it.
- `HEARTBEAT`: `.cache/implement-loop/heartbeat-<issue>` (developer, per-issue) and
  `.cache/implement-loop/review-heartbeat-<pr>` (reviewer, per-PR). Each worker touches its own file
  ~every 60s for its whole life; the script reads the age to tell whether that worker is alive.
  Per-issue/per-PR (not one shared file) so a finished-but-stuck worker can't mask another.
- `INTERVAL`: cron expression for the recurring pass. Default `*/14 * * * *` (~every 14 min).
  `--every <Nm>` overrides (e.g. `--every 10m` → `*/10 * * * *`).
- `WORKER_PROMPT`: `templates/dispatch-prompt.md` — the per-issue task handed to a fresh developer.
- `CATCHUP_PROMPT`: `templates/catchup-prompt.md` — the task handed to a resumed/respawned developer.
- `REVIEW_PROMPT`: `templates/review-prompt.md` — the per-PR-head task handed to a `reviewer`.
- `STATE_SHAPE`: `templates/state.json` — documents the shape the script writes: a `scope` list, a
  per-issue `status` (`queued | building | in-review | merged | closed | error`), and `current_work`
  — the active issue, its `developer` (`agent, spawned_at, restarts`), its `pr`/`branch`, and its
  `reviewer` (`reviewer_agent, reviewer_spawned_at, reviewer_head`).

GitHub is the source of truth; the script reads it read-only. It DOES read review state — the last
review's `commit_id` vs the PR head — because this loop now owns reviewer dispatch (that's why the
Bash guard is `implement-orchestrator`, which permits reading reviews but still blocks merges,
pushes, diffs, and posting reviews).

# Instructions

- **Execute the decision; never second-guess it.** The script returns one action (plus optional
  `review` / `stop_*` fields) per pass — carry it out and report. Do not reconcile, re-order, read
  GitHub, or review code yourself.
- **One ISSUE in flight, strictly serial** — but up to two workers ON that issue: its `developer`
  (long-lived: builds → opens PR → watches → merges) and a short-lived `reviewer` per head commit.
  The next issue dispatches only after the current one's PR merges.
- **Merging is approval-gated** by the global merge hook; the developer merges only after an APPROVED
  (or `VERDICT: approve`) review at the current head. The `reviewer` you spawn is what produces that
  review — together: implement → review → fix → approve → merge, all inside this one loop. (No
  separate `/pr-review-loop` is needed.)
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

## 1. Ask the script what to do (one call per pass)

```bash
uv run --no-project python "$CLAUDE_PROJECT_DIR/.claude/skills/implement-loop/scripts/loop_state.py" next $ARGUMENTS
```

It prints one JSON object: `{ "action": …, "report": […], "stop_agent": …, "stop_reviewer": …,
"review": … }`. **Print the `report` lines** as the pass report. Then, in order:

**First, honor any `stop_*` ids with `TaskStop`** — a background worker spawn is a `local_agent`
task whose `task_id` IS the agent id the script returns, so `TaskStop(task_id=<id>)` is a guaranteed
hard kill (no permission, no agent-teams flag). Killing a worker also stops its heartbeat loop.
- `stop_agent`: a developer whose issue is now closed (work merged) but still alive — it finished but
  hung and never replied. (This is the fix for "the worker finished but the loop didn't proceed.")
- `stop_reviewer`: a reviewer that is stale (the head moved under it), lingering (its head is now
  reviewed), or orphaned (issue closed / developer errored).

## 2. Execute the developer action

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

## 3. Spawn a reviewer if the script asks (the `review` field)

If the decision carries `review: { "spawn": true, "pr", "head", "issue" }`, the PR's current head
has not been reviewed and no reviewer is alive on it. Read `templates/review-prompt.md`, substitute
`{{PR_NUMBER}}`=`pr` and `{{ISSUE_NUMBER}}`=`issue`, and spawn ONE **Agent**: `subagent_type:
"reviewer"`, `run_in_background: true`. Capture the returned agent id and record it:
`uv run --no-project python "$CLAUDE_PROJECT_DIR/$DECISION_SCRIPT" review-dispatched --agent <id> --head <head>`.

The reviewer runs the `pr-review` skill (idempotent per head) and posts the verdict the merge gate
reads; the developer (watching its own PR) addresses changes / merges on approval. You do NOT read
the verdict or merge — the script re-checks "reviewed at head" from GitHub next pass and only asks
for another reviewer when the head moves. (`review` is absent while the developer is still building —
no PR yet — and once the head is already reviewed.)

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
