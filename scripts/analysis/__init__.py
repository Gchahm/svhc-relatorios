"""Analysis module — runs financial checks on scraped period data."""

import json
import logging
from pathlib import Path

from .checks import run_all_checks
from .loader import load_all_periods
from .reporter import print_summary

logger = logging.getLogger(__name__)


def run_analysis(
    data_dir: str,
    periods_filter: list[str] | None = None,
) -> None:
    """Run full analysis pipeline on scraped JSON data.

    Loads all period files, runs checks, writes alerts back to JSONs,
    and prints a console summary.
    """
    periods, refs = load_all_periods(data_dir, periods_filter)

    if not periods:
        logger.info("No periods to analyze")
        return

    alerts_by_period = run_all_checks(periods, refs)

    # Write alerts back to JSON files
    data_path = Path(data_dir)
    for period_key, alerts in alerts_by_period.items():
        period_data = periods[period_key]
        period_data.raw["alerts"] = [a.to_dict() for a in alerts]

        json_file = data_path / f"{period_key}.json"
        json_file.write_text(
            json.dumps(period_data.raw, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("%s: %d alerts written", period_key, len(alerts))

    print_summary(alerts_by_period)
