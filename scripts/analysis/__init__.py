"""Analysis module — runs financial checks on period data loaded from D1."""

import logging

from common import d1
from common.d1 import Target

from .checks import run_all_checks
from .documents import build_documents, check_document_overpayment
from .images import materialize_period_images
from .loader import load_all_periods
from .reporter import print_summary

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "../.cache/analysis"


def _read_existing_resolution(where_clause: str, target: Target) -> dict[str, dict]:
    """Read user-set resolution state for the alert rows a writeback is about to delete.

    Alert ids are deterministic, so an alert re-emitted by a re-run has the same id as the row
    the user previously resolved/annotated. Returning that state lets ``run_analysis`` graft it
    back onto the freshly-built rows (feature 023 / issue #34) instead of wiping it on every run.

    Returns ``{id: {"resolved", "resolved_at", "notes"}}`` for rows that actually carry
    disposition (``resolved`` truthy OR ``notes`` non-empty); default-state rows contribute
    nothing (a fresh insert already produces that default). ``where_clause`` MUST match the
    matching delete's WHERE so the read and the delete cover the same scope.
    """
    rows = d1.query(
        f"SELECT id, resolved, resolved_at, notes FROM alerts WHERE {where_clause}",
        target=target,
    )
    state: dict[str, dict] = {}
    for r in rows:
        resolved = r.get("resolved")
        notes = r.get("notes")
        if resolved or (notes not in (None, "")):
            state[r["id"]] = {
                "resolved": resolved or 0,
                "resolved_at": r.get("resolved_at"),
                "notes": notes,
            }
    return state


def _graft_resolution(rows: list[dict], existing: dict[str, dict]) -> None:
    """Overwrite the resolution fields of re-emitted alert rows with the user's prior disposition.

    Only rows whose id is in ``existing`` are touched; a brand-new alert (no prior row) keeps the
    unresolved default from ``Alert.to_dict`` (FR-005). Rows whose finding no longer fires are
    simply absent from ``rows`` and are dropped by the delete (FR-003) — this never re-inserts them.
    """
    for row in rows:
        prior = existing.get(row["id"])
        if prior is not None:
            row["resolved"] = prior["resolved"]
            row["resolved_at"] = prior["resolved_at"]
            row["notes"] = prior["notes"]


def run_analysis(
    target: Target = "local",
    periods_filter: list[str] | None = None,
    *,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> None:
    """Run the full analysis pipeline on period data from D1.

    Loads periods from D1, materializes page images from R2 (the duplicate-billing
    check hashes them to group shared NFs), runs checks, writes alerts back to D1
    (delete-then-insert per period so a re-run leaves no stale alert), and prints a
    console summary.
    """
    periods, refs = load_all_periods(target, periods_filter)

    if not periods:
        logger.info("No periods to analyze")
        return

    # Build the global documents entity (+ entry links) from attachment_analyses before
    # the checks, so the documents/overpayment signal reflects the latest extractions.
    # Global by design (reads D1 across all periods), independent of periods_filter.
    build_documents(target=target)

    # Bring images local so per-page content-hashing & NF grouping can run.
    materialize_period_images(periods, cache_dir, target)

    alerts_by_period = run_all_checks(periods, refs)

    for period_key, alerts in alerts_by_period.items():
        period = period_key.replace("'", "''")
        where = f"reference_period = '{period}'"
        rows = [a.to_dict() for a in alerts]
        # Carry user-set resolution/notes onto alerts that re-fire with the same id, BEFORE the
        # delete wipes the existing rows (feature 023 / issue #34).
        _graft_resolution(rows, _read_existing_resolution(where, target))
        # Recomputed each run: clear this period's alerts first so none go stale.
        d1.execute_sql(f"DELETE FROM alerts WHERE {where}", target=target)
        if rows:
            d1.upsert_tables({"alerts": rows}, target=target)
        logger.info("%s: %d alerts written to D1 (%s)", period_key, len(alerts), target)

    # Document overpayment is GLOBAL (cross-period): recompute it once over the whole
    # documents graph and write via a delete-by-type so it stays idempotent regardless
    # of which periods were filtered (the per-period delete above can't clear a
    # cross-period alert). Supersedes the retired duplicate_billing over-claim check.
    overpayment_alerts = check_document_overpayment(target=target)
    overpayment_rows = [a.to_dict() for a in overpayment_alerts]
    # Same resolution-preservation as the per-period path, scoped to the global delete's WHERE.
    _graft_resolution(overpayment_rows, _read_existing_resolution("type = 'document_overpayment'", target))
    d1.execute_sql("DELETE FROM alerts WHERE type = 'document_overpayment'", target=target)
    if overpayment_rows:
        d1.upsert_tables({"alerts": overpayment_rows}, target=target)
    logger.info("document_overpayment: %d alert(s) written to D1 (%s)", len(overpayment_alerts), target)

    print_summary(alerts_by_period)
