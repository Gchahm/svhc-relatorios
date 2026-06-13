---
name: qqq-agent-name
# ^ required, kebab-case, unique; this is the agent's `subagent_type` (how it's invoked). Match the filename.
description: >-
    qqq What this agent does, and WHEN Claude should delegate to it. Lead with the capability, then the
    trigger conditions — this string is what the model matches on, so write it for recall, not prose.
# Only `name` and `description` are required. Everything below is optional — delete what you don't use.
tools: qqq Bash, Read, Edit, Write, Glob, Grep
# ^ the tools the agent may use. OMIT this line entirely to inherit ALL of the parent's tools.
#   To preload skills use the `skills:` field, not `Skill` here. Use `disallowedTools:` to subtract from inherited.
model: inherit
# ^ qqq one of: sonnet | opus | haiku | fable | a full model id | inherit (default: inherit).
color: blue
# ^ qqq red | blue | green | yellow | purple | orange | pink | cyan (display color in the task list).
memory: project
# ^ qqq optional persistent memory scope: user | project | local. DELETE this line if the agent needs no memory.
# Other optional fields (add only if needed — see references/sub-agents.md):
#   disallowedTools, permissionMode, maxTurns, skills, mcpServers, background, effort, isolation, hooks
hooks:
# ^ qqq optional lifecycle hooks scoped to this agent. DELETE this whole block if unused.
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: qqq "$CLAUDE_PROJECT_DIR/.claude/hooks/guard.sh"
---

# Purpose

qqq Who this agent is and the ONE job it owns end-to-end. State what it returns to the caller (its
final message is the result, not a human-facing reply).

## Variables

qqq Inputs the agent is given in its task prompt (and any paths/ids it derives), one per line.

## Codebase Structure

qqq What the agent needs to know about this repo — or, for a repo-agnostic agent, where it reads
repo-specific facts from (its `memory`, the constitution, the repo itself). Keep repo specifics out
of the body when the agent is meant to be portable.

## Instructions

qqq The standing rules/constraints (what it must always/never do).

## Workflow

qqq The ordered steps the agent follows.

## Report

qqq The exact shape of the agent's final message back to the caller.
