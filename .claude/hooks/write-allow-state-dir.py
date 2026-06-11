#!/usr/bin/env python3
"""PreToolUse Write guard for speckit-issue-loop: the loop may only write its own state dir.

Blocks (exit 2) any Write whose target is outside .cache/speckit-issue-loop/ — the loop is a
dispatcher; every other file belongs to an issue worker's context.
"""

import json
import os
import sys

ALLOWED_REL = ".cache/speckit-issue-loop"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    allowed_root = os.path.realpath(os.path.join(project_dir, ALLOWED_REL))
    target = os.path.realpath(
        file_path if os.path.isabs(file_path) else os.path.join(project_dir, file_path)
    )

    if target == allowed_root or target.startswith(allowed_root + os.sep):
        sys.exit(0)

    sys.stderr.write(
        f"Blocked (issue-orchestrator guard): the loop only writes {ALLOWED_REL}/ — "
        f"all other files are worker context. Attempted: {file_path}\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
