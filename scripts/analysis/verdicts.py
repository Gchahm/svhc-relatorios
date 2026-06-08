"""Loop bookkeeping for the self-improving classification loop (feature 007).

This module is the **only** writer of ``data/scrape/<period>.verdicts.json`` — the
per-period working file holding review verdicts and the deterministic loop state.
It does no model calls and no network IO: pure file IO + arithmetic, so the loop's
working set is reproducible (SC-003) and termination is provable (SC-005).

Contracts:
- ``specs/007-classification-improve-loop/contracts/verdict-cli.md`` (record-verdict / loop-state)
- ``specs/007-classification-improve-loop/contracts/verdicts-file.schema.md`` (file shape)
- ``specs/007-classification-improve-loop/data-model.md`` (Verdict / LoopState / mismatch identity)

The vision/judgment lives in the ``review-mismatch`` agent; the codegen in the
``fix-mismatch`` worker; the coordination in the ``improve-classification`` skill.
This module just records what they decide and computes when to stop.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .extractions import summarize_mismatches

logger = logging.getLogger(__name__)

VERDICTS_SUFFIX = ".verdicts.json"

VERDICT_VALUES = {"true", "false", "transient", "page-error"}
ROOT_CAUSE_AREAS = {"reading", "rollup-precedence", "grouping", "reconciliation-tolerance", "other"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
FIX_STATUSES = {"pr-open", "failed"}  # never "merged" — merging is a human action (FR-008/SC-005)

DEFAULT_MAX_ITERATIONS = 3
DEFAULT_NO_PROGRESS_WINDOW = 2


def verdicts_path(data_dir: str, period: str) -> Path:
    """Path of the per-period verdicts/loop-state working file."""
    return Path(data_dir) / f"{period}{VERDICTS_SUFFIX}"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- #
# Mismatch identity (data-model Decision 4)
# --------------------------------------------------------------------------- #


def mismatch_key(mismatch: dict) -> str:
    """Stable identity for a mismatch — the loop's join key.

    Uses only the *stable* fields, excluding volatile extracted values, so a
    re-read that changes the extracted value does not look like a new mismatch
    (otherwise the loop would never converge).

    - per-document kinds: ``period|kind|document_id|entry_id``
    - ``duplicate_billing``: ``period|kind|sorted(document_ids)``
    """
    period = mismatch.get("period", "")
    kind = mismatch.get("kind", "")
    if kind == "duplicate_billing":
        docids = ",".join(sorted(str(d) for d in (mismatch.get("document_ids") or [])))
        return f"{period}|{kind}|{docids}"
    document_id = mismatch.get("document_id")
    entry_id = mismatch.get("entry_id")
    return f"{period}|{kind}|{document_id}|{entry_id}"


def _document_ids_of(mismatch: dict) -> list[str]:
    """Documents implicated by a mismatch (for affected-doc rescoping)."""
    if mismatch.get("kind") == "duplicate_billing":
        return [str(d) for d in (mismatch.get("document_ids") or [])]
    did = mismatch.get("document_id")
    return [str(did)] if did else []


# --------------------------------------------------------------------------- #
# Verdicts file: load / validate / upsert
# --------------------------------------------------------------------------- #


def load_verdicts_file(data_dir: str, period: str) -> dict:
    """Load the verdicts file, or a fresh structure when absent."""
    path = verdicts_path(data_dir, period)
    if not path.exists():
        return {"period": period, "verdicts": [], "loop_state": None}
    data = _read_json(path)
    data.setdefault("period", period)
    data.setdefault("verdicts", [])
    data.setdefault("loop_state", None)
    return data


def save_verdicts_file(data_dir: str, period: str, data: dict) -> None:
    _write_json(verdicts_path(data_dir, period), data)


def validate_verdict(rec: dict) -> None:
    """Raise ``ValueError`` if a verdict record is malformed.

    ``root_cause`` (with a valid ``area`` and a non-empty ``hypothesis``) is
    required iff ``verdict == "false"``.
    """
    if not rec.get("mismatch_key"):
        raise ValueError("verdict missing 'mismatch_key'")
    verdict = rec.get("verdict")
    if verdict not in VERDICT_VALUES:
        raise ValueError(f"invalid verdict {verdict!r}; expected one of {sorted(VERDICT_VALUES)}")
    confidence = rec.get("confidence")
    if confidence is not None and confidence not in CONFIDENCE_VALUES:
        raise ValueError(f"invalid confidence {confidence!r}; expected one of {sorted(CONFIDENCE_VALUES)}")
    rc = rec.get("root_cause")
    if verdict == "false":
        if not isinstance(rc, dict):
            raise ValueError("verdict 'false' requires a root_cause object")
        if rc.get("area") not in ROOT_CAUSE_AREAS:
            raise ValueError(f"root_cause.area must be one of {sorted(ROOT_CAUSE_AREAS)}")
        if not (rc.get("hypothesis") or "").strip():
            raise ValueError("root_cause.hypothesis must be a non-empty string")
    elif rc is not None:
        raise ValueError("root_cause is only allowed when verdict == 'false'")


def validate_fix(fix: dict) -> None:
    """Raise ``ValueError`` if a FixProposal reference is malformed (never 'merged')."""
    status = fix.get("status")
    if status not in FIX_STATUSES:
        raise ValueError(f"invalid fix status {status!r}; expected one of {sorted(FIX_STATUSES)} (never 'merged')")


def upsert_verdict(data: dict, rec: dict, iteration: int) -> dict:
    """Insert/replace a verdict record. Idempotent within an iteration.

    Latest-wins per ``mismatch_key`` (latest = highest iteration); records from
    prior iterations are retained so the no-progress guard can see verdict flips.
    Replacing the same ``(mismatch_key, iteration)`` is a no-op-equivalent overwrite.
    """
    rec = dict(rec)
    rec["iteration"] = iteration
    rec.setdefault("reviewed_at", _now_iso())
    key = rec["mismatch_key"]
    data["verdicts"] = [
        v for v in data.get("verdicts", []) if not (v.get("mismatch_key") == key and v.get("iteration") == iteration)
    ]
    data["verdicts"].append(rec)
    return rec


def _latest_verdicts(data: dict) -> dict[str, dict]:
    """Map mismatch_key -> the record with the highest iteration."""
    latest: dict[str, dict] = {}
    for v in data.get("verdicts", []):
        key = v.get("mismatch_key")
        if key is None:
            continue
        cur = latest.get(key)
        if cur is None or v.get("iteration", 0) >= cur.get("iteration", 0):
            latest[key] = v
    return latest


def _verdict_history_by_key(data: dict) -> dict[str, set]:
    """Map mismatch_key -> set of distinct verdict values seen across iterations."""
    out: dict[str, set] = {}
    for v in data.get("verdicts", []):
        key = v.get("mismatch_key")
        if key is None or "verdict" not in v:
            continue
        out.setdefault(key, set()).add(v["verdict"])
    return out


def record_verdict(
    data_dir: str,
    period: str,
    iteration: int,
    verdict_obj: dict,
    *,
    fix: dict | None = None,
) -> dict:
    """Upsert one verdict (and optionally attach a fix reference) into the file.

    ``verdict_obj`` is the object the ``review-mismatch`` agent returns. If it
    carries a ``verdict`` it is validated and upserted; ``fix`` (a FixProposal
    reference) is attached to the matching record for this iteration.
    """
    if not verdict_obj.get("mismatch_key"):
        raise ValueError("record-verdict requires 'mismatch_key' in --json")
    data = load_verdicts_file(data_dir, period)

    if "verdict" in verdict_obj:
        validate_verdict(verdict_obj)
        upsert_verdict(data, verdict_obj, iteration)

    if fix is not None:
        validate_fix(fix)
        key = verdict_obj["mismatch_key"]
        target = next(
            (v for v in data["verdicts"] if v.get("mismatch_key") == key and v.get("iteration") == iteration),
            None,
        )
        if target is None:
            # No verdict yet for this iteration: attach to the latest record for the key.
            target = _latest_verdicts(data).get(key)
        if target is None:
            raise ValueError(f"cannot attach fix: no verdict recorded for {key!r}")
        target["fix"] = fix

    save_verdicts_file(data_dir, period, data)
    return data


# --------------------------------------------------------------------------- #
# Loop state (data-model LoopState; deterministic termination — Decision 7)
# --------------------------------------------------------------------------- #


def _upsert_history(history: list[dict], record: dict) -> list[dict]:
    """Replace the entry for ``record['iteration']`` (idempotent) and keep sorted."""
    it = record["iteration"]
    out = [h for h in history if h.get("iteration") != it]
    out.append(record)
    out.sort(key=lambda h: h.get("iteration", 0))
    return out


def loop_state(
    data_dir: str,
    period: str,
    *,
    iteration: int | None = None,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    no_progress_window: int = DEFAULT_NO_PROGRESS_WINDOW,
    document_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
) -> dict:
    """Recompute, persist, and return the deterministic loop state for a period.

    Joins the current ``mismatches`` summary with stored verdicts to compute the
    open set, findings, data-quality items, the documents to re-scope next
    iteration, the per-iteration history, and a ``terminate`` signal.
    Byte-stable for identical inputs.
    """
    data = load_verdicts_file(data_dir, period)
    latest = _latest_verdicts(data)

    mismatches = summarize_mismatches(
        data_dir, [period], document_ids=document_ids, entry_ids=entry_ids
    )

    open_keys: list[str] = []
    findings: list[str] = []
    data_quality: list[str] = []
    # Documents to re-scope next iteration = those behind STILL-OPEN mismatches only, so a
    # converged document drops out of scope (SC-006). Transient verdicts keep their mismatch
    # open, so their documents are naturally included.
    affected: set[str] = set()
    false_count = 0
    fixes: list[dict] = []

    # Stable order: iterate mismatches as returned (deterministic), dedupe keys.
    seen: set[str] = set()
    for m in mismatches:
        key = mismatch_key(m)
        if key in seen:
            continue
        seen.add(key)
        v = latest.get(key)
        verdict = v.get("verdict") if v else None
        if verdict == "true":
            findings.append(key)
        elif verdict == "page-error":
            data_quality.append(key)
        else:  # None (unreviewed), "false", or "transient" -> still open
            open_keys.append(key)
            affected.update(_document_ids_of(m))
            if verdict == "false":
                false_count += 1
        if v and isinstance(v.get("fix"), dict):
            fix = v["fix"]
            fixes.append(
                {"mismatch_key": key, "pr_url": fix.get("pr_url"), "status": fix.get("status")}
            )

    # Resolve the current iteration.
    history = list(data.get("loop_state", {}).get("history", []) if data.get("loop_state") else [])
    if iteration is None:
        iteration = (max((h.get("iteration", 0) for h in history), default=0) or 0) + 1

    iter_record = {
        "iteration": iteration,
        "open_count": len(open_keys),
        "open_keys": sorted(open_keys),
        "false_count": false_count,
        "fixes": fixes,
    }
    history = _upsert_history(history, iter_record)

    # --- Termination (deterministic): converged > no-progress > max-iterations ---
    terminate = None
    if not open_keys:
        terminate = {
            "reason": "converged",
            "detail": "No open false/transient/unreviewed mismatches remain; only findings/data-quality.",
        }
    else:
        # No-progress: a verdict flip on any key, or a stagnant open set across the window.
        flips = [k for k, vals in _verdict_history_by_key(data).items() if len(vals) > 1]
        window = [h for h in history if h["iteration"] <= iteration][-no_progress_window:]
        stagnant = (
            len(window) >= no_progress_window
            and len(open_keys) > 0
            and len(open_keys) >= window[0]["open_count"]
        )
        if flips:
            terminate = {
                "reason": "no-progress",
                "detail": f"Verdict flipped across iterations for: {', '.join(sorted(flips))}.",
            }
        elif stagnant:
            terminate = {
                "reason": "no-progress",
                "detail": (
                    f"Open mismatch set did not shrink over {no_progress_window} iterations "
                    f"(open_count={len(open_keys)})."
                ),
            }
        elif iteration >= max_iterations:
            terminate = {
                "reason": "max-iterations",
                "detail": f"Reached the iteration cap ({max_iterations}).",
            }

    state = {
        "period": period,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "no_progress_window": no_progress_window,
        "open": sorted(open_keys),
        "findings": sorted(findings),
        "data_quality": sorted(data_quality),
        "affected_document_ids": sorted(affected),
        "history": history,
        "terminate": terminate,
    }
    data["loop_state"] = state
    save_verdicts_file(data_dir, period, data)
    return state
