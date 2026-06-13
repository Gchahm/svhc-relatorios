# Create custom subagents

> Source: https://code.claude.com/docs/en/sub-agents
> Create and use specialized AI subagents in Claude Code for task-specific workflows and improved context management.

Subagents are specialized AI assistants that handle specific types of tasks. Use one when a side task would flood your main conversation with search results, logs, or file contents you won't reference again: the subagent does that work in its own context and returns only the summary. Define a custom subagent when you keep spawning the same kind of worker with the same instructions.

Each subagent runs in its own context window with a custom system prompt, specific tool access, and independent permissions. When Claude encounters a task that matches a subagent's description, it delegates to that subagent, which works independently and returns results.

> **Note:** Subagents work within a single session. To run many independent sessions in parallel and monitor them from one place, see background agents. For sessions that communicate with each other, see agent teams.

Subagents help you:

- **Preserve context** by keeping exploration and implementation out of your main conversation
- **Enforce constraints** by limiting which tools a subagent can use
- **Reuse configurations** across projects with user-level subagents
- **Specialize behavior** with focused system prompts for specific domains
- **Control costs** by routing tasks to faster, cheaper models like Haiku

Claude uses each subagent's description to decide when to delegate tasks. When you create a subagent, write a clear description so Claude knows when to use it.

Claude Code includes several built-in subagents like **Explore**, **Plan**, and **general-purpose**. You can also create custom subagents to handle specific tasks.

## Built-in subagents

Claude Code includes built-in subagents that Claude automatically uses when appropriate. Each inherits the parent conversation's permissions with additional tool restrictions.

Explore and Plan skip your CLAUDE.md files and the parent session's git status to keep research fast and inexpensive. Every other built-in and custom subagent loads both.

**Explore** — A fast, read-only agent optimized for searching and analyzing codebases.
- **Model**: Haiku (fast, low-latency)
- **Tools**: Read-only tools (denied access to Write and Edit tools)
- **Purpose**: File discovery, code search, codebase exploration
- Claude delegates to Explore when it needs to search or understand a codebase without making changes. When invoking Explore, Claude specifies a thoroughness level: **quick** for targeted lookups, **medium** for balanced exploration, or **very thorough** for comprehensive analysis.

**Plan** — A research agent used during plan mode to gather context before presenting a plan.
- **Model**: Inherits from main conversation
- **Tools**: Read-only tools (denied access to Write and Edit tools)
- **Purpose**: Codebase research for planning

**General-purpose** — A capable agent for complex, multi-step tasks that require both exploration and action.
- **Model**: Inherits from main conversation
- **Tools**: All tools
- **Purpose**: Complex research, multi-step operations, code modifications

**Other** — additional helper agents, typically invoked automatically:

| Agent | Model | When Claude uses it |
| :--- | :--- | :--- |
| statusline-setup | Sonnet | When you run `/statusline` to configure your status line |
| claude-code-guide | Haiku | When you ask questions about Claude Code features |

Built-in subagents are always registered in interactive sessions. To block a specific built-in type, add it to `permissions.deny` (see [Disable specific subagents](#disable-specific-subagents)). To prevent Claude from delegating to any subagent, deny the `Agent` tool itself with `permissions.deny`. In non-interactive mode and the Agent SDK, set `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1` to remove all built-in types and supply only your own.

## Quickstart: create your first subagent

Subagents are defined in Markdown files with YAML frontmatter. You can create them manually or use the `/agents` command.

Walkthrough (user-level subagent via `/agents`):

1. **Open the subagents interface** — run `/agents`.
2. **Choose a location** — switch to the **Library** tab, select **Create new agent**, then choose **Personal** (saves to `~/.claude/agents/`, available in all projects).
3. **Generate with Claude** — select **Generate with Claude** and describe the subagent; Claude generates the identifier, description, and system prompt.
4. **Select tools** — for a read-only reviewer, deselect everything except **Read-only tools**. Keeping all tools selected makes the subagent inherit all tools from the main conversation.
5. **Select model** — choose which model the subagent uses (e.g. **Sonnet**).
6. **Choose a color** — pick a background color to identify the subagent in the UI.
7. **Configure memory** — **User scope** gives a persistent memory directory at `~/.claude/agent-memory/`; **None** if you don't want persisted learnings.
8. **Save and try it out** — press `s`/`Enter` to save (or `e` to save and edit). Available immediately: e.g. "Use the code-improver agent to suggest improvements in this project."

You can also create subagents manually as Markdown files, define them via CLI flags, or distribute them through plugins.

## Configure subagents

### Use the /agents command

The `/agents` command opens a tabbed interface. The **Running** tab lists live and recently finished subagents and lets you open or stop them. The **Library** tab lets you:

- View all available subagents (built-in, user, project, and plugin)
- Create new subagents with guided setup or Claude generation
- Edit existing subagent configuration and tool access
- Delete custom subagents
- See which subagents are active when duplicates exist

### Choose the subagent scope

Subagents are Markdown files with YAML frontmatter, stored in different locations depending on scope. When multiple subagents share the same name, the higher-priority location wins.

| Location | Scope | Priority | How to create |
| :--- | :--- | :--- | :--- |
| Managed settings | Organization-wide | 1 (highest) | Deployed via managed settings |
| `--agents` CLI flag | Current session | 2 | Pass JSON when launching Claude Code |
| `.claude/agents/` | Current project | 3 | Interactive or manual |
| `~/.claude/agents/` | All your projects | 4 | Interactive or manual |
| Plugin's `agents/` directory | Where plugin is enabled | 5 (lowest) | Installed with plugins |

**Project subagents** (`.claude/agents/`) are ideal for subagents specific to a codebase. Check them into version control. They're discovered by walking up from the current working directory. Directories added with `--add-dir` grant file access only and are not scanned for subagents.

**User subagents** (`~/.claude/agents/`) are personal subagents available in all your projects.

Claude Code scans `.claude/agents/` and `~/.claude/agents/` recursively, so you can organize definitions into subfolders (e.g. `agents/review/`). The subdirectory path does not affect identity — identity comes only from the `name` frontmatter field. Keep `name` values unique across the whole tree: if two files within one scope declare the same name, Claude Code keeps one and discards the other without warning.

Plugin `agents/` directories are also scanned recursively. Unlike project/user scopes, a subfolder inside a plugin's `agents/` directory becomes part of the scoped identifier: a file at `agents/review/security.md` in plugin `my-plugin` registers as `my-plugin:review:security`.

**CLI-defined subagents** are passed as JSON when launching Claude Code (`--agents`). They exist only for that session and aren't saved to disk. Example (macOS/Linux/WSL):

```bash
claude --agents '{
  "code-reviewer": {
    "description": "Expert code reviewer. Use proactively after code changes.",
    "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
    "tools": ["Read", "Grep", "Glob", "Bash"],
    "model": "sonnet"
  },
  "debugger": {
    "description": "Debugging specialist for errors and test failures.",
    "prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
  }
}'
```

The `--agents` flag accepts JSON with the same frontmatter fields as file-based subagents: `description`, `prompt`, `tools`, `disallowedTools`, `model`, `permissionMode`, `mcpServers`, `hooks`, `maxTurns`, `skills`, `initialPrompt`, `memory`, `effort`, `background`, `isolation`, and `color`. Use `prompt` for the system prompt (equivalent to the markdown body in file-based subagents).

**Managed subagents** are deployed by organization administrators — place markdown files in `.claude/agents/` inside the managed settings directory. They take precedence over project and user subagents with the same name.

**Plugin subagents** come from installed plugins and appear in `/agents` alongside custom subagents.

> **Note:** For security reasons, plugin subagents do not support the `hooks`, `mcpServers`, or `permissionMode` frontmatter fields. These are ignored when loading agents from a plugin. If you need them, copy the agent file into `.claude/agents/` or `~/.claude/agents/`.

Subagent definitions from any scope are also available to agent teams.

### Write subagent files

Subagent files use YAML frontmatter for configuration, followed by the system prompt in Markdown:

> **Note:** Subagents are loaded at session start. If you add or edit a subagent file directly on disk, restart your session to load it. Subagents created through the `/agents` interface take effect immediately without a restart.

```markdown
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

The frontmatter defines metadata and configuration. The body becomes the system prompt. Subagents receive only this system prompt (plus basic environment details like working directory), not the full Claude Code system prompt.

A subagent starts in the main conversation's current working directory. Within a subagent, `cd` commands do not persist between Bash/PowerShell tool calls and do not affect the main conversation's working directory. To give the subagent an isolated copy of the repository, set `isolation: worktree`.

#### Supported frontmatter fields

Only `name` and `description` are required.

| Field | Required | Description |
| :--- | :--- | :--- |
| `name` | Yes | Unique identifier using lowercase letters and hyphens. Hooks receive this value as `agent_type`. The filename does not have to match |
| `description` | Yes | When Claude should delegate to this subagent |
| `tools` | No | Tools the subagent can use. Inherits all tools if omitted. To preload Skills into context, use the `skills` field rather than listing `Skill` here |
| `disallowedTools` | No | Tools to deny, removed from inherited or specified list |
| `model` | No | Model to use: `sonnet`, `opus`, `haiku`, `fable`, a full model ID (e.g. `claude-opus-4-8`), or `inherit`. Defaults to `inherit` |
| `permissionMode` | No | Permission mode: `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, or `plan`. Ignored for plugin subagents |
| `maxTurns` | No | Maximum number of agentic turns before the subagent stops |
| `skills` | No | Skills to preload into the subagent's context at startup. The full skill content is injected, not just the description. Subagents can still invoke unlisted project/user/plugin skills through the Skill tool |
| `mcpServers` | No | MCP servers available to this subagent. Each entry is either a server name referencing an already-configured server (e.g. `"slack"`) or an inline definition. Ignored for plugin subagents |
| `hooks` | No | Lifecycle hooks scoped to this subagent. Ignored for plugin subagents |
| `memory` | No | Persistent memory scope: `user`, `project`, or `local`. Enables cross-session learning |
| `background` | No | Set to `true` to always run this subagent as a background task. Default: `false` |
| `effort` | No | Effort level when this subagent is active. Overrides the session effort level. Options: `low`, `medium`, `high`, `xhigh`, `max`; available levels depend on the model |
| `isolation` | No | Set to `worktree` to run the subagent in a temporary git worktree (isolated copy of the repo, branched by default from your default branch rather than the parent session's `HEAD`). Auto-cleaned if the subagent makes no changes |
| `color` | No | Display color: `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, or `cyan` |
| `initialPrompt` | No | Auto-submitted as the first user turn when this agent runs as the main session agent (via `--agent` or the `agent` setting). Commands and skills are processed. Prepended to any user-provided prompt |

### Choose a model

The `model` field controls which AI model the subagent uses:

- **Model alias**: `sonnet`, `opus`, `haiku`, or `fable`
- **Full model ID**: e.g. `claude-opus-4-8` or `claude-sonnet-4-6` (same values as `--model`)
- **inherit**: same model as the main conversation
- **Omitted**: defaults to `inherit`

When Claude invokes a subagent it can pass a `model` parameter for that invocation. Resolution order:

1. The `CLAUDE_CODE_SUBAGENT_MODEL` environment variable, if set
2. The per-invocation `model` parameter
3. The subagent definition's `model` frontmatter
4. The main conversation's model

### Control subagent capabilities

#### Available tools

Subagents inherit the internal tools and MCP tools available in the main conversation by default. The following depend on the main conversation's UI or session state and are **not available** to subagents even when listed in `tools`:

- `AskUserQuestion`
- `EnterPlanMode`
- `ExitPlanMode`, unless the subagent's `permissionMode` is `plan`
- `ScheduleWakeup`
- `WaitForMcpServers`

To restrict tools, use either `tools` (allowlist) or `disallowedTools` (denylist). Allowlist example:

```yaml
---
name: safe-researcher
description: Research agent with restricted capabilities
tools: Read, Grep, Glob, Bash
---
```

Denylist example (inherit everything except Write/Edit):

```yaml
---
name: no-writes
description: Inherits every tool except file writes
disallowedTools: Write, Edit
---
```

If both are set, `disallowedTools` is applied first, then `tools` is resolved against the remaining pool. A tool listed in both is removed.

#### Restrict which subagents can be spawned

When an agent runs as the main thread with `claude --agent`, it can spawn subagents using the Agent tool. To restrict which types it can spawn, use `Agent(agent_type)` syntax in `tools`:

> **Note:** In version 2.1.63, the Task tool was renamed to Agent. Existing `Task(...)` references still work as aliases.

```yaml
---
name: coordinator
description: Coordinates work across specialized agents
tools: Agent(worker, researcher), Read, Bash
---
```

This is an allowlist: only `worker` and `researcher` can be spawned. To allow spawning any subagent, use `Agent` without parentheses (`tools: Agent, Read, Bash`). If `Agent` is omitted entirely, the agent cannot spawn any subagents.

The `Agent(agent_type)` allowlist syntax applies only to an agent running as the main thread with `claude --agent`. In a subagent definition, listing `Agent` in `tools` lets that subagent spawn nested subagents, but any type list inside the parentheses is ignored.

#### Scope MCP servers to a subagent

Use `mcpServers` to give a subagent access to MCP servers not available in the main conversation. Inline servers are connected when the subagent starts and disconnected when it finishes; string references share the parent session's connection.

```yaml
---
name: browser-tester
description: Tests features in a real browser using Playwright
mcpServers:
  # Inline definition: scoped to this subagent only
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
  # Reference by name: reuses an already-configured server
  - github
---

Use the Playwright tools to navigate, screenshot, and interact with pages.
```

Inline definitions use the same schema as `.mcp.json` server entries (`stdio`, `http`, `sse`, `ws`). Defining a server inline here keeps it out of the main conversation, so its tool descriptions don't consume context there.

As of v2.1.153, MCP restrictions that apply to the main session also cover servers declared in subagent frontmatter: `--strict-mcp-config`/`--bare`, enterprise managed MCP configuration, and `allowedMcpServers`/`deniedMcpServers` policies. (`--strict-mcp-config` does not filter servers passed inline via `--agents` or the SDK `agents` option.)

#### Permission modes

The `permissionMode` field controls how the subagent handles permission prompts. Subagents inherit the permission context from the main conversation and can override the mode, except where the parent mode takes precedence.

| Mode | Behavior |
| :--- | :--- |
| `default` | Standard permission checking with prompts |
| `acceptEdits` | Auto-accept file edits and common filesystem commands for paths in the working directory or `additionalDirectories` |
| `auto` | Auto mode: a background classifier reviews commands and protected-directory writes |
| `dontAsk` | Auto-deny permission prompts (explicitly allowed tools still work) |
| `bypassPermissions` | Skip permission prompts |
| `plan` | Plan mode (read-only exploration) |

> **Warning:** Use `bypassPermissions` with caution. It skips permission prompts, allowing writes to `.git`, `.config/git`, `.claude`, `.vscode`, `.idea`, `.husky`, `.cargo`, `.devcontainer`, `.yarn`, and `.mvn`. Explicit `ask` rules and root/home-directory removals such as `rm -rf /` still prompt.

If the parent uses `bypassPermissions` or `acceptEdits`, this takes precedence and cannot be overridden. If the parent uses auto mode, the subagent inherits auto mode and any `permissionMode` in its frontmatter is ignored.

#### Preload skills into subagents

Use the `skills` field to inject skill content into a subagent's context at startup, giving it domain knowledge without runtime discovery.

```yaml
---
name: api-developer
description: Implement API endpoints following team conventions
skills:
  - api-conventions
  - error-handling-patterns
---

Implement API endpoints. Follow the conventions and patterns from the preloaded skills.
```

The full content of each listed skill is injected at startup. This controls which skills are preloaded, not which the subagent can access — without it, the subagent can still discover and invoke project/user/plugin skills through the Skill tool. To prevent skill invocation entirely, omit `Skill` from `tools` or add it to `disallowedTools`. You cannot preload skills that set `disable-model-invocation: true`. Missing/disabled listed skills are skipped with a debug-log warning.

> **Note:** This is the inverse of running a skill in a subagent. With `skills` in a subagent, the subagent controls the system prompt and loads skill content. With `context: fork` in a skill, the skill content is injected into the agent you specify.

#### Enable persistent memory

The `memory` field gives the subagent a persistent directory that survives across conversations.

```yaml
---
name: code-reviewer
description: Reviews code for quality and best practices
memory: user
---

You are a code reviewer. As you review code, update your agent memory with
patterns, conventions, and recurring issues you discover.
```

| Scope | Location | Use when |
| :--- | :--- | :--- |
| `user` | `~/.claude/agent-memory/<name-of-agent>/` | the subagent should remember learnings across all projects |
| `project` | `.claude/agent-memory/<name-of-agent>/` | the subagent's knowledge is project-specific and shareable via version control |
| `local` | `.claude/agent-memory-local/<name-of-agent>/` | the subagent's knowledge is project-specific but should not be checked into version control |

When memory is enabled: the system prompt includes instructions for reading/writing the memory directory; it includes the first 200 lines or 25KB of `MEMORY.md` (whichever comes first) with instructions to curate it if larger; and Read/Write/Edit tools are automatically enabled.

Tips: `project` is the recommended default scope. Ask the subagent to consult its memory before starting and to update it after finishing. Include memory instructions directly in the markdown body so it proactively maintains its knowledge base.

#### Conditional rules with hooks

For dynamic control over tool usage, use `PreToolUse` hooks to validate operations before they execute (allow some operations while blocking others). Example — read-only DB queries:

```yaml
---
name: db-reader
description: Execute read-only database queries
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
---
```

The hook script reads JSON from stdin, extracts the command, and exits with code 2 to block write operations:

```bash
#!/bin/bash
# ./scripts/validate-readonly-query.sh
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if echo "$COMMAND" | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b' > /dev/null; then
  echo "Blocked: Only SELECT queries are allowed" >&2
  exit 2
fi
exit 0
```

#### Disable specific subagents

Prevent Claude from using specific subagents via the `deny` array in settings, using `Agent(subagent-name)`:

```json
{
  "permissions": {
    "deny": ["Agent(Explore)", "Agent(my-custom-agent)"]
  }
}
```

Works for both built-in and custom subagents. Also available via `claude --disallowedTools "Agent(Explore)"`.

### Define hooks for subagents

Two ways to configure hooks:

1. **In the subagent's frontmatter** — run only while that subagent is active.
2. **In `settings.json`** — run in the main session when subagents start or stop.

> **Note:** Frontmatter hooks fire when the agent is spawned as a subagent (Agent tool or @-mention) and when the agent runs as the main session via `--agent` or the `agent` setting. In the main-session case they run alongside `settings.json` hooks.

Most common frontmatter events for subagents:

| Event | Matcher input | When it fires |
| :--- | :--- | :--- |
| `PreToolUse` | Tool name | Before the subagent uses a tool |
| `PostToolUse` | Tool name | After the subagent uses a tool |
| `Stop` | (none) | When the subagent finishes (converted to `SubagentStop` at runtime) |

Example combining both:

```yaml
---
name: code-reviewer
description: Review code changes with automatic linting
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh $TOOL_INPUT"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

Project-level hooks for subagent events (in `settings.json`):

| Event | Matcher input | When it fires |
| :--- | :--- | :--- |
| `SubagentStart` | Agent type name | When a subagent begins execution |
| `SubagentStop` | Agent type name | When a subagent completes |

```json
{
  "hooks": {
    "SubagentStart": [
      { "matcher": "db-agent", "hooks": [ { "type": "command", "command": "./scripts/setup-db-connection.sh" } ] }
    ],
    "SubagentStop": [
      { "hooks": [ { "type": "command", "command": "./scripts/cleanup-db-connection.sh" } ] }
    ]
  }
}
```

## Work with subagents

### Understand automatic delegation

Claude automatically delegates based on the task description in your request, the `description` field, and current context. To encourage proactive delegation, include phrases like "use proactively" in the description.

### Invoke subagents explicitly

Three patterns escalate from one-off suggestion to session-wide default:

- **Natural language**: name the subagent in your prompt; Claude decides whether to delegate. e.g. "Use the test-runner subagent to fix failing tests."
- **@-mention**: type `@` and pick the subagent from the typeahead — guarantees that subagent runs for one task. e.g. `@"code-reviewer (agent)" look at the auth changes`. Your full message still goes to Claude, which writes the task prompt; the @-mention controls which subagent, not the prompt. Plugin subagents appear under their scoped name (`my-plugin:code-reviewer`). You can type manually: `@agent-<name>` for local, `@agent-<scoped-name>` for plugin.
- **Session-wide**: `claude --agent <name>` makes the main thread take on that subagent's system prompt, tool restrictions, and model (replaces the default system prompt entirely, like `--system-prompt`; CLAUDE.md/memory still load). Persists on resume. For plugins, pass just the name, or a scoped name to disambiguate. To make it the project default, set `agent` in `.claude/settings.json` (`{ "agent": "code-reviewer" }`); the CLI flag overrides the setting.

### Run subagents in foreground or background

- **Foreground subagents** block the main conversation until complete. Permission prompts pass through to you as they come up.
- **Background subagents** run concurrently while you keep working. They use permissions already granted in the session and auto-deny any tool call that would otherwise prompt. If a background subagent needs to ask clarifying questions, that tool call fails but the subagent continues.

If a background subagent fails due to missing permissions, start a new foreground subagent with the same task to retry with interactive prompts.

Claude decides foreground vs background based on the task. You can also ask Claude to "run this in the background", or press **Ctrl+B** to background a running task. Set `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` to disable all background tasks. When `CLAUDE_CODE_FORK_SUBAGENT=1`, every subagent spawn runs in the background regardless of the `background` field.

### Common patterns

- **Isolate high-volume operations** — delegate verbose output (tests, docs, log processing) so only the summary returns: "Use a subagent to run the test suite and report only the failing tests with their error messages."
- **Run parallel research** — spawn multiple subagents for independent investigations: "Research the authentication, database, and API modules in parallel using separate subagents." (Many subagents returning detailed results can consume significant context. For sustained parallelism, use agent teams.)
- **Chain subagents** — sequence multi-step workflows: "Use the code-reviewer subagent to find performance issues, then use the optimizer subagent to fix them."

### Choose between subagents and main conversation

Use the **main conversation** when: the task needs frequent back-and-forth; multiple phases share significant context; you're making a quick targeted change; latency matters (subagents start fresh).

Use **subagents** when: the task produces verbose output you don't need in main context; you want to enforce tool restrictions/permissions; the work is self-contained and can return a summary.

Consider **Skills** instead when you want reusable prompts/workflows that run in the main conversation context. For a quick question about something already in your conversation, use `/btw` (sees full context, no tool access, answer discarded).

### Spawn nested subagents

As of Claude Code v2.1.172, a subagent can spawn its own subagents — useful when a delegated task splits into parallel subtasks. Only the top-level subagent's summary returns to you.

A nested subagent is configured the same way as a top-level one and resolves from the same scopes. Depth is counted as the number of subagent levels below the main conversation:

- **Foreground subagents**: can spawn at any depth. Each level blocks its parent, so the chain is self-limiting.
- **Background subagents**: a background subagent at depth five does not receive the Agent tool and cannot spawn further (fixed, non-configurable limit).

To prevent a subagent from spawning others, omit `Agent` from its `tools` or add it to `disallowedTools`. A fork cannot spawn another fork, but can spawn other subagent types (which count toward the depth limit).

### Manage subagent context

#### What loads at startup

Each subagent starts with a fresh, isolated context window. It does not see your conversation history, the skills you've invoked, or files Claude already read. The exception is a fork, which inherits the parent conversation.

A non-fork subagent's initial context contains:

- **System prompt**: the agent's own prompt plus environment details, not the full Claude Code system prompt.
- **Task message**: the delegation prompt Claude writes at handoff.
- **CLAUDE.md and memory**: every level of the memory hierarchy the main conversation loads (`~/.claude/CLAUDE.md`, project rules, `CLAUDE.local.md`, managed policy files). Explore and Plan skip this.
- **Git status**: a snapshot from the start of the parent session. Absent when not a Git repo or `includeGitInstructions` is `false`. Explore and Plan skip it.
- **Preloaded skills**: full content of any skill named in the `skills` field. Built-in agents don't preload skills.

Explore and Plan are the only subagents that omit CLAUDE.md and git status. If a rule must reach the subagent (e.g. "ignore the `vendor/` directory"), restate it in the delegation prompt.

#### Resume subagents

Each subagent invocation creates a new instance with fresh context. To continue an existing subagent's work, ask Claude to resume it — resumed subagents retain full conversation history.

When a subagent completes, Claude receives its agent ID. Built-in Explore and Plan agents are one-shot and return no agent ID (can't be resumed; use `general-purpose` or a custom subagent). Claude uses `SendMessage` with the agent's ID as the `to` field to resume — `SendMessage` is only available when agent teams are enabled (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). A stopped subagent that receives a `SendMessage` auto-resumes in the background.

Agent IDs / transcripts: `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`. Subagent transcripts persist independently — unaffected by main-conversation compaction, resumable after restart (resume the same session), and cleaned up per `cleanupPeriodDays` (default 30 days).

#### Auto-compaction

Subagents support automatic compaction using the same logic as the main conversation; `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` applies. Compaction events are logged in subagent transcripts as `compact_boundary` system entries with `compactMetadata.preTokens`.

## Fork the current conversation

> **Note:** Forked subagents require Claude Code v2.1.117 or later. From v2.1.161 the `/fork` command is enabled by default; on earlier versions it requires `CLAUDE_CODE_FORK_SUBAGENT=1`. Making forks the model's default spawn behavior is experimental.

A fork is a subagent that inherits the entire conversation so far instead of starting fresh. It sees the same system prompt, tools, model, and message history as the main session, so you can hand it a side task without re-explaining. The fork's own tool calls stay out of your conversation; only its final result returns. Use a fork when a named subagent would need too much background, or to try several approaches in parallel from the same starting point.

Set `CLAUDE_CODE_FORK_SUBAGENT=1` to enable explicitly, `0` to disable. Enabling fork mode: Claude spawns a fork whenever it would otherwise use general-purpose (named subagents like Explore still spawn normally); every subagent spawn runs in the background (set `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` to keep spawns synchronous).

Start a fork yourself with `/fork` plus a directive (Claude names the fork from the first words):

```text
/fork draft unit tests for the parser changes so far
```

The fork appears in a panel below your prompt and runs in the background; its result arrives as a message when finished.

### Observe and steer running forks

| Key | Action |
| :--- | :--- |
| `↑` / `↓` | Move between rows |
| `Enter` | Open the selected fork's transcript and send it follow-up messages |
| `x` | Dismiss a finished fork or stop a running one |
| `Esc` | Return focus to the prompt input |

### How forks differ from named subagents

|  | Fork | Named subagent |
| :--- | :--- | :--- |
| Context | Full conversation history | Fresh context with the prompt you pass |
| System prompt and tools | Same as main session | From the subagent's definition file |
| Model | Same as main session | From the subagent's `model` field |
| Permissions | Prompts surface in your terminal | Auto-denied when running in the background |
| Prompt cache | Shared with main session | Separate cache |

A fork's first request reuses the parent's prompt cache, making forking cheaper than a fresh subagent for same-context tasks. When Claude spawns a fork through the Agent tool, it can pass `isolation: "worktree"` so the fork's edits go to a separate git worktree.

### Limitations

`CLAUDE_CODE_FORK_SUBAGENT=1` enables fork mode in interactive mode, non-interactive mode, and the Agent SDK; `0` disables it everywhere. A fork cannot spawn further forks.

## Example subagents

> **Best practices:** Design focused subagents (each excels at one task) · Write detailed descriptions (Claude uses them to decide when to delegate) · Limit tool access (grant only necessary permissions) · Check into version control.

### Code reviewer

Read-only reviewer with limited tool access (no Edit/Write) and a detailed prompt.

```markdown
---
name: code-reviewer
description: Expert code review specialist. Proactively reviews code for quality, security, and maintainability. Use immediately after writing or modifying code.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are a senior code reviewer ensuring high standards of code quality and security.

When invoked:
1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:
- Code is clear and readable
- Functions and variables are well-named
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage
- Performance considerations addressed

Provide feedback organized by priority:
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.
```

### Debugger

Analyzes and fixes issues (includes Edit).

```markdown
---
name: debugger
description: Debugging specialist for errors, test failures, and unexpected behavior. Use proactively when encountering any issues.
tools: Read, Edit, Bash, Grep, Glob
---

You are an expert debugger specializing in root cause analysis.

When invoked:
1. Capture error message and stack trace
2. Identify reproduction steps
3. Isolate the failure location
4. Implement minimal fix
5. Verify solution works

Debugging process:
- Analyze error messages and logs
- Check recent code changes
- Form and test hypotheses
- Add strategic debug logging
- Inspect variable states

For each issue, provide:
- Root cause explanation
- Evidence supporting the diagnosis
- Specific code fix
- Testing approach
- Prevention recommendations

Focus on fixing the underlying issue, not the symptoms.
```

### Data scientist

Domain-specific subagent with `model: sonnet`.

```markdown
---
name: data-scientist
description: Data analysis expert for SQL queries, BigQuery operations, and data insights. Use proactively for data analysis tasks and queries.
tools: Bash, Read, Write
model: sonnet
---

You are a data scientist specializing in SQL and BigQuery analysis.

When invoked:
1. Understand the data analysis requirement
2. Write efficient SQL queries
3. Use BigQuery command line tools (bq) when appropriate
4. Analyze and summarize results
5. Present findings clearly

Key practices:
- Write optimized SQL queries with proper filters
- Use appropriate aggregations and joins
- Include comments explaining complex logic
- Format results for readability
- Provide data-driven recommendations

For each analysis:
- Explain the query approach
- Document any assumptions
- Highlight key findings
- Suggest next steps based on data

Always ensure queries are efficient and cost-effective.
```

### Database query validator

Allows Bash but validates commands via a `PreToolUse` hook to permit only read-only SQL.

```markdown
---
name: db-reader
description: Execute read-only database queries. Use when analyzing data or generating reports.
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
---

You are a database analyst with read-only access. Execute SELECT queries to answer questions about the data.

When asked to analyze data:
1. Identify which tables contain the relevant data
2. Write efficient SELECT queries with appropriate filters
3. Present results clearly with context

You cannot modify data. If asked to INSERT, UPDATE, DELETE, or modify schema, explain that you only have read access.
```

Validation script (exit code 2 blocks; make executable with `chmod +x`):

```bash
#!/bin/bash
# Blocks SQL write operations, allows SELECT queries
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
if [ -z "$COMMAND" ]; then
  exit 0
fi
if echo "$COMMAND" | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE)\b' > /dev/null; then
  echo "Blocked: Write operations not allowed. Use SELECT queries only." >&2
  exit 2
fi
exit 0
```

On Windows, write the validation script in PowerShell and add `shell: powershell` to the hook entry.
