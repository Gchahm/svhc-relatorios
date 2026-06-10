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
        # Recomputed each run: clear this period's alerts first so none go stale.
        d1.execute_sql(f"DELETE FROM alerts WHERE reference_period = '{period}'", target=target)
        rows = [a.to_dict() for a in alerts]
        if rows:
            d1.upsert_tables({"alerts": rows}, target=target)
        logger.info("%s: %d alerts written to D1 (%s)", period_key, len(alerts), target)

    # Document overpayment is GLOBAL (cross-period): recompute it once over the whole
    # documents graph and write via a delete-by-type so it stays idempotent regardless
    # of which periods were filtered (the per-period delete above can't clear a
    # cross-period alert). Supersedes the retired duplicate_billing over-claim check.
    overpayment_alerts = check_document_overpayment(target=target)
    d1.execute_sql("DELETE FROM alerts WHERE type = 'document_overpayment'", target=target)
    if overpayment_alerts:
        d1.upsert_tables({"alerts": [a.to_dict() for a in overpayment_alerts]}, target=target)
    logger.info("document_overpayment: %d alert(s) written to D1 (%s)", len(overpayment_alerts), target)

    print_summary(alerts_by_period)
