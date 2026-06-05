---
name: speckit
description: >-
   Spec-driven development workflow for this repo: specify → clarify → plan → tasks →
   analyze → implement → pr (plus checklist, constitution, full, taskstoissues). Use when
   creating or updating a feature spec, generating an implementation plan or task breakdown,
   running cross-artifact analysis, implementing tasks, or opening a feature PR. Routes to the
   matching phase and resolves the active feature from the branch / specs folder.
---

# Speckit

Spec-driven development. Each phase has detailed instructions in `references/<phase>.md`;
this file routes to the right one and tracks workflow state. The phases were previously the
`/speckit.*` slash commands — same behavior, now one skill.

## Routing

Invocation looks like `speckit <phase> [arguments]` (e.g. `speckit specify add row reordering`).

1. Read the **first token** of the input as the phase keyword (table below).
2. Everything after it is that phase's arguments — substitute it wherever the reference says `$ARGUMENTS`.
3. **Read `references/<phase>.md` and follow it exactly.** It is the authoritative instruction set.
4. If no phase keyword is given, infer the next phase from workflow state (see *State detection*),
   confirm it with the user, then proceed.

| Phase | Reference | Purpose |
|-------|-----------|---------|
| `specify` | `references/specify.md` | Create/update the feature spec; creates the branch + spec dir |
| `clarify` | `references/clarify.md` | Resolve underspecified areas via targeted questions |
| `plan` | `references/plan.md` | Generate the implementation plan + design artifacts |
| `tasks` | `references/tasks.md` | Generate the dependency-ordered task breakdown |
| `analyze` | `references/analyze.md` | Cross-artifact consistency/quality analysis |
| `checklist` | `references/checklist.md` | Generate a custom validation checklist |
| `implement` | `references/implement.md` | Execute the tasks in tasks.md |
| `pr` | `references/pr.md` | Open the feature PR |
| `constitution` | `references/constitution.md` | Create/update the project constitution |
| `taskstoissues` | `references/taskstoissues.md` | Convert tasks into GitHub issues |
| `full` | `references/full.md` | Run the whole pipeline in one shot |

## Scripts

The bundled scripts in `scripts/` do the mechanical work (branch creation, prerequisite
checks, plan setup, agent-context updates). The references call them by repo-relative path,
e.g. `.claude/skills/speckit/scripts/create-new-feature.sh`. Run them from the repo root.
They resolve the repo root via git and read the bundled `.specifyrc` for branch naming.

## Branch / spec naming

Branches and spec dirs are named `<PROJECT>-<ISSUE>-<short-name>` (e.g. `PROJ-123-reorder-rows`),
governed by `.specifyrc` in this folder (`SPECIFY_BRANCH_PATTERN`, `SPECIFY_JIRA_PROJECT`).
The issue number is the Jira ticket, not auto-incremented. Specs live in `specs/<branch-name>/`.

## State detection (replaces phase handoffs)

The workflow state is on disk — no need to track it separately. Resolve the active feature
directory from the current branch (or the `SPECIFY_FEATURE` env var, or a ticket the user names),
glob `specs/<PROJECT>-<ISSUE>-*`, and list its contents to see which phases have run:

| Artifact present | Phase completed | Typical next phase |
|------------------|-----------------|--------------------|
| `spec.md` | specify | clarify or plan |
| `plan.md`, `research.md`, `data-model.md`, `contracts/` | plan | tasks |
| `tasks.md` | tasks | analyze or implement |
| `analysis.md` | analyze | implement |
| `tasks.md` with `[x]` items | implement (in progress) | finish implement, then pr |

Use this to suggest the next phase and to resume mid-workflow.

## Memory

The project constitution lives at `.claude/skills/speckit/memory/constitution.md`. The `analyze`
and `plan` phases read it for principle validation; the `constitution` phase reads and overwrites it.

## Outputs (written to the repo, not the skill)

- `specs/<branch-name>/` — specs, plans, tasks, analysis
- `AGENTS.md` — updated by `update-agent-context.sh`
