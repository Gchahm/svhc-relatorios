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

### Step 4: Create the PR

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
- End with the spec link: `**Spec**: <url>`

Example:
```markdown
Add user preference endpoints for theme and notification settings.

**Spec**: https://github.com/<org>/<repo>/tree/main/specs/001-short-name/spec.md
```

### Step 5: Report results

- Spec push status (pushed / no changes)
- PR URL
- Spec URL (for reference)

### Error handling

- **Not on a feature branch**: guide the user to create one matching `SPECIFY_BRANCH_PATTERN` (e.g. `001-short-name`)
- **No spec directory**: suggest running `speckit specify` first
- **No commits to PR**: guide the user to commit changes first
- **gh not authenticated**: `gh auth login`
- **Push fails**: the branch may need a pull/rebase first
