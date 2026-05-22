"""Load period JSON files and build analysis data structures."""

import json
import logging
from pathlib import Path

from .models import PeriodData, RefIndex

logger = logging.getLogger(__name__)


def load_all_periods(
    data_dir: str,
    periods_filter: list[str] | None = None,
) -> tuple[dict[str, PeriodData], RefIndex]:
    """Load all period JSON files and build merged reference index.

    Returns (periods dict sorted chronologically, merged RefIndex).
    """
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("*.json"))

    if periods_filter:
        json_files = [f for f in json_files if f.stem in periods_filter]

    refs = RefIndex()
    periods: dict[str, PeriodData] = {}

    for json_file in json_files:
        raw = json.loads(json_file.read_text(encoding="utf-8"))
        period = json_file.stem

        reports = raw.get("accountability_reports", [])
        if not reports:
            logger.warning("Skipping %s: no accountability report", period)
            continue

        refs.merge_period(raw, period)

        periods[period] = PeriodData(
            period=period,
            raw=raw,
            report=reports[0],
            entries=raw.get("entries", []),
            category_subtotals=raw.get("category_subtotals", []),
            documents=raw.get("documents", []),
        )

    # Also scan all periods for vendor first-seen (even filtered ones need full context)
    if periods_filter:
        all_refs = RefIndex()
        for json_file in sorted(data_path.glob("*.json")):
            raw = json.loads(json_file.read_text(encoding="utf-8"))
            all_refs.merge_period(raw, json_file.stem)
        refs.vendor_first_seen = all_refs.vendor_first_seen

    logger.info("Loaded %d period(s) with %d subcategories, %d vendors, %d units",
                len(periods), len(refs.subcategories), len(refs.vendors), len(refs.units))

    return dict(sorted(periods.items())), refs
