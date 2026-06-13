---
name: qqq-skill-name
description: qqq What this skill does. Use when qqq trigger conditions.
allowed-tools: Task, TaskOutput, Bash, Glob, Grep, Read, Edit, Write, NotebookEdit, WebFetch, TodoWrite, WebSearch, KillShell, AskUserQuestion, Skill, EnterPlanMode, ExitPlanMode
model: opus
context: fork
agent: general-purpose
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "echo 'pre-hook'"
          once: true
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "echo 'post-hook'"
  Stop:
    - hooks:
        - type: command
          command: "echo 'stop-hook'"
user-invocable: true
disable-model-invocation: false
---

# qqq Skill Title

## Purpose

qqq

## Variables

SOME_VAR: "qqq"

## Instructions

qqq

## Workflow

1. qqq
2. qqq
3. qqq

## Examples

qqq

## Report

qqq
