"""Check registry and orchestrator."""

import logging

from ..models import Alert, PeriodData, RefIndex
from .consistency import run_consistency
from .trends import run_trends
from .advanced import run_advanced

logger = logging.getLogger(__name__)


def run_all_checks(
    periods: dict[str, PeriodData],
    refs: RefIndex,
) -> dict[str, list[Alert]]:
    """Run all checks across all periods.

    Returns dict mapping period -> list of alerts.
    """
    alerts_by_period: dict[str, list[Alert]] = {p: [] for p in periods}

    for period_key, period in periods.items():
        alerts_by_period[period_key].extend(run_consistency(period, periods, refs))
        alerts_by_period[period_key].extend(run_trends(period, periods, refs))
        alerts_by_period[period_key].extend(run_advanced(period, periods, refs))

    total = sum(len(a) for a in alerts_by_period.values())
    logger.info("Total: %d alerts across %d periods", total, len(periods))
    return alerts_by_period
