#!/usr/bin/env python3
"""Global PreToolUse Bash hook: PR merges only with an approval at the current head commit.

Intercepts both merge paths — `gh pr merge <sel>` and `gh api .../pulls/<n>/merge` — and allows
the merge only when one of these holds:
  - the PR's reviewDecision is APPROVED (works when the reviewer is a distinct account), or
  - a review AT THE CURRENT HEAD COMMIT is APPROVED or carries the `VERDICT: approve` fallback
    body the pr-review skill posts when GitHub rejects self-approval on a same-account PR.

The head-commit check means an approval is invalidated by any later push. Registered in
.claude/settings.json so it covers every context (main session, skill, worker subagent — the
payload cwd resolves the right repo). Non-merge commands pass through. Fails closed: if the
review state cannot be verified, the merge is blocked.
"""

import json
import re
import subprocess
import sys

# Command-position anchoring so prose mentions (commit messages, docs) don't trigger the gate.
_CMD_POS = r"(?m)(?:^|&&|\|\||[;|]|\$\(|`)\s*"
_GH_PR_MERGE = _CMD_POS + r"gh\s+pr\s+merge\b([^\n;|&]*)"
_GH_API_MERGE = _CMD_POS + r"gh\s+api\b[^\n;|&]*\bpulls/(\d+)/merge\b"


def _gh(args, cwd):
    return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=30, cwd=cwd)


def _block(message):
    sys.stderr.write(f"merge gate: {message}\n")
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or None

    selector = None
    pr_merge = re.search(_GH_PR_MERGE, command)
    api_merge = re.search(_GH_API_MERGE, command)
    if pr_merge:
        # First non-flag token after `merge` is the PR selector (number/url/branch); may be absent.
        selector = next(
            (tok for tok in pr_merge.group(1).split() if not tok.startswith("-")), None
        )
    elif api_merge:
        selector = api_merge.group(1)
    else:
        sys.exit(0)

    try:
        view = _gh(
            ["pr", "view", *([selector] if selector else []),
             "--json", "number,reviewDecision,headRefOid"],
            cwd,
        )
        if view.returncode != 0:
            _block(f"`gh pr view` failed ({view.stderr.strip()}); merge blocked.")
        info = json.loads(view.stdout)

        if info.get("reviewDecision") == "APPROVED":
            sys.exit(0)

        # Single-account fallback: GitHub rejects self-approval, so the pr-review skill posts a
        # COMMENT review starting with `VERDICT: approve`. Honor it (or a plain APPROVED review
        # that branch protection doesn't surface in reviewDecision) only at the current head.
        head = info.get("headRefOid") or ""
        reviews_resp = _gh(
            ["api", f"repos/{{owner}}/{{repo}}/pulls/{info['number']}/reviews", "--paginate"],
            cwd,
        )
        if reviews_resp.returncode != 0:
            _block(f"could not list reviews ({reviews_resp.stderr.strip()}); merge blocked.")
        for review in json.loads(reviews_resp.stdout):
            if review.get("commit_id") != head:
                continue  # approval predates the latest push — not valid for this head
            if review.get("state") == "APPROVED":
                sys.exit(0)
            body = (review.get("body") or "").strip().lower()
            if body.startswith("verdict: approve"):
                sys.exit(0)
    except SystemExit:
        raise
    except Exception as exc:
        _block(f"could not verify review state ({exc}); merge blocked.")

    _block(
        "no approval found at the current head commit (reviewDecision "
        f"'{info.get('reviewDecision') or 'none'}', no APPROVED or 'VERDICT: approve' review at "
        f"{head[:7]}). Get the PR reviewed/re-reviewed first — merging is approval-gated."
    )


if __name__ == "__main__":
    main()
