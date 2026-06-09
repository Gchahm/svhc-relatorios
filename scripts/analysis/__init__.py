"""Analysis module — runs financial checks on period data loaded from D1."""

import logging

from common import d1
from common.d1 import Target

from .checks import run_all_checks
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

    # Bring images local so the duplicate-billing check can content-hash & group NFs.
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

    print_summary(alerts_by_period)
