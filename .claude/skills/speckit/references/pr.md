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

### Step 4: Verify in the running app

Before opening the PR, verify the change where it actually runs — exercise the affected surface, not
just unit tests. Use **this project's** run/verify conventions, which live in the constitution's
**Running & Verifying the App** section (`.claude/agent-memory/speckit/constitution.md`) — this skill
hardcodes no commands, so read them from there:

- Start the app / dev server as that section documents, drive the affected surface against local or
  prod-like data (not synthetic input), and watch for errors. If the constitution names a dedicated
  verification agent/skill for the app, use it.
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

Closes #<issue>

**Spec**: <spec-url>
EOF
)"
```

If this work tracks a GitHub issue (the caller named one, or the spec/branch references one), the
body **must** contain a `Closes #<issue>` line (GitHub's standard closing keyword) so merging
auto-closes the issue. Drop the line only when there is genuinely no associated issue.

Add any labels your project requires with `--label <label>`.

### PR description format

- Brief and concise (1-3 sentences); no test plans
- A `Closes #<issue>` line whenever the work tracks an issue (see Step 5) — required for auto-close
- A `**Verification**` section: the 1-3 bullets from Step 4 (what was exercised in the running app
  against local data), or `none — no runtime surface`
- End with the spec link: `**Spec**: <url>`

Example:
```markdown
Add user preference endpoints for theme and notification settings.

Closes #42

**Verification**:
- GET/PUT /api/preferences round-trip via the running dev server (real user row)
- /dashboard/settings renders saved theme after reload

**Spec**: https://github.com/<org>/<repo>/tree/main/specs/001-short-name/spec.md
```

### Step 6: Report results

- Spec push status (pushed / no changes)
- PR URL
- Spec URL (for reference)

### Step 7: Hand off — opening the PR ends this phase

Opening the PR and reporting it (Step 6) is where the `pr` phase stops. **Reviewing, addressing
review feedback, and merging are the caller's responsibility — not this skill's.** This keeps speckit
repo-agnostic: it does not arm watchers, poll for reviews, touch heartbeat files, or merge.

- Under the **implement-loop**, the `developer` agent owns its PR through merge — it polls the PR in
  the foreground, addresses the `reviewer` agent's requested changes, and squash-merges on approval.
  That watch/merge protocol lives in the `developer` agent definition, not here.
- Run standalone (a human invoked `/speckit pr`), the human reviews and merges.

If you are a caller pushing a fix to an existing PR, two things are worth carrying over: classify
reviews **body-first** — in a single-account setup GitHub forbids self-approval, so a `COMMENTED`
review whose body starts `VERDICT: approve` IS an approval and `VERDICT: request-changes` IS a change
request; the `state` field alone is not enough. And re-run the project's checks (the constitution's
*Running & Verifying the App* section) before pushing.

### Error handling

- **Not on a feature branch**: guide the user to create one matching `SPECIFY_BRANCH_PATTERN` (e.g. `001-short-name`)
- **No spec directory**: suggest running `speckit specify` first
- **No commits to PR**: guide the user to commit changes first
- **gh not authenticated**: `gh auth login`
- **Push fails**: the branch may need a pull/rebase first
