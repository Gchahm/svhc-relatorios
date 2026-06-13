---
name: build-skill
description: >-
   Author a new Claude Code skill (or revise an existing one) following this repo's
   conventions — a `SKILL.md` with valid frontmatter plus standalone files in a
   `references/` folder that the main file points to. Bundles curated, verbatim Claude
   documentation under `references/` so skill authoring is grounded in the official
   tool/skill/agent reference rather than recalled from memory. Use it for "create a new
   skill", "scaffold a skill named X", "add a reference doc to the skill builder", or
   "review/fix a skill's structure".
---

# Build Skill

A meta-skill for building other skills. It does two things:

1. **Routes** skill-authoring work (scaffold a new skill, revise one, add a reference doc).
2. **Grounds** that work in curated Claude documentation kept verbatim under `references/`,
   so authoring decisions cite the official reference instead of memory.

The reference set grows over time: each time the user supplies a Claude docs link, save its
content as a new file under `references/` and add a row to the **References** table below.

## Conventions (MUST follow)

- **Python the skill RUNS is ALWAYS launched through Astral `uv` — never bare `python`/`python3`.**
  Any Python a skill/agent executes (analysis CLIs, bundled `scripts/` helpers, one-off commands)
  MUST go through `uv run` (this repo's convention; see `CLAUDE.md`). Use `uv run python …` for code
  inside the `scripts/` uv project, or `uv run --no-project python <path>` for a stdlib-only helper
  that lives outside it (e.g. a skill's own `scripts/` file). This applies to instructions in
  `SKILL.md`/agent bodies and to prompt templates — a literal `python3 foo.py` there is a defect.
  **One carve-out:** PreToolUse/Stop **`hooks:` commands** stay on `python3` — they fire on the hot
  path of every matched tool call, and the repo's hooks (`.claude/hooks/*.py`) are stdlib-only and
  invoked that way; wrapping them in `uv run` only adds per-call latency. Match the existing hooks.

## Skill anatomy (the pattern this repo follows)

A skill is a directory under `.claude/skills/<name>/` containing:

- **`SKILL.md`** — required. YAML frontmatter (`name`, `description`, optionally
  `allowed-tools`, `hooks:`, `shell:`) followed by the instruction body. The body is the
  authoritative prompt the model follows when the skill is invoked.
- **`references/<topic>.md`** — optional standalone files the `SKILL.md` points to by
  repo-relative path. Keep large or stable material (reference docs, per-phase instructions,
  examples) here so `SKILL.md` stays a thin router. This mirrors the `speckit` skill.
- **`scripts/`, `memory/`** — optional. Mechanical helpers and persistent state,
  respectively (again, see `speckit`).

An **agent** (subagent) is a single Markdown file under `.claude/agents/<name>.md` — YAML
frontmatter plus a system-prompt body. See `references/sub-agents.md` for the full format.

Scaffolds for both live in this skill's `templates/` folder (see **Templates** below).

### Frontmatter rules

- `name` — kebab-case, matches the directory name.
- `description` — the single most important field: it is what the model sees when deciding
  whether to invoke the skill. Lead with what it does, then a concrete "Use it for …" list of
  trigger phrases. Write it for *recall*, not prose.
- Keep `SKILL.md` focused; push depth into `references/`.

## Routing

Invocation looks like `build-skill <action> [arguments]`.

1. Read the **first token** as the action keyword (table below).
2. Everything after it is that action's arguments.
3. Before acting, read the relevant **References** file(s) so the work is grounded in the
   official docs — never recall tool/skill/frontmatter behavior from memory.
4. If no action keyword is given, infer intent from the request and confirm with the user.

| Action | Purpose |
|--------|---------|
| `new <name> <purpose>` | Scaffold a new `.claude/skills/<name>/` from `templates/skill.md` (+ `references/` if it needs depth). |
| `new-agent <name> <purpose>` | Scaffold a new `.claude/agents/<name>.md` from `templates/agent.md`. |
| `review <name>` | Audit an existing skill (or agent) against the anatomy + frontmatter rules and the references. |
| `add-reference <url>` | Fetch a Claude docs page, save it verbatim under `references/`, and add a row below. |

## Authoring a new skill

1. Clarify the skill's single responsibility and its trigger phrases (these become the
   `description`).
2. **Start from `templates/skill.md`** — copy it to `.claude/skills/<name>/SKILL.md` and
   replace every `qqq` placeholder. Do not leave any `qqq` behind.
3. Decide tool surface: which built-in tools it needs (consult `references/tools-reference.md`)
   and whether to constrain it with `allowed-tools`. Drop frontmatter keys the skill doesn't
   need (the template lists the full set; most skills need only `name` + `description`, plus
   `allowed-tools` when restricting).
4. Replace the body sections (Purpose / Variables / Instructions / Workflow / Examples /
   Report) with the real instructions; keep `SKILL.md` thin and push lengthy material into
   `references/` (point to them by repo-relative path, e.g.
   `.claude/skills/<name>/references/<topic>.md`).
5. Skill definitions are cached per session — after creating or editing a skill, the session
   must be restarted before the change takes effect.

## Authoring a new agent

1. Clarify the agent's single responsibility, when Claude should delegate to it
   (`description`), and which tools it needs — consult `references/sub-agents.md`.
2. **Start from `templates/agent.md`** — copy it to `.claude/agents/<name>.md` and replace
   every `qqq` placeholder; drop frontmatter keys the agent doesn't need.
3. Write the system-prompt body (Purpose / Variables / Codebase Structure / Instructions /
   Workflow / Report).
4. Agents are also loaded at session start — restart to pick up a new or edited agent file.

## Templates

Scaffolds to copy when creating new artifacts. Both use `qqq` as the placeholder marker —
every `qqq` must be replaced (or its line removed) before the file is final.

| Template | For | Target location |
|----------|-----|-----------------|
| `templates/skill.md` | A new skill | `.claude/skills/<name>/SKILL.md` |
| `templates/agent.md` | A new subagent | `.claude/agents/<name>.md` |

## References

Curated Claude documentation, saved verbatim. Read the relevant file before making authoring
decisions in that area. Each file records its source URL at the top.

| Reference | Source | Covers |
|-----------|--------|--------|
| `references/tools-reference.md` | https://code.claude.com/docs/en/tools-reference | The complete built-in tool catalog, permission-rule formats, and per-tool behavior (Agent, Bash, Edit, Read, Write, Glob, Grep, WebFetch, WebSearch, etc.). |
| `references/sub-agents.md` | https://code.claude.com/docs/en/sub-agents | Creating/configuring custom subagents: file format + scopes, the full supported-frontmatter table, tool/MCP/permission control, model selection, memory, hooks, foreground vs background, nested subagents, forking, and example agents. |

> Add a new row here whenever a docs page is saved under `references/`.
