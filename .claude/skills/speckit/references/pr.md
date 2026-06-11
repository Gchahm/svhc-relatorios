## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). User input can override:
- PR title
- Target branch (default: main)
- Additional PR description content

## Outline

Create a pull request for the current speckit feature, with a link to the feature spec in the description.

### Prerequisites

- On a feature branch matching `SPECIFY_BRANCH_PATTERN` from `.specifyrc` (e.g. `001-short-name`)
- Committed changes ready for PR
- A feature spec at `specs/<branch-name>/spec.md`
- `gh` CLI authenticated (`gh auth login`)

### Step 1: Gather context

```bash
# Branch naming config (SPECIFY_BRANCH_PATTERN, SPECIFY_BRANCH_EXAMPLE)
source .claude/skills/speckit/.specifyrc 2>/dev/null || true

BRANCH=$(git rev-parse --abbrev-ref HEAD)
ORIGIN=$(git remote get-url origin)
```

Derive the repo's HTTPS base from `ORIGIN` (works for any host/org):
- `git@github.com:<org>/<repo>.git` → `https://github.com/<org>/<repo>`
- `https://github.com/<org>/<repo>.git` → `https://github.com/<org>/<repo>`

### Step 2: Commit & push the spec, then the branch

```bash
# Commit any spec changes (skip if nothing changed)
git add specs/<branch-name>
git commit -m "docs: update spec for <branch-name>"

# Push the feature branch
git push -u origin <branch-name>
```

**Separate specs repo (optional):** if `specs/` is a symlink to its own git repository (a wrapper/monorepo
setup), commit and push there instead of the main repo:
```bash
git -C specs/ add . && git -C specs/ commit -m "docs: update spec for <branch-name>" && git -C specs/ push origin HEAD:main
```

### Step 3: Determine the spec URL

Build a link to the spec in whichever repo it lives in:
```
https://github.com/<org>/<repo>/tree/<default-branch>/specs/<branch-name>/spec.md
```
If specs live in a separate repo, use that repo's base URL and its layout (some store features at the
repo root, i.e. `<branch-name>/spec.md`).

Example: `https://github.com/<org>/<repo>/tree/main/specs/001-short-name/spec.md`

### Step 4: Verify in the running app (local data)

Before opening the PR, verify the change where it actually runs. The dev checkout carries prod-like
local data (Miniflare D1/R2 under `.wrangler/`), so the feature can be exercised against real data
shapes, not an empty database:

- Start the app (`pnpm dev`) and drive the affected surface — the `verify` and `ui-login` skills
  cover the auth-gated dashboard via the Playwright browser.
- Exercise the feature with the local data (real entries/attachments/alerts), not synthetic input;
  watch for errors in the dev server output while doing so.
- Keep 1-3 bullets of *what you exercised and observed* — they go in the PR body (next step).
- Only changes with no runtime surface (docs, CI, comments) may skip this; the PR body must then say
  `Verification: none — no runtime surface`.

### Step 5: Create the PR

```bash
gh pr create \
  --base main \
  --title "<PR title>" \
  --body "$(cat <<'EOF'
<Brief 1-3 sentence summary of the change>

**Spec**: <spec-url>
EOF
)"
```

Add any labels your project requires with `--label <label>`.

### PR description format

- Brief and concise (1-3 sentences); no test plans
- A `**Verification**` section: the 1-3 bullets from Step 4 (what was exercised in the running app
  against local data), or `none — no runtime surface`
- End with the spec link: `**Spec**: <url>`

Example:
```markdown
Add user preference endpoints for theme and notification settings.

**Verification**:
- GET/PUT /api/preferences round-trip via the running dev server (real user row)
- /dashboard/settings renders saved theme after reload

**Spec**: https://github.com/<org>/<repo>/tree/main/specs/001-short-name/spec.md
```

### Step 6: Report results

- Spec push status (pushed / no changes)
- PR URL
- Spec URL (for reference)

### Step 7: Own the PR until merge (review follow-up protocol)

The agent context that opened the PR **owns it through merge**. Opening the PR is not the end of the
feature — reviews come back, and you are the one with the spec, plan, and implementation in context,
so you handle them here rather than letting a fresh agent rediscover everything.

After reporting the PR URL, end your turn. Review events arrive as follow-up messages in this same
context (from the user, or from an orchestrator such as `speckit-issue-loop`). Handle each:

**Changes requested** — a review with blocking inline comments:

1. Fetch the review and its inline comments:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<pr>/reviews
   gh api repos/{owner}/{repo}/pulls/<pr>/comments
   ```
2. Address **every** blocking comment with commits on the same feature branch — fix it, or if you
   believe the reviewer is wrong, don't change the code silently: reply on the comment thread with
   your reasoning and let the next review round decide.
3. Keep the spec in sync: if a fix changes behavior described in `specs/<branch>/spec.md`, update the
   spec in the same push.
4. Run the project's checks (`pnpm lint`, `pnpm format`, tests where they exist) before pushing.
5. Push, reply to each inline comment with a one-liner on what changed, and report tersely
   (commits pushed, comments addressed/contested). Do not echo diffs.

**Approved (the go-ahead)** — squash-merge and clean up:

```bash
gh pr merge <pr> --squash --delete-branch
```

Verify any `Closes #<issue>` issue actually closed, then report `merged`. Never merge before an
explicit approval, and never dismiss or wait out a requested-changes review.

### Error handling

- **Not on a feature branch**: guide the user to create one matching `SPECIFY_BRANCH_PATTERN` (e.g. `001-short-name`)
- **No spec directory**: suggest running `speckit specify` first
- **No commits to PR**: guide the user to commit changes first
- **gh not authenticated**: `gh auth login`
- **Push fails**: the branch may need a pull/rebase first
