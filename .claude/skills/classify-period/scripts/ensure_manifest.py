#!/usr/bin/env python3
"""PreToolUse hook for the `classify-period` skill: ensure the work manifest exists.

Fires before each Read. When the skill goes to read a period's work manifest
(`<period>.extract-todo.json`) and it is not on disk yet, this creates it by
running the deterministic `docs-plan` command for that period — so the manifest is
generated lazily by the hook, not by the agent. The period and data dir are taken
from the manifest path. Any other read passes straight through.

Exit 0 = allow the read (manifest present, just created, or not our concern).
Exit 2 = block with a message (could not produce the manifest).

Input: the PreToolUse hook JSON on stdin (uses `tool_input.file_path`). For manual
testing, a path may be passed as the first CLI argument. Stdlib only — it shells
out to `uv run python -m scraper docs-plan`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SUFFIX = ".extract-todo.json"


def _fail(msg: str) -> None:
    sys.stderr.write(f"[classify-period] {msg}\n")
    sys.exit(2)


def _project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _target_path() -> str | None:
    """The path the Read tool is about to open, from CLI arg or hook stdin JSON."""
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path")
    return path.strip() if isinstance(path, str) and path.strip() else None


def main() -> None:
    target = _target_path()
    if target is None:
        sys.exit(0)

    project_dir = _project_dir()
    tp = Path(target)
    if not tp.is_absolute():
        tp = Path(project_dir) / tp

    # Only a manifest read concerns us.
    if not tp.name.endswith(SUFFIX):
        sys.exit(0)
    # Already present — nothing to do; let the read proceed.
    if tp.exists():
        sys.exit(0)

    period = tp.name[: -len(SUFFIX)]
    if not period:
        _fail(f"could not derive a period from `{tp.name}`")

    data_dir = str(tp.parent)
    scripts_dir = Path(project_dir) / "scripts"
    if not scripts_dir.is_dir():
        _fail(f"scripts/ directory not found under {project_dir}; cannot run docs-plan")

    try:
        proc = subprocess.run(
            ["uv", "run", "python", "-m", "scraper", "docs-plan", "--periodo", period, "--data-dir", data_dir],
            cwd=str(scripts_dir),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        _fail(f"failed to run docs-plan for {period}: {e}")

    if proc.returncode != 0:
        _fail(f"docs-plan failed for {period} (exit {proc.returncode}): {proc.stderr.strip()[-500:]}")

    if not tp.exists():
        # docs-plan ran but selected nothing (e.g. every document already analyzed).
        _fail(
            f"docs-plan produced no manifest for {period} — likely nothing to extract "
            f"(all documents already analyzed). Re-run `docs-plan --periodo {period} --reanalyze` "
            f"if you intend to re-extract. docs-plan said: {proc.stdout.strip()[-300:]}"
        )

    print(f"[classify-period] created manifest for {period} via docs-plan")
    sys.exit(0)


if __name__ == "__main__":
    main()
