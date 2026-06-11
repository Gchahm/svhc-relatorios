---
name: pr-review-loop
description: >-
    Keep an automated PR-review loop alive over the repo's open pull requests. Each pass lists open
    PRs, selects the ones whose current head commit has not been reviewed yet (new PRs, or PRs with new
    pushes since the last review), and delegates each one to the pr-review skill in an isolated
    subagent, collecting only terse verdicts. One persistent reviewer worker per PR: re-reviews after
    new pushes continue the SAME worker via SendMessage, so it remembers its earlier findings while the
    loop stays thin. Designed to run as the recurring prompt of /loop. Use for
    "watch open PRs and review them automatically", "start the PR review loop", "babysit our PRs", or
    "run a review pass over open PRs".
argument-hint: "[--repo owner/name] [--once]"
allowed-tools: Bash, Agent
model: haiku
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-deny.py" --profile review-orchestrator'
---

# Purpose

Be the thin, always-cheap orchestrator of automated PR review. Each invocation performs **one pass**:
find what needs review, fan the heavy work out to context-isolated workers that run the `pr-review`
skill, collect one verdict line per PR, report. You never read diffs or page through code yourself —
your context stays flat so the loop can run indefinitely.

# Keeping the loop alive

This skill does one pass per invocation; the recurrence comes from `/loop`:

- **Standing loop (the normal mode):** start it with

    ```
    /loop 15m /pr-review-loop
    ```

    Each firing runs one pass. The pass is cheap when idle (one `gh pr list` + one SHA check per PR),
    so a 10–15 minute interval is fine. Stop it by cancelling the loop.

- **Self-paced:** `/loop /pr-review-loop` lets the model pick the next wake-up. When a pass found work,
  re-check sooner (a few minutes); when a pass was idle, back off (20–30 minutes).

- **Single pass:** invoking the skill directly (or with `--once`) runs one pass and ends. If invoked
  directly without `--once` and not under `/loop`, run the pass, then remind the user they can make it
  standing with `/loop 15m /pr-review-loop` — do not build your own sleep loop in Bash.

# One pass

## 1. Find candidates

```bash
gh pr list --state open --json number,title,author,headRefOid,isDraft
gh api user --jq .login
```

Drop drafts. For each remaining PR, check whether its current head still needs a review (same check
`pr-review` makes, done here cheaply so you don't spawn workers for nothing):

```bash
gh api repos/{owner}/{repo}/pulls/<n>/reviews --paginate \
    --jq '[.[] | select(.user.login=="<me>")] | last | .commit_id'
```

A PR **needs review** when that is empty or differs from its `headRefOid`. If no PR needs review,
report `idle — <k> open PRs, all reviewed at head` and end the pass.

## 2. Delegate each review (parallel, isolated, persistent per PR)

Each PR gets ONE reviewer worker for its lifetime. Keep a PR → worker-id mapping in your own context
across passes (worker ids are session-scoped; after a session restart the mapping is simply empty and
GitHub state remains authoritative).

- **First review of a PR** — spawn one subagent via the Agent tool, all candidates in a single batch
  so they run concurrently, and **always with `model: opus`** (the review is the judgment-heavy step;
  this loop itself runs on a cheap model, and workers would otherwise inherit it). Prompt:

  > Invoke the `pr-review` skill for PR #<n> in this repo and follow it exactly. You are this PR's
  > reviewer for its lifetime: keep your findings in mind — you will be asked to re-review in this
  > same context when the author pushes. Return ONLY the final one-line verdict
  > (`#<n> <verdict> @<sha7> — …`) — no diff content, no commentary.

  Record the worker id against the PR.

- **Re-review (head moved since our last review)** — `SendMessage` to that PR's existing worker:

  > PR #<n>'s head moved to <sha7>. Re-review per the pr-review skill's re-review protocol: check
  > whether your previous blocking comments were addressed, review the new changes, and submit a new
  > verdict. Return ONLY the one-line verdict.

  If `SendMessage` fails (worker gone — new session), fall back to a fresh spawn with the first-review
  prompt; the skill itself recovers prior findings from the PR's review thread.

Do not run the reviews inline yourself: the per-PR diff reading must stay in the workers' contexts,
not yours. Drop a PR's mapping entry once the PR is merged or closed.

## 3. Report the pass

One line per PR plus a header, e.g.:

```
pass complete — 3 open, 2 reviewed, 1 already current
#41 request-changes @a1b2c3d — 2 blocking, 1 nit
#43 approve @9f8e7d6 — 0 blocking, 0 nits ✅ good to merge
```

If a worker fails (gh error, rate limit), report that PR as `error` with the reason and move on — the
next pass retries it naturally, since its head is still unreviewed.

# Boundaries

- Orchestrate only: never fetch a PR diff, read changed files, or post review comments yourself — that
  is the workers' job via `pr-review`.
- Never merge, close, or push to any PR. The approve verdict is a go-ahead for the PR's owner — a
  human, or the `speckit-issue-loop` worker that opened it.
- One review per (PR, head commit) — guaranteed by the SHA check here plus the same check inside
  `pr-review`.
- Each pass must terminate on its own; recurrence comes only from `/loop`, never from a Bash
  sleep/while loop.
