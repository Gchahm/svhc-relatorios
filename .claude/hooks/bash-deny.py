#!/usr/bin/env python3
"""PreToolUse Bash guard for the PR/issue automation skills.

Reads the hook payload JSON on stdin and exits 2 (block, reason on stderr feeds back to the
model) when the Bash command matches a pattern the given --profile must never run; exits 0
(allow) otherwise. Wired into skill frontmatter `hooks:` blocks — see:
  pr-review-loop      --profile review-orchestrator
  speckit-issue-loop  --profile issue-orchestrator
  pr-review           --profile reviewer
"""

import argparse
import json
import re
import sys

# A mutating `gh api` call against PR reviews/comments (the loop legitimately GETs these).
_POST_REVIEWS = (
    r"(?s)\bgh\s+api\b(?=.*\bpulls/[^\s]*/(?:reviews|comments)\b)"
    r"(?=.*(?:-X\s*POST|--method\s*POST|--input|\s-f\s|\s-F\s))"
)

PROFILES = {
    "review-orchestrator": [
        (
            r"\bgh\s+pr\s+(diff|merge|close|review|edit)\b",
            "the loop never reviews or mutates PRs — delegate to a pr-review worker (Agent tool / SendMessage)",
        ),
        (r"\bgit\s+push\b", "the loop never pushes"),
        (_POST_REVIEWS, "posting reviews/comments is the pr-review worker's job"),
    ],
    "issue-orchestrator": [
        (
            r"\bgh\s+pr\s+(diff|merge|close|review|edit)\b",
            "the loop never reads diffs or mutates PRs — relay the event to the issue's worker via SendMessage",
        ),
        (
            r"\bgit\s+(push|commit|merge|rebase|checkout|switch|reset)\b",
            "the loop never touches the working tree or the remote — implementation lives in the issue workers",
        ),
        (_POST_REVIEWS, "posting reviews/comments is worker context"),
    ],
    "reviewer": [
        (
            r"\bgh\s+pr\s+(merge|close|edit|ready)\b",
            "the reviewer is read-only on PR state — the APPROVE verdict is the go-ahead; the PR's owner merges",
        ),
        (r"\bgit\s+(push|commit|merge|rebase)\b", "the reviewer never modifies code"),
        (
            r"\bgit\s+(checkout|switch)\b",
            "never check the PR branch out — use `git fetch origin pull/<n>/head` + `git show/diff FETCH_HEAD`",
        ),
    ],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    args = parser.parse_args()

    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # malformed payload — never wedge the session

    command = (payload.get("tool_input") or {}).get("command") or ""
    for pattern, reason in PROFILES[args.profile]:
        if re.search(pattern, command):
            sys.stderr.write(
                f"Blocked ({args.profile} guard): {reason}.\nCommand: {command[:200]}\n"
            )
            sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
