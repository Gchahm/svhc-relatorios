#!/usr/bin/env python3
"""Global PreToolUse Bash hook: `gh pr merge` only when the PR's reviewDecision is APPROVED.

Registered in .claude/settings.json so it covers EVERY context (main session, skill, worker
subagent — including worktrees, via the payload cwd). Non-merge commands pass through untouched.
Fails closed: if the review state cannot be verified, the merge is blocked.
"""

import json
import re
import subprocess
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    # Match only in command position (line start or after a shell separator), so prose
    # mentions of the command — commit messages, docs — don't trigger the gate.
    match = re.search(
        r"(?m)(?:^|&&|\|\||[;|]|\$\(|`)\s*gh\s+pr\s+merge\b([^\n;|&]*)", command
    )
    if not match:
        sys.exit(0)

    # First non-flag token after `merge` is the PR selector (number/url/branch); may be absent.
    selector = next(
        (tok for tok in match.group(1).split() if not tok.startswith("-")), None
    )
    view_cmd = ["gh", "pr", "view"] + ([selector] if selector else []) + [
        "--json", "reviewDecision", "-q", ".reviewDecision",
    ]

    try:
        result = subprocess.run(
            view_cmd, capture_output=True, text=True, timeout=30,
            cwd=payload.get("cwd") or None,
        )
    except Exception as exc:
        sys.stderr.write(f"merge gate: could not verify review state ({exc}); merge blocked.\n")
        sys.exit(2)

    if result.returncode != 0:
        sys.stderr.write(
            f"merge gate: `gh pr view` failed ({result.stderr.strip()}); merge blocked.\n"
        )
        sys.exit(2)

    decision = result.stdout.strip()
    if decision != "APPROVED":
        sys.stderr.write(
            f"merge gate: reviewDecision is '{decision or 'none'}', not APPROVED — merging is "
            "approval-gated. Get a review approval first (or a human merges via the GitHub UI).\n"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
