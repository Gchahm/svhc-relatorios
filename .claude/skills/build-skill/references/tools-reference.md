# Tools reference

> Source: https://code.claude.com/docs/en/tools-reference
> Complete reference for the tools Claude Code can use, including permission requirements and per-tool behavior.

Claude Code has access to a set of built-in tools that help it understand and modify your codebase. The tool names are the exact strings you use in [permission rules](https://code.claude.com/docs/en/permissions#tool-specific-permission-rules), [subagent tool lists](https://code.claude.com/docs/en/sub-agents), and [hook matchers](https://code.claude.com/docs/en/hooks). To disable a tool entirely, add its name to the `deny` array in your permission settings.

To add custom tools, connect an [MCP server](https://code.claude.com/docs/en/mcp). To extend Claude with reusable prompt-based workflows, write a [skill](https://code.claude.com/docs/en/skills), which runs through the existing `Skill` tool rather than adding a new tool entry.

## Tool catalog

| Tool | Description | Permission Required |
| :--- | :--- | :--- |
| `Agent` | Spawns a subagent with its own context window to handle a task. See [Agent tool behavior](#agent-tool-behavior) | No |
| `AskUserQuestion` | Asks multiple-choice questions to gather requirements or clarify ambiguity | No |
| `Bash` | Executes shell commands in your environment. See [Bash tool behavior](#bash-tool-behavior) | Yes |
| `CronCreate` | Schedules a recurring or one-shot prompt within the current session. Tasks are session-scoped and restored on `--resume`/`--continue` if unexpired | No |
| `CronDelete` | Cancels a scheduled task by ID | No |
| `CronList` | Lists all scheduled tasks in the session | No |
| `Edit` | Makes targeted edits to specific files. See [Edit tool behavior](#edit-tool-behavior) | Yes |
| `EnterPlanMode` | Switches to plan mode to design an approach before coding | No |
| `EnterWorktree` | Creates an isolated git worktree and switches into it. Pass a `path` to switch into an existing worktree instead of creating one. From within a worktree session, or a subagent with a pinned working directory (`isolation: worktree`), only the `path` form is available and the target must be under `.claude/worktrees/` | No |
| `ExitPlanMode` | Presents a plan for approval and exits plan mode | Yes |
| `ExitWorktree` | Exits a worktree session and returns to the original directory. Not available to subagents that already run in their own working directory | No |
| `Glob` | Finds files based on pattern matching. See [Glob tool behavior](#glob-tool-behavior) | No |
| `Grep` | Searches for patterns in file contents. See [Grep tool behavior](#grep-tool-behavior) | No |
| `ListMcpResourcesTool` | Lists resources exposed by connected MCP servers | No |
| `LSP` | Code intelligence via language servers: jump to definitions, find references, report type errors/warnings. See [LSP tool behavior](#lsp-tool-behavior) | No |
| `Monitor` | Runs a command in the background and feeds each output line back to Claude, so it can react to log entries, file changes, or polled status mid-conversation. See [Monitor tool](#monitor-tool) | Yes |
| `NotebookEdit` | Modifies Jupyter notebook cells. See [NotebookEdit tool behavior](#notebookedit-tool-behavior) | Yes |
| `PowerShell` | Executes PowerShell commands natively. See [PowerShell tool](#powershell-tool) for availability | Yes |
| `PushNotification` | Sends a desktop notification, and a phone push when Remote Control is connected, so a long-running or scheduled task can reach you when you step away. Push delivery runs through Anthropic-hosted infrastructure (not on Bedrock, Vertex AI, or Foundry) | No |
| `Read` | Reads the contents of files. See [Read tool behavior](#read-tool-behavior) | No |
| `ReadMcpResourceTool` | Reads a specific MCP resource by URI | No |
| `RemoteTrigger` | Creates, updates, runs, and lists Routines on claude.ai. Backs the `/schedule` command. Routines require a Pro/Max/Team/Enterprise plan (not on Bedrock, Vertex AI, or Foundry) | No |
| `ScheduleWakeup` | Reschedules the next iteration of a self-paced `/loop`. Claude calls this at the end of each iteration to pick when the next runs (one minute to one hour out); you don't call it directly. The pending wakeup appears in `session_crons` in Stop hook input. Not available on Bedrock, Vertex AI, or Foundry | No |
| `SendMessage` | Sends a message to an agent-team teammate, or resumes a subagent by its agent ID. Stopped subagents auto-resume in the background. Only when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set | No |
| `ShareOnboardingGuide` | Uploads `ONBOARDING.md` and returns a share link teammates can open in Claude Code. Called from `/team-onboarding`. Available to claude.ai subscribers on Pro/Max/Team/Enterprise plans | Yes |
| `Skill` | Executes a skill within the main conversation | Yes |
| `TaskCreate` | Creates a new task in the task list | No |
| `TaskGet` | Retrieves full details for a specific task | No |
| `TaskList` | Lists all tasks with their current status | No |
| `TaskOutput` | (Deprecated) Retrieves output from a background task. Prefer `Read` on the task's output file path | No |
| `TaskStop` | Kills a running background task by ID | No |
| `TaskUpdate` | Updates task status, dependencies, details, or deletes tasks | No |
| `TeamCreate` | Creates an agent team with multiple teammates. Only when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set | No |
| `TeamDelete` | Disbands an agent team and cleans up teammate processes. Only when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set | No |
| `TodoWrite` | Manages the session task checklist. Disabled by default as of v2.1.142 in favor of `TaskCreate`/`TaskGet`/`TaskList`/`TaskUpdate`. Set `CLAUDE_CODE_ENABLE_TASKS=0` to re-enable | No |
| `ToolSearch` | Searches for and loads deferred tools when tool search is enabled | No |
| `WaitForMcpServers` | Waits for MCP servers still connecting in the background, so a request can use their tools without restarting. Only appears when tool search is disabled (`ToolSearch` handles the wait when enabled) | No |
| `WebFetch` | Fetches content from a specified URL. See [WebFetch tool behavior](#webfetch-tool-behavior) | Yes |
| `WebSearch` | Performs web searches. See [WebSearch tool behavior](#websearch-tool-behavior) | Yes |
| `Workflow` | Runs a dynamic workflow: a script that orchestrates many subagents in the background and returns one consolidated result | Yes |
| `Write` | Creates or overwrites files. See [Write tool behavior](#write-tool-behavior) | Yes |

## Configure tools with permission rules and hooks

For the most part, Claude decides when to use these tools. You reference tool names directly when defining permissions and other configuration:

- in `permissions.allow` and `permissions.deny` in settings, and the `/permissions` interface
- in the `--allowedTools` and `--disallowedTools` CLI flags
- in the Agent SDK's `allowedTools` and `disallowedTools` options
- in a subagent's `tools` or `disallowedTools` frontmatter
- in a skill's `allowed-tools` frontmatter
- in a hook's `if` condition

All of these accept the same rule format, `ToolName(specifier)`. The specifier depends on the tool, and several tools share a format:

| Rule format | Applies to | Details |
| :--- | :--- | :--- |
| `Bash(npm run *)` | Bash, Monitor | Command pattern matching |
| `PowerShell(Get-ChildItem *)` | PowerShell | Command pattern matching |
| `Read(~/secrets/**)` | Read, Grep, Glob, LSP | Path pattern matching |
| `Edit(/src/**)` | Edit, Write, NotebookEdit | Path pattern matching |
| `Skill(deploy *)` | Skill | Skill name matching |
| `Agent(Explore)` | Agent | Subagent type matching |
| `WebFetch(domain:example.com)` | WebFetch | Domain matching |
| `WebSearch` | WebSearch | No specifier; allow or deny the tool as a whole |

Tools not listed here, such as `ExitPlanMode` or `ShareOnboardingGuide`, accept only the bare tool name with no specifier.

An `Edit(...)` allow rule also grants read access to the same path, so you do not need a matching `Read(...)` rule.

Hook `matcher` fields use bare tool names, not the parenthesized rule format. For the field names each tool passes to `tool_input` in hooks, see the PreToolUse input reference.

## Agent tool behavior

The Agent tool spawns a subagent in a separate context window. The subagent works through its task autonomously, then returns a single text result to the parent conversation. The parent does not see the subagent's intermediate tool calls or outputs, only that final result. To cap how many turns a subagent runs, set `maxTurns` in the subagent definition.

The same Agent tool also launches forked subagents when fork mode is enabled. A fork inherits the full parent conversation instead of starting fresh, always runs in the background, and still surfaces permission prompts in your terminal. The rest of this section describes named subagents.

Which tools a named subagent can use depends on the `tools` and `disallowedTools` fields in the subagent definition:

- **Neither field set**: the subagent inherits every tool available to the parent.
- **`tools` only**: the subagent gets only the listed tools.
- **`disallowedTools` only**: the subagent gets every parent tool except the listed ones.
- **Both set**: `disallowedTools` takes precedence. A tool listed in both is removed.

Launching the subagent does not itself prompt for permission. The subagent's own tool calls are checked against your permission rules as it runs:

- **Foreground subagents** show the same permission prompts you would see in the main conversation, at the moment each tool call happens.
- **Background subagents** do not show prompts. They run with the permissions already granted in the session and auto-deny any tool call that would otherwise prompt. After a denial, the subagent keeps going without that tool.

To limit what a subagent can reach in the first place, narrow its `tools` field, leave Bash off the list, or set deny rules in your settings.

## Bash tool behavior

The Bash tool runs each command in a separate process with the following persistence behavior:

- When Claude runs `cd` in the main session, the new working directory carries over to later Bash commands as long as it stays inside the project directory or an additional working directory you added with `--add-dir`, `/add-dir`, or `additionalDirectories` in settings. Subagent sessions never carry over working directory changes.
  - If `cd` lands outside those directories, Claude Code resets to the project directory and appends `Shell cwd was reset to <dir>` to the tool result.
  - To disable this carry-over so every Bash command starts in the project directory, set `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1`.
- Environment variables do not persist. An `export` in one command will not be available in the next.
- Aliases and shell functions defined in your shell startup file are available. At session start, Claude Code sources `~/.zshrc`, `~/.bashrc`, or `~/.profile` depending on your shell, captures the resulting aliases, functions, and shell options, and applies them to every Bash command.

Activate your virtualenv or conda environment before launching Claude Code. To make environment variables persist across Bash commands, set `CLAUDE_ENV_FILE` to a shell script before launching Claude Code, or use a SessionStart hook to populate it dynamically.

Two limits bound each command:

- **Timeout**: two minutes by default. Claude can request up to 10 minutes per command with the `timeout` parameter. Override the default and ceiling with `BASH_DEFAULT_TIMEOUT_MS` and `BASH_MAX_TIMEOUT_MS`.
- **Output length**: 30,000 characters by default. When a command produces more, Claude Code saves the full output to a file in the session directory and gives Claude the file path plus a short preview from the start. Raise the limit with `BASH_MAX_OUTPUT_LENGTH`, up to a hard ceiling of 150,000 characters.

For long-running processes such as dev servers or watch builds, Claude can set `run_in_background: true` to start the command as a background task and continue working while it runs. List and stop background tasks with `/tasks`.

## Edit tool behavior

The Edit tool performs exact string replacement. It takes an `old_string` and a `new_string` and replaces the first with the second. It does not use regex or fuzzy matching.

Three checks must pass for an edit to apply:

- **Read-before-edit**: Claude must have read the file in the current conversation, and the file must not have changed on disk since that read. This check runs first, before any string matching.
- **Match**: `old_string` must appear in the file exactly as written. A single character of whitespace or indentation difference is enough to miss.
- **Uniqueness**: `old_string` must appear exactly once. When it appears more than once, Claude either supplies a longer string with enough surrounding context to pin down one occurrence, or sets `replace_all: true` to replace them all.

Viewing a file with Bash also satisfies the read-before-edit requirement when the command is `cat`, `head`, `tail`, `sed -n 'X,Yp'`, `grep`, `egrep`, or `fgrep` on a single file with no pipes or redirects. Piped output and other Bash commands do not count.

This affects edit eligibility only, not permissions. Read and Edit deny rules also apply to file commands Claude Code recognizes in Bash, such as `cat`, `head`, `tail`, `sed`, and `grep`, but not to arbitrary subprocesses that read or write files indirectly. For OS-level enforcement that covers every process, enable the sandbox.

## Glob tool behavior

The Glob tool finds files by name pattern. It supports standard glob syntax including `**` for recursive directory matching:

- `**/*.js` matches all `.js` files at any depth
- `src/**/*.ts` matches all `.ts` files under `src/`
- `*.{json,yaml}` matches `.json` and `.yaml` files in the current directory

Results are sorted by modification time and capped at 100 files. If the cap is hit, Claude sees a truncation flag in the result and can narrow the pattern.

Glob does not respect `.gitignore` by default. To make Glob respect `.gitignore`, set `CLAUDE_CODE_GLOB_NO_IGNORE=false` before launching Claude Code.

## Grep tool behavior

The Grep tool searches file contents for patterns. Where Glob finds files by name, Grep finds lines inside them.

Grep is built on ripgrep and uses ripgrep's regex syntax, not POSIX grep. Patterns that include regex metacharacters need escaping. For example, finding `interface{}` in Go code takes the pattern `interface\{\}`.

Three output modes control what comes back:

- `files_with_matches`: file paths only, no line content. This is the default.
- `content`: matching lines with file and line number.
- `count`: match count per file.

Claude can scope results by file with the `glob` parameter, such as `**/*.tsx`, or by language with the `type` parameter, such as `py` or `rust`. By default, patterns match within a single line. Claude can set `multiline: true` to match across line boundaries.

Grep respects `.gitignore`, so gitignored files are skipped. To search a gitignored file, Claude passes its path directly.

## LSP tool behavior

The LSP tool gives Claude code intelligence from a running language server. After each file edit, it automatically reports type errors and warnings. Claude can also call it directly to navigate code: jump to a symbol's definition, find references, get type information, list symbols, search by name across the workspace, find implementations, or trace call hierarchies.

The tool is inactive until you install a code intelligence plugin for your language.

## Monitor tool

> Requires Claude Code v2.1.98 or later.

The Monitor tool lets Claude watch something in the background and react when it changes, without pausing the conversation: tail a log file and flag errors, poll a PR or CI job, watch a directory for changes, or track output from any long-running script.

Claude writes a small script for the watch, runs it in the background, and receives each output line as it arrives. Stop a monitor by asking Claude to cancel it or by ending the session.

Monitor uses the same permission rules as Bash. It is not available on Bedrock, Vertex AI, or Foundry, nor when `DISABLE_TELEMETRY` or `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` is set.

## NotebookEdit tool behavior

NotebookEdit modifies a Jupyter notebook one cell at a time, targeting cells by their `cell_id`. Three edit modes:

- `replace`: overwrite the cell's source. This is the default.
- `insert`: add a new cell after the target. With no `cell_id`, the new cell goes at the start. Requires `cell_type` set to `code` or `markdown`.
- `delete`: remove the target cell.

Permission rules use the `Edit(...)` path format. A rule like `Edit(notebooks/**)` covers NotebookEdit calls on files in that directory.

## PowerShell tool

The PowerShell tool lets Claude run PowerShell commands natively. On Windows without Git Bash, the tool is enabled automatically. On Windows with Git Bash it is rolling out progressively. On Linux, macOS, and WSL it is opt-in (requires PowerShell 7+).

Enable it by setting `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` in your environment or `settings.json`. Claude Code spawns PowerShell with `-ExecutionPolicy Bypass` at process scope only; set `CLAUDE_CODE_POWERSHELL_RESPECT_EXECUTION_POLICY=1` to respect the machine's effective policy.

Shell selection settings: `"defaultShell": "powershell"` (interactive `!` commands), `"shell": "powershell"` on a command hook, and `shell: powershell` in skill frontmatter.

## Read tool behavior

The Read tool takes a file path and returns the contents with line numbers. Claude always passes absolute paths.

By default Read returns the file from the start. When a whole-file read exceeds the token limit, Read returns the first page with a `PARTIAL view` notice telling Claude how to read more with `offset` and `limit`. A read that passes an explicit `offset`/`limit` and still exceeds the limit returns an error.

Read handles several file types beyond plain text:

- **Images**: returned as visual content Claude can see, not raw bytes. Large images are resized/recompressed to fit the model's image limits.
- **PDFs**: short `.pdf` files read whole; for PDFs longer than 10 pages, read in ranges with a `pages` parameter (e.g. `"1-5"`), up to 20 pages at a time.
- **Jupyter notebooks**: `.ipynb` files return all cells with their outputs.

Read only reads files, not directories. Use `ls` via Bash to list directory contents.

## WebFetch tool behavior

WebFetch takes a URL and a prompt describing what to extract. It fetches the page, converts HTML to Markdown, and runs the prompt against the content using a small, fast model. For most fetches Claude receives that model's answer, not the raw page — WebFetch is lossy by design.

Behaviors that shape the response:

- HTTP URLs are automatically upgraded to HTTPS.
- Large pages are truncated to a fixed character limit before processing.
- Responses are cached for 15 minutes.
- When a URL redirects to a different host, WebFetch returns a text result naming the original and redirect target instead of following it. Claude then fetches the new URL with a second call.

In default and `acceptEdits` modes, WebFetch prompts the first time it reaches a new domain, except a built-in set of preapproved documentation domains. Add a `WebFetch(domain:example.com)` rule to allow another domain in advance. `auto` and `bypassPermissions` modes skip the prompt entirely.

## WebSearch tool behavior

WebSearch runs a query against Anthropic's web search backend and returns result titles and URLs. It does not fetch the result pages — follow up with WebFetch to read one.

The tool may issue up to eight backend searches per call. Claude can scope results with `allowed_domains` or `blocked_domains` (the two lists cannot be combined in a single call).

WebSearch permission rules take no specifier. A bare `WebSearch` entry in `allow` or `deny` is the only form. Available on the Claude API and Microsoft Foundry; on Vertex AI with Claude 4 models; not on Bedrock.

## Write tool behavior

The Write tool creates a new file or overwrites an existing one with the full content provided. It does not append or merge.

If the target path already exists, Claude must have read that file at least once in the current conversation before overwriting it. A Write to an unread existing file fails with an error. This constraint does not apply to new files.

For partial changes to an existing file, use Edit instead of Write.

## Check which tools are available

Your exact tool set depends on your provider, platform, and settings. To check what's loaded in a running session, ask Claude directly ("What tools do you have access to?"). For exact MCP tool names, run `/mcp`.
