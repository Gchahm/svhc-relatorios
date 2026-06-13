#!/usr/bin/env python3
"""Deterministic decision engine for the implement-loop skill.

The loop orchestrator (a cheap model) calls this once per pass to learn the ONE action to take, so
the decision logic — scope/dependency ordering, worker liveness, completion detection — lives in
code, not in the model's head. All state lives in `.cache/implement-loop/state.json`; THIS SCRIPT IS
ITS ONLY WRITER. GitHub is the source of truth for issue/PR state and is read **read-only** here
(never review state — that is the worker's business, and the issue-orchestrator Bash guard forbids
it).

Subcommands
-----------
  next [scope-args...]            Reconcile with GitHub + decide. Prints one JSON object:
                                  {"action": <action>, "report": [<line>, ...], ...fields}.
  dispatched --issue N --agent ID Record a freshly spawned worker as current_work.
  resumed --agent ID              Record a resumed/respawned worker (resets the liveness clock,
                                  increments the restart counter).

Actions returned by `next`
--------------------------
  dispatch  Spawn a new `developer` worker for {issue,title} (use templates/dispatch-prompt.md).
  resume    The current worker is not running but its issue is still open — it died; continue it
            (use templates/catchup-prompt.md), in place via SendMessage or via a fresh spawn.
  wait      A worker is alive, OR the next issue is dependency-blocked — do nothing this pass.
  done      Every scoped issue is terminal — disarm the loop (CronDelete).
  error     The current issue exceeded the restart cap — surface it; current_work is cleared so the
            next pass moves on.

Any action may also carry a "stop_agent": <id> field: a worker whose issue is now closed (work
done) but that still looks alive — i.e. it finished the merge but is stuck and never returned its
terminal reply. The orchestrator must STOP that worker before acting (TaskStop with this id — a
background developer spawn is a `local_agent` task whose task_id IS its agent id), so a zombie can't
linger.

The decision tree (matches the skill's Workflow):
  current_work?
    no  -> pick next eligible issue (dependency gate + scope order) -> dispatch | wait | done
    yes -> issue closed (PR merged)? -> clear current_work; if the worker still looks alive, return
                                        its id as stop_agent; then dispatch the next | done | wait.
                                        (Closed WINS over agent-alive: a stuck worker never stalls
                                        the loop.)
           else agent running?       -> wait
           else (died, issue open)   -> resume   (or error past the restart cap)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

STATE_REL = ".cache/implement-loop/state.json"
HEARTBEAT_DIR_REL = ".cache/implement-loop"
# Per-ISSUE heartbeat (`heartbeat-<issue>`), NOT one shared file: a worker that finished but is
# still alive/stuck must not keep the *next* issue's worker looking alive.

GRACE_SECONDS = 180          # right after a spawn the worker is still arming — treat as alive
HEARTBEAT_STALE_SECONDS = 300  # worker touches the heartbeat ~every 60s; 5 missed ticks = dead
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


# ---------------------------------------------------------------- liveness

def heartbeat_age(issue):
    try:
        path = os.path.join(project_dir(), HEARTBEAT_DIR_REL, f"heartbeat-{issue}")
        return time.time() - os.stat(path).st_mtime
    except OSError:
        return None


def agent_running(cw):
    """Is the current worker alive? Within the post-spawn grace window, or a fresh per-issue heartbeat."""
    if time.time() - (cw.get("spawned_at") or 0) < GRACE_SECONDS:
        return True
    age = heartbeat_age(cw.get("issue"))
    return age is not None and age < HEARTBEAT_STALE_SECONDS


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
            if rec["status"] == "queued":
                rec["status"] = "in-review"
        if n not in open_by_num and rec["status"] != "error":
            rec["status"] = "merged" if rec.get("pr") else "closed"

    cw = state.get("current_work")
    stop_agent = None  # a finished worker (issue closed) still running — orchestrator must stop it

    # ---- branch 1: a worker owns an issue ----
    if cw:
        n = cw["issue"]
        rec = recs[str(n)]
        closed = gh_issue_closed(n)
        if closed is None:
            closed = n not in open_by_num  # fall back to the open-list snapshot
        if closed:
            # The issue is closed (PR merged) -> the work is DONE, regardless of the worker. This
            # wins over the agent-alive check: a worker that finished but is stuck (never returns
            # its terminal reply) must not stall the loop. If it still looks alive, hand its id back
            # as stop_agent so the orchestrator stops the zombie before moving on.
            rec["status"] = "merged" if rec.get("pr") else "closed"
            if agent_running(cw):
                stop_agent = cw.get("agent")
            state["current_work"] = None  # fall through to dispatch the next issue
            cw = None
        elif agent_running(cw):
            age = heartbeat_age(n)
            hb = f"heartbeat {int(age)}s" if age is not None else "within grace"
            save_state(state)
            return emit({"action": "wait", "issue": n, "agent": cw["agent"], "pr": rec.get("pr"),
                         "reason": f"worker alive ({hb})", "report": report_lines(state, n)})
        else:
            # worker is not running and the issue is still open -> it died
            if cw.get("restarts", 0) >= MAX_RESTARTS:
                rec["status"] = "error"
                state["current_work"] = None
                save_state(state)
                return emit({"action": "error", "issue": n,
                             "reason": f"exceeded restart cap ({MAX_RESTARTS}) — surfacing",
                             "report": report_lines(state, n)})
            save_state(state)
            return emit({"action": "resume", "issue": n,
                         "title": (open_by_num.get(n) or {}).get("title", ""),
                         "branch": rec.get("branch") or cw.get("branch"),
                         "pr": rec.get("pr"), "agent": cw["agent"],
                         "use_template": "catchup-prompt.md",
                         "reason": "worker not running, issue still open — died; continue it",
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
                     "stop_agent": stop_agent,
                     "report": report_lines(state, n, dispatching=n)})

    save_state(state)
    if all(recs[str(n)]["status"] in TERMINAL for n in scope):
        return emit({"action": "done", "reason": "every scoped issue is terminal",
                     "stop_agent": stop_agent, "report": report_lines(state)})
    reason = ("waiting on " + ", ".join(f"#{n}→{blk}" for n, blk in waiting)) if waiting \
        else "no eligible issue this pass"
    return emit({"action": "wait", "reason": reason, "stop_agent": stop_agent,
                 "report": report_lines(state)})


# ---------------------------------------------------------------- record subcommands

def cmd_dispatched(args):
    state = load_state()
    rec = state["issues"][str(args.issue)]
    state["current_work"] = {"issue": args.issue, "agent": args.agent, "spawned_at": time.time(),
                             "branch": rec.get("branch"), "pr": rec.get("pr"), "restarts": 0}
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

    if len(sys.argv) >= 2 and sys.argv[1] == "next":
        cmd_next(sys.argv[2:])
        return
    args = parser.parse_args()
    if args.cmd == "dispatched":
        cmd_dispatched(args)
    elif args.cmd == "resumed":
        cmd_resumed(args)


if __name__ == "__main__":
    main()
