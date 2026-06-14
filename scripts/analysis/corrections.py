"""Data-correction audit trail + reversibility (feature 054 / TRIAGE-003).

The autonomous false-positive triage agent (design `docs/features/false-positive-triage-agent.md`,
decision D3) corrects fiscal **data** with no human pre-approval gate. For a fraud-audit tool that
makes the audit trail + reversibility the *only* safety net — they are load-bearing, not optional
(design §4.4). This module is that safety net:

- a durable, queryable, analysis-owned store — the ``data_corrections`` D1 table (NOT the ephemeral
  ``<period>.verdicts.json`` cache, NOT ``alerts.notes``); one row per CHANGED FIELD of one
  apply-correction call, rows of a call correlated by ``batch_id``;
- ``apply_correction`` — record each field change ``{attachment_id, page, field, from, to, evidence,
  agent, timestamp}``, apply it via the existing staging path, then **verify-after** (the targeted
  finding cleared AND no new finding appeared for the affected scope, else roll back / flag);
- ``list_corrections`` / ``undo_correction`` — human review + reversal of any *applied* correction.

The correction *primitive* is the existing one (decision D2 / design §4.5): write the verified per-
page extraction via the ``record_classification`` staging gate, then propagate via the feature-050
**staging-driven** ``apply_extractions`` (so only the corrected attachment's NF group is rolled up,
non-destructively). This module wraps that primitive with the snapshot/verify/restore machinery; it
invents no new extraction path.

Restore (rollback + undo) is a *deterministic re-derive*: ``attachment_analyses`` is a pure roll-up
of the ``page_classifications`` staging rows, so restoring the pre-correction staging snapshot and
re-propagating reproduces the prior analysis byte-for-byte. The snapshot lives in the correction
record (``from_staging``), so the store is self-contained for reversal.

Stdlib only (analysis-package invariant): D1 via ``common.d1``; ids via ``common.det_id``.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys

from common import d1, det_id, now_ms
from common.d1 import Target

from .extractions import DEFAULT_CACHE_DIR, apply_extractions, summarize_mismatches
from .page_classifications import (
    clear_classified_stamp,
    load_stored_records,
    record_classification,
    staging_rows_from_records,
    validate_page_fields,
)
from .verdicts import mismatch_key

logger = logging.getLogger(__name__)

TABLE = "data_corrections"
STAGING_TABLE = "page_classifications"

STATUS_APPLIED = "applied"
STATUS_ROLLED_BACK = "rolled-back"
STATUS_FLAGGED = "flagged"
STATUS_REVERTED = "reverted"

CORRECTION_AGENT_DEFAULT = "triage-agent"
UNDO_ACTOR_DEFAULT = "human"


# --------------------------------------------------------------------------- #
# Pure helpers (id builders, diff, verify-after, status guard) — unit-tested
# --------------------------------------------------------------------------- #


def _canonical(corrected_pages: dict) -> str:
    """Deterministic JSON of the corrected-pages mapping (sorted keys) — for id minting."""
    return json.dumps(corrected_pages, ensure_ascii=False, sort_keys=True)


def batch_id(attachment_id: str, target_finding_key: str, corrected_pages: dict) -> str:
    """Stable id correlating the field-rows of one apply-correction call (idempotent — FR-012)."""
    return det_id("data_correction_batch", attachment_id, target_finding_key or "", _canonical(corrected_pages))


def correction_id(batch: str, page_label: str, field: str) -> str:
    """Stable per-field row id (idempotent: re-applying the same correction overwrites the row)."""
    return det_id("data_correction", batch, page_label, field)


def field_diff(current_fields: dict | None, corrected_fields: dict) -> list[dict]:
    """Per-field ``{field, from, to}`` for every field whose value changed.

    Compares the page's CURRENT recorded extraction (``current_fields``; ``None`` when the page had
    no prior staging row — every corrected field is then a change from null) against the corrected
    extraction. Unchanged fields are skipped. An empty result ⇒ no-op (FR-009). Values are compared
    by equality on the parsed JSON values (so ``320`` ≠ ``800``, ``"x"`` ≠ ``"y"``, ``None`` is a
    distinct value). Deterministic field order (sorted) for stable ids/output.
    """
    cur = current_fields or {}
    out: list[dict] = []
    for field in sorted(corrected_fields):
        new = corrected_fields[field]
        old = cur.get(field)
        if old != new:
            out.append({"field": field, "from": old, "to": new})
    return out


def verify_after(before_keys: set[str], after_keys: set[str], target_finding_key: str) -> tuple[bool, str]:
    """The verify-after rule (FR-004 / FR-010).

    Fail-closed: if the targeted finding is not in the BEFORE set, the correction is *unverifiable*
    ("did it clear?" is unanswerable) → ``(False, "unverifiable: …")``; the caller MUST NOT apply.

    Otherwise PASS iff BOTH:
      (a) the targeted finding cleared — ``target_finding_key`` not in ``after_keys``; AND
      (b) no new finding appeared for the scope — ``after_keys - before_keys`` is empty.
    Returns ``(ok, reason)``; ``reason`` describes the failure (empty on pass).
    """
    if target_finding_key not in before_keys:
        return False, f"unverifiable: target finding {target_finding_key!r} not present before the correction"
    if target_finding_key in after_keys:
        return False, f"target finding {target_finding_key!r} did not clear"
    new = sorted(after_keys - before_keys)
    if new:
        return False, f"new finding(s) appeared: {', '.join(new)}"
    return True, ""


def can_undo(status: str) -> bool:
    """Undo is allowed only for an ``applied`` correction (FR-008)."""
    return status == STATUS_APPLIED


def correction_row(
    *,
    row_id: str,
    batch: str,
    attachment_id: str,
    period: str | None,
    page_label: str,
    field: str,
    from_value,
    to_value,
    evidence: str | None,
    agent: str,
    target_finding_key: str | None,
    status: str,
    detail: str | None,
    from_staging: list[dict] | None,
    created_at: int,
) -> dict:
    """Assemble one ``data_corrections`` row dict for upsert (JSON-encoding the value/snapshot cols)."""
    return {
        "id": row_id,
        "batch_id": batch,
        "attachment_id": attachment_id,
        "period": period,
        "page_label": page_label,
        "field": field,
        # JSON-encode so a number / string / null round-trips unambiguously on read.
        "from_value": json.dumps(from_value, ensure_ascii=False),
        "to_value": json.dumps(to_value, ensure_ascii=False),
        "evidence": evidence,
        "agent": agent,
        "target_finding_key": target_finding_key,
        "status": status,
        "detail": detail,
        # _escape_sql JSON-serializes a list/dict; store the raw snapshot list.
        "from_staging": from_staging if from_staging is not None else None,
        "created_at": created_at,
        "reverted_at": None,
        "reverted_by": None,
    }


# --------------------------------------------------------------------------- #
# D1 reads (scope, findings, snapshot) — thin, all via common.d1
# --------------------------------------------------------------------------- #


def _q(value: str) -> str:
    """Single-quote-escape a scalar for inline SQL."""
    return "'" + str(value).replace("'", "''") + "'"


def _attachment_context(attachment_id: str, target: Target) -> tuple[str | None, str | None]:
    """Return ``(period, content_hash)`` for an attachment, or ``(None, None)`` if unknown.

    Period comes from the attachment's entry's accountability report; content_hash is the shared-NF
    grouping key. Read-only against the mirror tables (never written here)."""
    rows = d1.query(
        "SELECT r.period AS period, a.content_hash AS content_hash "
        "FROM attachments a JOIN entries e ON a.entry_id = e.id "
        "JOIN accountability_reports r ON e.report_id = r.id "
        f"WHERE a.id = {_q(attachment_id)}",
        target=target,
    )
    if not rows:
        return None, None
    return rows[0].get("period"), rows[0].get("content_hash")


def _affected_scope(attachment_id: str, target: Target) -> list[str]:
    """The attachment + its shared-NF sibling attachment ids (the verify-after / propagation scope).

    Siblings share a non-NULL ``content_hash`` (the authoritative shared-NF key — feature 005/016).
    A NULL/absent hash means no siblings (the attachment is its own scope). Sorted, distinct."""
    _, content_hash = _attachment_context(attachment_id, target)
    if not content_hash:
        return [attachment_id]
    rows = d1.query(
        f"SELECT id FROM attachments WHERE content_hash = {_q(content_hash)}",
        target=target,
    )
    ids = {r["id"] for r in rows} | {attachment_id}
    return sorted(ids)


def _finding_keys(attachment_ids: list[str], target: Target, cache_dir: str) -> set[str]:
    """The set of stable finding keys (``mismatch_key``) over the given attachment scope.

    Reuses ``summarize_mismatches`` (the single-source finding detector) scoped by attachment id and
    ``verdicts.mismatch_key`` (the same identity the loop/agent use), so verify-after speaks exactly
    the agent's language and never reimplements detection."""
    if not attachment_ids:
        return set()
    rows = summarize_mismatches(target=target, cache_dir=cache_dir, attachment_ids=attachment_ids)
    return {mismatch_key(m) for m in rows}


def _snapshot_staging(attachment_id: str, target: Target) -> list[dict]:
    """The attachment's prior per-page extraction as ``page_classifications``-shaped rows.

    The restore input AND the diff base. Sourced from the persisted ``attachment_analysis_records``
    (joined via this attachment's ``attachment_analyses``), NOT the live staging table: feature 035
    PRUNES the staging rows once apply rolls them up, so a steady-state classified attachment has no
    staging rows — but its frozen per-page extraction lives durably in ``…_records.response`` (the
    exact object that was staged, written at roll-up time via ``D1ExtractionProvider``). Restoring
    those as staging and re-applying re-derives the prior ``attachment_analyses`` byte-for-byte
    (research D3). Each row is shaped to the staging contract (id keyed on ``(attachment_id,
    page_label)`` so the restore overwrites the right rows). Empty list ⇒ the page set carried no
    parseable extraction (its exact prior state).

    The D1 read + the pure record→staging transform live in ``page_classifications`` (the
    ``load_stored_records`` / ``staging_rows_from_records`` seam, feature 056) so this snapshot and the
    ``re-derive`` command share ONE implementation."""
    return staging_rows_from_records(attachment_id, load_stored_records(attachment_id, target))


def _current_page_fields(snapshot: list[dict], page_label: str) -> dict | None:
    """The current recorded fields object for one page in a staging snapshot (or None)."""
    for row in snapshot:
        if row.get("page_label") == page_label:
            resp = row.get("response")
            return resp if isinstance(resp, dict) else None
    return None


# --------------------------------------------------------------------------- #
# D1 writes (restore, status update) — atomic batches (feature 024 idiom)
# --------------------------------------------------------------------------- #


def _restore_staging(attachment_id: str, snapshot: list[dict], target: Target) -> bool:
    """Restore the attachment's staging rows to ``snapshot`` in ONE atomic batch.

    ``DELETE`` the attachment's current staging rows + ``INSERT OR REPLACE`` the snapshot rows
    (feature 024: one ``execute_sql``). An empty snapshot leaves the staging table cleared for the
    attachment (its exact prior state when it was unclassified). Returns True on success, False on
    a caught failure (so the caller can mark the correction ``flagged`` rather than silently OK)."""
    try:
        delete = f"DELETE FROM {STAGING_TABLE} WHERE attachment_id = {_q(attachment_id)};"
        insert = d1.upsert_sql({STAGING_TABLE: snapshot}) if snapshot else ""
        d1.execute_sql(delete + ("\n" + insert if insert else ""), target=target)
        return True
    except Exception:  # noqa: BLE001 — restore failure must downgrade to `flagged`, not raise
        logger.exception("Failed to restore staging snapshot for attachment %s", attachment_id)
        return False


def _propagate(attachment_id: str, period: str | None, target: Target, cache_dir: str) -> None:
    """Re-derive the analysis for the corrected attachment's NF group + refresh documents/alerts.

    Precondition: the corrected/restored ``page_classifications`` staging rows are ALREADY written.
    Clears the classified stamp (staging untouched — see ``clear_classified_stamp``) so the attachment
    enters the pending plan, then runs the feature-050 staging-driven ``apply_extractions`` (rolls up
    ONLY groups whose representative has staging rows — i.e. exactly this corrected group), then
    ``run_analysis`` (which itself rebuilds the global ``documents`` entity before writing alerts).
    Scoped to the attachment's period so unrelated periods are untouched.

    ``run_analysis``'s human-readable alert summary is printed to stdout via the reporter; redirect
    stdout to stderr for the duration so it does not corrupt the JSON result the apply/undo CLI
    prints to stdout (the ``analyze`` command keeps its stdout summary — this redirect is local).
    ``apply_extractions`` likewise prints a roll-up summary, so it is redirected too."""
    from . import run_analysis  # local import: run_analysis lives in the package __init__

    periods_filter = [period] if period else None
    clear_classified_stamp(attachment_id, target)
    with contextlib.redirect_stdout(sys.stderr):
        apply_extractions(target=target, periods_filter=periods_filter, cache_dir=cache_dir)
        run_analysis(target=target, periods_filter=periods_filter, cache_dir=cache_dir)


def _write_rows(rows: list[dict], target: Target) -> None:
    d1.upsert_tables({TABLE: rows}, target=target)


def _update_batch_status(
    batch: str, status: str, *, detail: str | None, reverted_at: int | None, reverted_by: str | None, target: Target
) -> None:
    """Set the status (+ optional reversal stamps) for every row of a batch in one statement."""
    sets = [f"status = {_q(status)}"]
    if detail is not None:
        sets.append(f"detail = {_q(detail)}")
    if reverted_at is not None:
        sets.append(f"reverted_at = {reverted_at}")
    if reverted_by is not None:
        sets.append(f"reverted_by = {_q(reverted_by)}")
    d1.execute_sql(f"UPDATE {TABLE} SET {', '.join(sets)} WHERE batch_id = {_q(batch)};", target=target)


# --------------------------------------------------------------------------- #
# Public operations
# --------------------------------------------------------------------------- #


def apply_correction(
    attachment_id: str,
    target_finding_key: str,
    corrected_pages: dict,
    *,
    evidence: str | None = None,
    agent: str = CORRECTION_AGENT_DEFAULT,
    target: Target = "local",
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> dict:
    """Record + apply one data correction to one attachment, gated by verify-after.

    ``corrected_pages`` maps ``{page_label: fields-object}`` (each validated against the frozen
    ``page_classifications`` contract). Flow (contract ``corrections-cli.md``):

    1. Resolve the affected scope (attachment + shared-NF siblings) + the attachment's period.
    2. BEFORE findings over that scope; fail-closed if ``target_finding_key`` is absent → result
       ``unverifiable``, NO data change (FR-010).
    3. Snapshot current staging + compute the per-field diff; empty diff ⇒ ``no-op``, NO row (FR-009).
    4. Apply: write corrected staging (validated) → propagate (mark-pending → staging-driven apply →
       analyze).
    5. AFTER findings; ``verify_after``. PASS → rows ``applied``. FAIL → restore snapshot; rows
       ``rolled-back`` (restore OK) or ``flagged`` (restore failed).

    Returns the contract result dict. Idempotent (FR-012): an identical replay re-mints the same ids
    and, since the corrected staging already equals the live staging, step 3 sees an empty diff (no-op).
    """
    if not corrected_pages:
        return {"result": "no-op", "batch_id": None, "attachment_id": attachment_id,
                "target_finding": target_finding_key, "corrections": [], "reason": "no corrected pages supplied"}
    for page_label, fields in corrected_pages.items():
        err = validate_page_fields(fields)
        if err is not None:
            raise ValueError(f"corrected page {page_label!r} rejected: {err}")

    period, _ = _attachment_context(attachment_id, target)
    scope = _affected_scope(attachment_id, target)
    batch = batch_id(attachment_id, target_finding_key, corrected_pages)

    # (2) Fail-closed verify precondition — BEFORE findings must contain the target (else unverifiable).
    before = _finding_keys(scope, target, cache_dir)
    if target_finding_key not in before:
        reason = f"unverifiable: target finding {target_finding_key!r} not present before the correction"
        logger.info("apply-correction %s: %s — no data change", attachment_id, reason)
        return {"result": "unverifiable", "batch_id": batch, "attachment_id": attachment_id,
                "target_finding": target_finding_key, "corrections": [], "reason": reason}

    # (3) Snapshot + per-field diff. The snapshot is the deterministic restore input.
    snapshot = _snapshot_staging(attachment_id, target)
    diffs: list[tuple[str, dict]] = []  # (page_label, {field,from,to})
    for page_label, fields in corrected_pages.items():
        current = _current_page_fields(snapshot, page_label)
        for d in field_diff(current, fields):
            diffs.append((page_label, d))
    if not diffs:
        logger.info("apply-correction %s: corrected values equal current — nothing to correct", attachment_id)
        return {"result": "no-op", "batch_id": batch, "attachment_id": attachment_id,
                "target_finding": target_finding_key, "corrections": [], "reason": "corrected values equal current"}

    # (4) Apply the corrected staging then propagate.
    for page_label, fields in corrected_pages.items():
        record_classification(attachment_id, page_label, fields, target=target)
    _propagate(attachment_id, period, target, cache_dir)

    # (5) AFTER findings + verify-after.
    after = _finding_keys(scope, target, cache_dir)
    ok, reason = verify_after(before, after, target_finding_key)

    created = now_ms()

    def build_rows(status: str, detail: str | None) -> list[dict]:
        rows = []
        for page_label, d in diffs:
            rows.append(
                correction_row(
                    row_id=correction_id(batch, page_label, d["field"]),
                    batch=batch,
                    attachment_id=attachment_id,
                    period=period,
                    page_label=page_label,
                    field=d["field"],
                    from_value=d["from"],
                    to_value=d["to"],
                    evidence=evidence,
                    agent=agent,
                    target_finding_key=target_finding_key,
                    status=status,
                    detail=detail,
                    from_staging=snapshot,
                    created_at=created,
                )
            )
        return rows

    if ok:
        rows = build_rows(STATUS_APPLIED, "verify-after passed")
        _write_rows(rows, target)
        logger.info("apply-correction %s: applied %d field correction(s)", attachment_id, len(rows))
        return {"result": "applied", "batch_id": batch, "attachment_id": attachment_id,
                "target_finding": target_finding_key, "corrections": _summary(rows)}

    # Verify failed → roll back to the snapshot, re-propagate to re-derive the prior analysis.
    restored = _restore_staging(attachment_id, snapshot, target)
    if restored:
        _propagate(attachment_id, period, target, cache_dir)
        status, result_detail = STATUS_ROLLED_BACK, f"verify-after failed ({reason}); rolled back"
    else:
        status, result_detail = STATUS_FLAGGED, f"verify-after failed ({reason}); ROLLBACK ALSO FAILED — needs a human"
    rows = build_rows(status, result_detail)
    _write_rows(rows, target)
    logger.warning("apply-correction %s: %s", attachment_id, result_detail)
    return {"result": status, "batch_id": batch, "attachment_id": attachment_id,
            "target_finding": target_finding_key, "corrections": _summary(rows), "reason": reason}


def _summary(rows: list[dict]) -> list[dict]:
    """Terse per-field view for the result payload (decode the JSON-encoded from/to)."""
    out = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "field": r["field"],
                "from": json.loads(r["from_value"]),
                "to": json.loads(r["to_value"]),
                "page": r["page_label"],
                "status": r["status"],
            }
        )
    return out


def list_corrections(
    *,
    attachment_ids: list[str] | None = None,
    period: str | None = None,
    status: str | None = None,
    target: Target = "local",
) -> list[dict]:
    """List recorded corrections, optionally scoped (FR-006). Read-only.

    Returns rows ordered ``created_at DESC, id`` with ``from_value``/``to_value`` decoded back to
    their values (and ``from_staging`` left as stored text — it is the bulky restore blob, not for
    display). Scope filters AND together."""
    clauses = []
    if attachment_ids:
        ids = ",".join(_q(a) for a in attachment_ids)
        clauses.append(f"attachment_id IN ({ids})")
    if period:
        clauses.append(f"period = {_q(period)}")
    if status:
        clauses.append(f"status = {_q(status)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = d1.query(
        f"SELECT id, batch_id, attachment_id, period, page_label, field, from_value, to_value, "
        f"evidence, agent, target_finding_key, status, detail, created_at, reverted_at, reverted_by "
        f"FROM {TABLE}{where} ORDER BY created_at DESC, id",
        target=target,
    )
    for r in rows:
        for col in ("from_value", "to_value"):
            v = r.get(col)
            if isinstance(v, str) and v:
                try:
                    r[col] = json.loads(v)
                except json.JSONDecodeError:
                    pass
    return rows


def undo_correction(
    correction_or_batch_id: str,
    *,
    actor: str = UNDO_ACTOR_DEFAULT,
    target: Target = "local",
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> dict:
    """Reverse a previously-applied correction (FR-007/FR-008).

    Accepts a row id OR a ``batch_id`` (the whole batch reverses together — its field rows share one
    ``from_staging``). Rejected unless every row of the batch is ``applied`` (``can_undo``) with NO
    data change. Otherwise restore the snapshot, re-propagate, and stamp the batch ``reverted``."""
    ident = _q(correction_or_batch_id)
    rows = d1.query(
        f"SELECT id, batch_id, attachment_id, period, status, from_staging FROM {TABLE} "
        f"WHERE batch_id = {ident} OR id = {ident}",
        target=target,
    )
    if not rows:
        return {"result": "rejected", "batch_id": correction_or_batch_id, "reason": "correction not found"}

    batch = rows[0]["batch_id"]
    # Re-read by batch so a row-id input still reverses the whole call atomically.
    batch_rows = [r for r in rows if r["batch_id"] == batch] if any(r["id"] == correction_or_batch_id for r in rows) else rows
    if any(r["batch_id"] != batch for r in batch_rows):
        batch_rows = d1.query(
            f"SELECT id, batch_id, attachment_id, period, status, from_staging FROM {TABLE} "
            f"WHERE batch_id = {_q(batch)}",
            target=target,
        )

    bad = [r["status"] for r in batch_rows if not can_undo(r["status"])]
    if bad:
        return {"result": "rejected", "batch_id": batch,
                "reason": f"only 'applied' corrections can be undone; batch status: {sorted(set(bad))}"}

    attachment_id = batch_rows[0]["attachment_id"]
    period = batch_rows[0].get("period")
    raw_snapshot = batch_rows[0].get("from_staging")
    snapshot = []
    if isinstance(raw_snapshot, str) and raw_snapshot:
        try:
            snapshot = json.loads(raw_snapshot)
        except json.JSONDecodeError:
            snapshot = []
    elif isinstance(raw_snapshot, list):
        snapshot = raw_snapshot

    restored = _restore_staging(attachment_id, snapshot, target)
    if not restored:
        return {"result": "rejected", "batch_id": batch, "reason": "failed to restore the pre-correction snapshot"}
    _propagate(attachment_id, period, target, cache_dir)

    _update_batch_status(batch, STATUS_REVERTED, detail="reverted by human undo",
                         reverted_at=now_ms(), reverted_by=actor, target=target)
    logger.info("undo-correction %s: reverted batch %s by %s", attachment_id, batch, actor)
    return {"result": "reverted", "batch_id": batch}
