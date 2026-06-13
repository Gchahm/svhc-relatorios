#!/usr/bin/env python3
"""Deterministic decision engine for the implement-loop skill.

The loop orchestrator (a cheap model) calls this once per pass to learn the ONE action to take, so
the decision logic — scope/dependency ordering, worker liveness, completion detection — lives in
code, not in the model's head. All state lives in `.cache/implement-loop/state.json`; THIS SCRIPT IS
ITS ONLY WRITER. GitHub is the source of truth for issue/PR state and is read **read-only** here —
including the last review's commit_id vs the PR head, to decide reviewer dispatch (the loop's Bash
guard is `implement-orchestrator`, which permits reading reviews but blocks merges/pushes/diffs/
posting reviews).

Subcommands
-----------
  next [scope-args...]            Reconcile with GitHub + decide. Prints one JSON object:
                                  {"action": <action>, "report": [<line>, ...], ...fields}.
  dispatched --issue N --agent ID Record a freshly spawned developer as current_work.
  resumed --agent ID              Record a resumed/respawned developer (resets the liveness clock,
                                  increments the restart counter).
  review-dispatched --agent ID --head SHA
                                  Record a reviewer the orchestrator just spawned for the PR head.

Actions returned by `next` (the DEVELOPER track) — ONE call per pass
--------------------------------------------------------------------
  dispatch  Spawn a new `developer` worker for {issue,title} (use templates/dispatch-prompt.md).
  resume    The developer is not running but its issue is still open — it died; continue it
            (use templates/catchup-prompt.md), in place via SendMessage or via a fresh spawn.
  wait      A developer is alive, OR the next issue is dependency-blocked — nothing to dispatch.
  done      Every scoped issue is terminal — disarm the loop (CronDelete).
  error     The current issue exceeded the restart cap — surface it; current_work is cleared so the
            next pass moves on.

Extra fields any action may also carry (the REVIEWER track + cleanup), handled before/around the
developer action in the SAME pass (so the loop stays one `next` call per pass):
  "stop_agent": <id>      A developer whose issue is now closed (work done) but still alive — i.e. it
                          finished the merge but is stuck and never replied. TaskStop it (a background
                          worker spawn is a `local_agent` task whose task_id IS its agent id) so the
                          zombie can't linger.
  "stop_reviewer": <id>   A reviewer to TaskStop: a stale reviewer on an old head, a lingering one
                          whose head is now reviewed, or an orphaned one (issue closed / dev errored).
  "review": {"spawn": true, "pr": N, "head": SHA, "issue": N}
                          The PR's current head has NOT been reviewed and no reviewer is alive on it —
                          spawn a `reviewer` worker (use templates/review-prompt.md), then record it
                          with `review-dispatched`. GitHub is ground truth for "reviewed at head"
                          (my last review's commit_id vs headRefOid), so this needs no completion
                          tracking — only reviewer liveness, to avoid double-spawning.

The decision tree (matches the skill's Workflow):
  current_work?
    no  -> pick next eligible issue (dependency gate + scope order) -> dispatch | wait | done
    yes -> issue closed (PR merged)? -> clear current_work; reap still-alive workers via stop_agent /
                                        stop_reviewer; then dispatch the next | done | wait.
                                        (Closed WINS over agent-alive: a stuck worker never stalls it.)
           else -> reviewer track (review / stop_reviewer) + developer track (wait | resume | error),
                   both folded onto the one returned action.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

STATE_REL = ".cache/implement-loop/state.json"
# Liveness comes from each subagent's HARNESS-OWNED transcript mtime, NOT a self-touched heartbeat.
# A heartbeat (a `while true; touch …` loop) orphans — it outlives the agent and lies "alive" forever
# (observed in practice). The transcript `agent-<id>.jsonl` is written by the harness as the agent
# works and freezes the moment it stops, so it can't be orphaned.
_TRANSCRIPT_GLOB = "~/.claude/projects/*/*/subagents/agent-{id}.jsonl"

GRACE_SECONDS = 180          # right after a spawn the transcript may not exist yet — treat as alive
AGENT_STALE_SECONDS = 1200   # transcript silent ≥20 min => dead/idle (tolerates a long single tool
                             # call like a build; the pass interval is ~14 min)
MAX_RESTARTS = 2             # resumes of one issue before we give up and surface an error

_DEP_RE = re.compile(r"(?im)^\s*(?:depends on|blocked by)\s*#(\d+)\b")
_TASK_RE = re.compile(r"(?im)^\s*-\s*\[\s\]\s*#(\d+)\b")  # an unchecked task-list item is a blocker


# ---------------------------------------------------------------- state I/O

def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def state_path():
    return os.path.join(project_dir(), STATE_REL)


def load_state():
    try:
        with open(state_path()) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(state):
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(state, fh, indent=2)


# ---------------------------------------------------------------- GitHub (read-only)

def gh_json(args):
    """Run `gh ... --json ...` and parse stdout; return None on any failure (never raise)."""
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout or "null")
    except ValueError:
        return None


def gh_issue_closed(number):
    """True if closed, False if open, None if unknown (gh failed)."""
    data = gh_json(["issue", "view", str(number), "--json", "state"])
    if data is None:
        return None
    return (data.get("state") or "").upper() == "CLOSED"


def gh_pr_open_head(number):
    """The PR's current head commit if it is OPEN, else None (closed/merged/gh failure)."""
    data = gh_json(["pr", "view", str(number), "--json", "number,state,headRefOid"])
    if not data or (data.get("state") or "").upper() != "OPEN":
        return None
    return data.get("headRefOid")


def _gh_scalar(args):
    """Run a gh command whose --jq yields a bare scalar; return the stripped string or None."""
    try:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return (proc.stdout or "").strip() or None


def gh_my_login():
    return _gh_scalar(["api", "user", "--jq", ".login"])


def gh_last_reviewed_commit(number, login):
    """The head commit of my most recent review on the PR (the pr-review-loop idempotency check)."""
    if not login:
        return None
    return _gh_scalar(["api", f"repos/{{owner}}/{{repo}}/pulls/{number}/reviews", "--paginate",
                       "--jq", f'[.[] | select(.user.login=="{login}")] | last | .commit_id'])


# ---------------------------------------------------------------- liveness

def transcript_age(agent_id):
    """Seconds since the subagent's transcript was last written, or None if no transcript exists.

    The harness writes `agent-<id>.jsonl` as the subagent works (across any session of this project),
    so a fresh mtime means it is actively working and a stale one means it has stopped. Unlike a
    self-touched heartbeat, this cannot be orphaned.
    """
    if not agent_id:
        return None
    paths = glob.glob(os.path.expanduser(_TRANSCRIPT_GLOB.format(id=agent_id)))
    if not paths:
        return None
    return time.time() - max(os.stat(p).st_mtime for p in paths)


def _alive(agent_id, spawned_at):
    if agent_id is None:
        return False
    if time.time() - (spawned_at or 0) < GRACE_SECONDS:
        return True  # just spawned — transcript may not exist yet
    age = transcript_age(agent_id)
    return age is not None and age < AGENT_STALE_SECONDS


def agent_running(cw):
    """Is the developer worker alive? (post-spawn grace, or a fresh transcript mtime)"""
    return _alive(cw.get("agent"), cw.get("spawned_at"))


def reviewer_running(cw):
    """Is a reviewer worker alive for this PR? (post-spawn grace, or a fresh transcript mtime)"""
    return _alive(cw.get("reviewer_agent"), cw.get("reviewer_spawned_at"))


def compute_review(cw, rec, login):
    """Decide the reviewer directive for the in-flight issue's PR.

    Returns (review, stop_reviewer): `review` is {"spawn", "pr", "head", "issue"} when a reviewer
    should be (re)dispatched, else None; `stop_reviewer` is an agent id to TaskStop (a stale reviewer
    on an old head, or a lingering reviewer whose head is now reviewed), else None.
    """
    pr = cw.get("pr") or rec.get("pr")
    if not pr:
        return None, None  # developer still building — no PR to review yet
    head = gh_pr_open_head(pr)
    if not head:
        return None, None  # PR not open, or gh failed — decide nothing this pass
    needs_review = gh_last_reviewed_commit(pr, login) != head
    alive = reviewer_running(cw)
    rev_head = cw.get("reviewer_head")
    if needs_review:
        if alive and rev_head == head:
            return None, None  # a reviewer is already on this exact head — let it finish
        stop = cw.get("reviewer_agent") if alive else None  # stale reviewer on an old head
        return {"spawn": True, "pr": pr, "head": head, "issue": cw["issue"]}, stop
    # head already reviewed -> no reviewer needed; reap a lingering one
    return None, (cw.get("reviewer_agent") if alive else None)


# ---------------------------------------------------------------- scope helpers

def priority_rank(issue):
    for label in issue.get("labels", []) or []:
        name = label.get("name", "") if isinstance(label, dict) else str(label)
        m = re.match(r"priority:(\d+)", name.strip(), re.I)
        if m:
            return int(m.group(1))
    return 99  # unlabeled sorts after any priority


def has_label(issue, label):
    if not label:
        return True
    names = [(l.get("name") if isinstance(l, dict) else str(l)) for l in (issue.get("labels") or [])]
    return label in names


def blockers(body):
    s = body or ""
    return {int(n) for n in _DEP_RE.findall(s)} | {int(n) for n in _TASK_RE.findall(s)}


def pr_closing(number, prs):
    pat = re.compile(rf"(?i)\bcloses?\s+#{number}\b")
    for pr in prs:
        if pat.search(pr.get("body") or ""):
            return pr
    return None


def parse_scope_args(argv):
    """Extract an ordered explicit scope list and a --label filter; ignore loop flags."""
    scope, label = [], None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--label" and i + 1 < len(argv):
            label = argv[i + 1]; i += 2; continue
        if tok == "--every" and i + 1 < len(argv):
            i += 2; continue  # interval is the skill's concern, not the decision's
        if tok == "--once":
            i += 1; continue
        for part in tok.replace(",", " ").split():
            if part.isdigit():
                scope.append(int(part))
        i += 1
    return scope, label


TERMINAL = {"merged", "closed", "error"}


# ---------------------------------------------------------------- the `next` decision

def cmd_next(argv):
    state = load_state()
    explicit, label = parse_scope_args(argv)

    issues = gh_json(["issue", "list", "--state", "open", "--json",
                      "number,title,labels,body", "--limit", "500"])
    prs = gh_json(["pr", "list", "--state", "open", "--json",
                   "number,headRefName,body", "--limit", "500"]) or []
    if issues is None:
        # GitHub unreachable — do not guess; hold this pass.
        return emit({"action": "wait", "reason": "GitHub unreachable (gh failed) — holding",
                     "report": ["pass held — could not reach GitHub this pass"]})
    open_by_num = {i["number"]: i for i in issues}

    # ---- initialize scope on the first pass (then it is fixed) ----
    if "scope" not in state:
        if explicit:
            scope = explicit
        else:
            cand = [i["number"] for i in issues if has_label(i, label)]
            cand.sort(key=lambda n: (priority_rank(open_by_num[n]), n))
            scope = cand
        state["scope"] = scope
        state["issues"] = {str(n): {"status": "queued", "pr": None, "branch": None} for n in scope}
        state.setdefault("current_work", None)

    scope = state["scope"]
    recs = state["issues"]

    # ---- reconcile every scoped issue with GitHub ----
    for n in scope:
        rec = recs.setdefault(str(n), {"status": "queued", "pr": None, "branch": None})
        pr = pr_closing(n, prs)
        if pr:
            rec["pr"] = pr["number"]
            rec["branch"] = pr["headRefName"]
            if rec["status"] in ("queued", "building"):
                rec["status"] = "in-review"
        if n not in open_by_num and rec["status"] != "error":
            rec["status"] = "merged" if rec.get("pr") else "closed"

    cw = state.get("current_work")
    stop_agent = None     # a finished developer (issue closed) still running — orchestrator stops it
    stop_reviewer = None  # a stale/lingering reviewer to TaskStop
    review = None         # a {"spawn", "pr", "head", "issue"} reviewer directive

    # ---- branch 1: a worker owns an issue ----
    if cw:
        n = cw["issue"]
        rec = recs[str(n)]
        closed = gh_issue_closed(n)
        if closed is None:
            closed = n not in open_by_num  # fall back to the open-list snapshot
        if closed:
            # The issue is closed (PR merged) -> the work is DONE, regardless of the workers. This
            # wins over the agent-alive check: a developer that finished but is stuck (never returns
            # its terminal reply) must not stall the loop. Hand back any still-alive worker id so the
            # orchestrator stops the zombie(s) before moving on.
            rec["status"] = "merged" if rec.get("pr") else "closed"
            if agent_running(cw):
                stop_agent = cw.get("agent")
            if reviewer_running(cw):
                stop_reviewer = cw.get("reviewer_agent")
            state["current_work"] = None  # fall through to dispatch the next issue
            cw = None
        else:
            # Issue still open: decide the reviewer track (independent of the developer track), then
            # the developer track. Both directives ride on the one returned action.
            review, stop_reviewer = compute_review(cw, rec, gh_my_login())
            if stop_reviewer and not (review and review.get("spawn")):
                cw["reviewer_agent"] = cw["reviewer_spawned_at"] = cw["reviewer_head"] = None
            if agent_running(cw):
                age = transcript_age(cw.get("agent"))
                hb = f"transcript {int(age)}s ago" if age is not None else "within grace"
                save_state(state)
                return emit({"action": "wait", "issue": n, "agent": cw["agent"], "pr": rec.get("pr"),
                             "reason": f"worker alive ({hb})", "review": review,
                             "stop_reviewer": stop_reviewer, "report": report_lines(state, n)})
            if cw.get("restarts", 0) >= MAX_RESTARTS:
                rec["status"] = "error"
                if reviewer_running(cw):
                    stop_reviewer = cw.get("reviewer_agent")  # dev gave up — orphaned reviewer
                state["current_work"] = None
                save_state(state)
                return emit({"action": "error", "issue": n, "stop_reviewer": stop_reviewer,
                             "reason": f"exceeded restart cap ({MAX_RESTARTS}) — surfacing",
                             "report": report_lines(state, n)})
            # developer not running and the issue is still open -> it died; resume it (and still
            # review the open PR if its head needs it)
            save_state(state)
            return emit({"action": "resume", "issue": n,
                         "title": (open_by_num.get(n) or {}).get("title", ""),
                         "branch": rec.get("branch") or cw.get("branch"),
                         "pr": rec.get("pr"), "agent": cw["agent"],
                         "use_template": "catchup-prompt.md",
                         "reason": "worker not running, issue still open — died; continue it",
                         "review": review, "stop_reviewer": stop_reviewer,
                         "report": report_lines(state, n)})

    # ---- branch 2: nothing in flight -> pick the next eligible issue ----
    waiting = []
    for n in scope:
        rec = recs[str(n)]
        if rec["status"] in TERMINAL or rec["status"] == "in-review":
            continue
        if n not in open_by_num:
            continue  # closed already; reconcile will have marked it terminal
        blk = sorted(b for b in blockers((open_by_num[n].get("body"))) if b in open_by_num)
        if blk:
            rec["status"] = "queued"
            waiting.append((n, blk))
            continue
        # eligible
        save_state(state)
        return emit({"action": "dispatch", "issue": n,
                     "title": open_by_num[n].get("title", ""),
                     "use_template": "dispatch-prompt.md", "reason": "next eligible issue",
                     "stop_agent": stop_agent, "stop_reviewer": stop_reviewer,
                     "report": report_lines(state, n, dispatching=n)})

    save_state(state)
    if all(recs[str(n)]["status"] in TERMINAL for n in scope):
        return emit({"action": "done", "reason": "every scoped issue is terminal",
                     "stop_agent": stop_agent, "stop_reviewer": stop_reviewer,
                     "report": report_lines(state)})
    reason = ("waiting on " + ", ".join(f"#{n}→{blk}" for n, blk in waiting)) if waiting \
        else "no eligible issue this pass"
    return emit({"action": "wait", "reason": reason, "stop_agent": stop_agent,
                 "stop_reviewer": stop_reviewer, "report": report_lines(state)})


# ---------------------------------------------------------------- record subcommands

def cmd_dispatched(args):
    state = load_state()
    rec = state["issues"][str(args.issue)]
    state["current_work"] = {"issue": args.issue, "agent": args.agent, "spawned_at": time.time(),
                             "branch": rec.get("branch"), "pr": rec.get("pr"), "restarts": 0,
                             "reviewer_agent": None, "reviewer_spawned_at": None, "reviewer_head": None}
    rec["status"] = "in-review" if rec.get("pr") else "building"
    rec["worker"] = args.agent
    save_state(state)
    emit({"ok": True, "current_work": state["current_work"]})


def cmd_resumed(args):
    state = load_state()
    cw = state.get("current_work")
    if not cw:
        emit({"ok": False, "reason": "no current_work to resume"}); return
    cw["agent"] = args.agent
    cw["spawned_at"] = time.time()
    cw["restarts"] = cw.get("restarts", 0) + 1
    state["issues"][str(cw["issue"])]["worker"] = args.agent
    save_state(state)
    emit({"ok": True, "current_work": cw})


def cmd_review_dispatched(args):
    """Record a reviewer the orchestrator just spawned for the current PR head."""
    state = load_state()
    cw = state.get("current_work")
    if not cw:
        emit({"ok": False, "reason": "no current_work for a reviewer"}); return
    cw["reviewer_agent"] = args.agent
    cw["reviewer_spawned_at"] = time.time()
    cw["reviewer_head"] = args.head
    save_state(state)
    emit({"ok": True, "current_work": cw})


# ---------------------------------------------------------------- reporting

def report_lines(state, active=None, dispatching=None):
    scope = state.get("scope", [])
    recs = state.get("issues", {})
    counts = {}
    for n in scope:
        counts[recs[str(n)]["status"]] = counts.get(recs[str(n)]["status"], 0) + 1
    header = f"scope {len(scope)}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    lines = [header]
    for n in scope:
        rec = recs[str(n)]
        tag = rec["status"]
        pr = f"PR #{rec['pr']}" if rec.get("pr") else ""
        note = ""
        if n == dispatching:
            note = "(dispatching…)"
        elif n == active:
            note = "(active)"
        lines.append(f"#{n} {tag} {pr} {note}".rstrip())
    return lines


def emit(obj):
    print(json.dumps(obj))


# ---------------------------------------------------------------- entry

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next", add_help=False)
    d = sub.add_parser("dispatched"); d.add_argument("--issue", type=int, required=True); d.add_argument("--agent", required=True)
    r = sub.add_parser("resumed"); r.add_argument("--agent", required=True)
    rd = sub.add_parser("review-dispatched"); rd.add_argument("--agent", required=True); rd.add_argument("--head", required=True)

    if len(sys.argv) >= 2 and sys.argv[1] == "next":
        cmd_next(sys.argv[2:])
        return
    args = parser.parse_args()
    if args.cmd == "dispatched":
        cmd_dispatched(args)
    elif args.cmd == "resumed":
        cmd_resumed(args)
    elif args.cmd == "review-dispatched":
        cmd_review_dispatched(args)


if __name__ == "__main__":
    main()
