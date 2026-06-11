"""Authoritative re-scrape reconciliation of portal deletions (BUG-004 / issue #35).

The scrape is otherwise add/update-only: a period re-scrape upserts the rows that still exist on the
brcondos portal but leaves rows that were *removed* from the portal in D1 forever, so the mirror
tables (``entries``, ``attachments``, ``category_subtotals``, ``approvers``) silently stop being an
EXACT mirror of the portal. Because a row that vanishes from the portal is itself a fraud signal,
this module makes a re-scrape authoritative: it diffs the freshly-scraped row set against what D1
holds for the period, hard-deletes the stale (vanished) mirror rows, cascade-cleans every
analysis-owned dependent keyed to a removed entry/attachment, and raises one idempotent ``critical``
``portal_row_vanished`` alert recording the vanished rows' frozen values as evidence.

Strict mirror + evidence-in-alert: the mirror rows are hard-deleted (so ``entries``/``attachments``
stay an exact portal mirror — no soft-delete column is added to a mirror table), while the evidence
lives in the analysis-owned ``alerts`` table (its ``metadata`` JSON). No schema migration.

Kept stdlib-only and free of the scraper's playwright import so it is unit-testable directly (see
``scripts/tests/test_reconcile.py``), mirroring ``scripts/scraper/preserve.py``. This module is PURE:
it builds the reconciliation SQL batch + alert payload from already-fetched data and performs no I/O.
The impure reads (``d1.query``) and the single batched ``d1.execute_sql`` live in ``runner.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from common import det_id as _det_id, now_ms as _now_ms

ALERT_TYPE = "portal_row_vanished"
ALERT_SEVERITY = "critical"


# ─── Inputs / output ─────────────────────────────────────────────────────────


@dataclass
class ExistingRows:
    """Rows currently in D1 for the period (read back AFTER the upsert, in runner.py)."""

    entries: list[dict] = field(default_factory=list)          # each: {id, date, description, amount}
    attachments: list[dict] = field(default_factory=list)      # each: {id, entry_id}
    subtotal_ids: set[str] = field(default_factory=set)
    approver_ids: set[str] = field(default_factory=set)


@dataclass
class ScrapedIds:
    """Id sets the current scrape produced for the period (from the in-memory period payload)."""

    entry_ids: set[str] = field(default_factory=set)
    attachment_ids: set[str] = field(default_factory=set)
    subtotal_ids: set[str] = field(default_factory=set)
    approver_ids: set[str] = field(default_factory=set)


@dataclass
class ReconcileResult:
    sql: str                                # the batch SQL ("" only when there is nothing to do)
    deleted_counts: dict[str, int]          # {entries, attachments, category_subtotals, approvers}
    alert: dict | None                      # the alerts row dict to INSERT, or None when nothing vanished


# ─── SQL helpers ───────────────────────────────────────────────────────────────


def _sql_str(value) -> str:
    """Escape a value as a SQL string literal (single quotes doubled). Mirrors d1._escape_sql."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'"
    return "'" + str(value).replace("'", "''") + "'"


def _in_list(ids) -> str | None:
    """Render a SQL ``IN`` tuple for a non-empty id collection, else None (skip the statement)."""
    ids = list(ids)
    if not ids:
        return None
    return "(" + ", ".join(_sql_str(i) for i in ids) + ")"


# ─── Reconciliation ──────────────────────────────────────────────────────────


def build_reconciliation(period: str, existing: ExistingRows, scraped: ScrapedIds) -> ReconcileResult:
    """Build the reconciliation SQL batch + vanished-row alert for one period (pure).

    ``stale`` per table = ids in D1 for the period that the current scrape did NOT produce. An
    attachment is stale if it is gone from the scrape OR its owning entry vanished (entry-gone wins).
    The returned ``sql`` is ONE batch string: ``PRAGMA defer_foreign_keys = ON;`` + the cascade
    DELETEs (child→parent, only for non-empty id sets) + the mirror DELETEs + an ALWAYS-issued
    ``DELETE FROM alerts WHERE type=<ALERT_TYPE> AND reference_period=<period>`` (clears any prior
    per-period alert) + — only when something is stale — the ``INSERT OR REPLACE INTO alerts`` row.
    Running it in a single ``execute_sql`` makes the deletes + evidence one D1 batch (atomic).

    Every DELETE is scoped to the stale id sets or this period, so surviving rows and other periods
    are never matched. When nothing is stale the result still carries the clear-only alert DELETE so
    the alert is truly idempotent (a re-scrape that reverts a deletion clears the stale alert).
    """
    existing_entry_ids = {e["id"] for e in existing.entries}
    existing_attachment_ids = {a["id"] for a in existing.attachments}

    stale_entry_ids = existing_entry_ids - scraped.entry_ids
    # An attachment is stale if it's gone from the scrape OR its owning entry vanished.
    stale_attachment_ids = (existing_attachment_ids - scraped.attachment_ids) | {
        a["id"] for a in existing.attachments if a.get("entry_id") in stale_entry_ids
    }
    stale_subtotal_ids = existing.subtotal_ids - scraped.subtotal_ids
    stale_approver_ids = existing.approver_ids - scraped.approver_ids

    deleted_counts = {
        "entries": len(stale_entry_ids),
        "attachments": len(stale_attachment_ids),
        "category_subtotals": len(stale_subtotal_ids),
        "approvers": len(stale_approver_ids),
    }
    anything_stale = any(deleted_counts.values())

    se = _in_list(stale_entry_ids)
    sa = _in_list(stale_attachment_ids)
    ss = _in_list(stale_subtotal_ids)
    sap = _in_list(stale_approver_ids)

    period_lit = _sql_str(period)
    stmts: list[str] = ["PRAGMA defer_foreign_keys = ON;"]

    # ── Cascade-clean analysis-owned dependents (child → parent) ──
    if sa:
        stmts.append(
            f'DELETE FROM "attachment_analysis_records" WHERE "attachment_analysis_id" IN '
            f'(SELECT "id" FROM "attachment_analyses" WHERE "attachment_id" IN {sa});'
        )
        stmts.append(f'DELETE FROM "attachment_analyses" WHERE "attachment_id" IN {sa};')
        stmts.append(f'DELETE FROM "attachment_state" WHERE "attachment_id" IN {sa};')
        stmts.append(f'DELETE FROM "page_classifications" WHERE "attachment_id" IN {sa};')
    # document_entries links a removed entry (entry_id) and/or a removed attachment (source_attachment_id).
    if se or sa:
        conds = []
        if se:
            conds.append(f'"entry_id" IN {se}')
        if sa:
            conds.append(f'"source_attachment_id" IN {sa}')
        stmts.append(f'DELETE FROM "document_entries" WHERE {" OR ".join(conds)};')

    # ── Hard-delete the stale mirror rows ──
    if sa:
        stmts.append(f'DELETE FROM "attachments" WHERE "id" IN {sa};')
    if se:
        stmts.append(f'DELETE FROM "entries" WHERE "id" IN {se};')
    if ss:
        stmts.append(f'DELETE FROM "category_subtotals" WHERE "id" IN {ss};')
    if sap:
        stmts.append(f'DELETE FROM "approvers" WHERE "id" IN {sap};')

    # ── Vanished-row alert: ALWAYS clear this period's prior alert, then re-insert if stale ──
    stmts.append(
        f'DELETE FROM "alerts" WHERE "type" = {_sql_str(ALERT_TYPE)} '
        f'AND "reference_period" = {period_lit};'
    )

    alert: dict | None = None
    if anything_stale:
        alert = _build_alert(period, existing, stale_entry_ids, stale_attachment_ids,
                             stale_subtotal_ids, stale_approver_ids, deleted_counts)
        cols = list(alert.keys())
        col_list = ", ".join(f'"{c}"' for c in cols)
        values = ", ".join(_sql_str(alert[c]) for c in cols)
        stmts.append(f'INSERT OR REPLACE INTO "alerts" ({col_list}) VALUES ({values});')

    return ReconcileResult(sql="\n".join(stmts), deleted_counts=deleted_counts, alert=alert)


def _build_alert(
    period: str,
    existing: ExistingRows,
    stale_entry_ids: set[str],
    stale_attachment_ids: set[str],
    stale_subtotal_ids: set[str],
    stale_approver_ids: set[str],
    deleted_counts: dict[str, int],
) -> dict:
    """Build the ``portal_row_vanished`` alerts row dict (matches analysis Alert.to_dict shape)."""
    deleted_entries = [
        {
            "id": e["id"],
            "date": e.get("date"),
            "description": e.get("description"),
            "amount": e.get("amount"),
        }
        for e in existing.entries
        if e["id"] in stale_entry_ids
    ]
    metadata = {
        # feature-018 deep-link convention (the alerts UI reads metadata.entry_ids).
        "entry_ids": sorted(stale_entry_ids),
        # frozen evidence so the loss is auditable after the rows are gone (FR-006).
        "deleted_entries": deleted_entries,
        "deleted_attachment_ids": sorted(stale_attachment_ids),
        "deleted_subtotal_ids": sorted(stale_subtotal_ids),
        "deleted_approver_ids": sorted(stale_approver_ids),
        "counts": deleted_counts,
    }
    total = sum(deleted_counts.values())
    return {
        # Stable per-period id → idempotent across re-scrapes.
        "id": _det_id("alert", period, ALERT_TYPE),
        "created_at": _now_ms(),
        "type": ALERT_TYPE,
        "severity": ALERT_SEVERITY,
        "title": f"{total} ledger row(s) vanished from portal — {period}",
        "description": (
            f"A re-scrape of {period} found {total} row(s) present in the mirror but no longer on "
            f"the brcondos portal — removed between scrapes. Counts: "
            f"entries={deleted_counts['entries']}, attachments={deleted_counts['attachments']}, "
            f"category_subtotals={deleted_counts['category_subtotals']}, "
            f"approvers={deleted_counts['approvers']}. Their frozen values are recorded as evidence."
        ),
        "reference_period": period,
        "metadata": json.dumps(metadata, ensure_ascii=False),
        "resolved": 0,
        "resolved_at": None,
        "notes": None,
    }
