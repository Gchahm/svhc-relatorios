---
name: pr-review
description: >-
    Review one open GitHub pull request end-to-end: fetch the diff and surrounding code, review it for
    correctness, project-convention, and security problems, post inline comments on the exact lines that
    require fixes, and submit a verdict — REQUEST_CHANGES when fixes are needed, or APPROVE with an
    explicit go-ahead to merge when the PR is clean. Idempotent per head commit: it skips a PR whose
    current head it has already reviewed. Always targets this repository (svhc-relatorios) — it never
    reviews another repo. Use when asked to "review PR #N", "re-review this PR after my push", or when
    invoked by the pr-review-loop orchestrator.
argument-hint: "<pr-number>"
allowed-tools: Bash, Read, Grep, Glob
model: opus
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: 'python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/bash-deny.py" --profile reviewer'
---

# Purpose

Perform one complete, idempotent review of a single pull request. The output of this skill lives on
GitHub (one review with inline comments + a verdict), and the final message in the session is a terse
one-line verdict so an orchestrator can collect it cheaply.

# Input

`$ARGUMENTS`: a PR number (required, first token). The skill always operates on **this repository**
(the repo of the current directory) — there is no option to target another repo. All `gh` calls below
use `{owner}/{repo}` placeholders, which `gh api` resolves from the current repo.

# Steps

## 1. Resolve the PR and decide whether a review is due

```bash
gh pr view <n> --json number,title,body,author,headRefOid,baseRefName,isDraft,state,files
gh api user --jq .login
gh api repos/{owner}/{repo}/pulls/<n>/reviews --paginate \
    --jq '[.[] | select(.user.login=="<me>")] | last | {state, commit_id}'
```

Skip (report, do nothing on GitHub) when any of these hold:

- The PR is not `OPEN`, or is a draft.
- My latest review's `commit_id` equals the current `headRefOid` — this head was already reviewed.
  Report `SKIP #<n> already-reviewed@<sha7>` and stop.

## 2. Gather the change and its context

- `gh pr diff <n>` — the full unified diff. This is the primary review artifact.
- Read the PR title/body for stated intent; review against what it claims to do.
- For each touched file where the diff alone is ambiguous, read the **full file at the PR head**, not
  the local working tree:

    ```bash
    git fetch origin pull/<n>/head
    git show FETCH_HEAD:<path>
    ```

- Read the repo's `CLAUDE.md` (and any convention docs it points to) so convention findings are
  grounded in the project's actual rules, not generic taste.

Never check the PR branch out into the working tree, and never modify or push anything.

## 3. Review

Look for, in priority order:

1. **Correctness** — logic bugs, broken edge cases, wrong API usage, race conditions, data loss,
   regressions against the stated intent of the PR.
2. **Project conventions** — violations of CLAUDE.md rules and established patterns in the codebase
   (verify the pattern actually exists nearby before citing it).
3. **Security** — injection, authz gaps on new routes, secrets in code, unsafe input handling.
4. **Tests/verification** — behavior changes with no test or stated verification when the project
   clearly tests that area.
5. **Verification evidence** — the PR body must carry a `**Verification**` section saying what was
   exercised in the running app against local data (speckit pr phase, Step 4). On a PR with runtime
   surface, a missing or hollow section ("works fine", no concrete surface/data named) is a
   **blocking** finding: request changes asking for the verification to be performed and recorded.
   `none — no runtime surface` is acceptable only when the diff really has none.

Rules of judgment:

- Only report findings you are confident in and that you can tie to a specific line. No speculation.
- Do not flag style that the project's formatter/linter already enforces (e.g. Prettier/ESLint).
- A finding is **blocking** if merging it would ship a bug, a security hole, or a clear convention
  violation. Everything else is a non-blocking `nit:`.
- Each blocking comment must say concretely what to change, ideally with a suggested replacement using
  a GitHub suggestion block:

    ````markdown
    ```suggestion
    <corrected line(s)>
    ```
    ````

## 4. Submit ONE review with inline comments

Build the payload and submit it in a single API call so comments and verdict land atomically:

```bash
cat > /tmp/pr-review-<n>.json <<'EOF'
{
    "commit_id": "<headRefOid>",
    "event": "REQUEST_CHANGES",
    "body": "<2-5 sentence summary: what the PR does, overall assessment, count of blocking items>",
    "comments": [
        { "path": "src/foo.ts", "line": 42, "side": "RIGHT", "body": "<finding + concrete fix>" },
        { "path": "src/bar.ts", "start_line": 10, "line": 14, "side": "RIGHT", "body": "<multi-line finding>" }
    ]
}
EOF
gh api repos/{owner}/{repo}/pulls/<n>/reviews -X POST --input /tmp/pr-review-<n>.json
```

- `line`/`start_line` are line numbers in the **new** file (`side: "RIGHT"`); use `side: "LEFT"` only
  for comments on deleted lines. Comments may only target lines present in the diff.
- **Verdict rules:**
    - ≥1 blocking finding → `"event": "REQUEST_CHANGES"`; every blocking finding is an inline comment.
    - 0 blocking findings → `"event": "APPROVE"` with body ending in an explicit go-ahead:
      `"✅ Good to merge."` Non-blocking `nit:` comments may still ride along.
- If GitHub rejects the verdict with 422 (you authored the PR — GitHub forbids self-approval/
  self-request-changes), resubmit the same payload with `"event": "COMMENT"` and prepend the verdict
  to the body: `VERDICT: approve — good to merge (self-authored; GitHub forbids formal self-approval)`
  or `VERDICT: request-changes`. The `VERDICT: approve` prefix and the payload's `commit_id` are
  **load-bearing**: the merge-approval gate authorizes a merge only when it finds an `APPROVED`
  review or a body starting with `VERDICT: approve` **at the PR's current head commit** — keep the
  prefix byte-exact and always set `commit_id` to the head you reviewed.

## 5. Report

End with exactly one terse line (this is what an orchestrator reads):

```
#<n> <verdict: approve|request-changes|skip> @<sha7> — <blocking-count> blocking, <nit-count> nits
```

# Re-review protocol (continued context)

When you are this PR's standing reviewer and get a follow-up message that the head moved (the
author pushed after your review), re-review **in this same context** — your earlier findings are the
baseline:

1. Re-run step 1 for the new head (the already-reviewed skip check applies to the new SHA).
2. Diff what changed since the head you last reviewed: `git fetch origin pull/<n>/head` then
   `git diff <last-reviewed-sha>..FETCH_HEAD`, plus any author replies on your comment threads.
3. For each of your previous blocking findings, verify it is actually fixed — not just touched. If
   the author replied contesting a finding, weigh the argument on its merits and drop the finding if
   they're right.
4. Review the newly added changes as in step 3 of a first review (new code can introduce new bugs).
5. Submit one new review per step 4's rules: unresolved or new blocking findings → `REQUEST_CHANGES`
   (re-state unresolved items explicitly so they aren't lost); everything resolved → `APPROVE` with
   the go-ahead. Then report the one-line verdict.

If you have no memory of a prior review (fresh context on an already-reviewed PR), reconstruct the
baseline from the PR itself: read the existing review threads (`gh api .../pulls/<n>/reviews` and
`/comments`) before re-reviewing.

# Boundaries

- One review per head commit. Never post a second review for a head you already reviewed.
- Read-only with respect to code: never commit, push, merge, close, or edit the PR.
- The go-ahead is advisory — merging is performed by the PR's owner (a human, or the issue worker
  that opened it), never by the reviewer.
