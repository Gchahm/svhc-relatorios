"""Console output formatting for analysis results."""

from .models import Alert

SEVERITY_ICONS = {"critical": "!!", "warning": "! ", "info": "i "}
SCORE_WEIGHTS = {"critical": 10, "warning": 5, "info": 1}


def print_summary(alerts_by_period: dict[str, list[Alert]]) -> None:
    total = sum(len(a) for a in alerts_by_period.values())
    if total == 0:
        print("\nNo alerts found.")
        return

    print(f"\n{'='*70}")
    print(f"  ANALYSIS SUMMARY — {total} alert(s) across {len(alerts_by_period)} period(s)")
    print(f"{'='*70}")

    for period in sorted(alerts_by_period.keys()):
        alerts = alerts_by_period[period]
        if not alerts:
            continue

        score = sum(SCORE_WEIGHTS.get(a.severity, 1) for a in alerts)
        critical = sum(1 for a in alerts if a.severity == "critical")
        warning = sum(1 for a in alerts if a.severity == "warning")
        info = sum(1 for a in alerts if a.severity == "info")

        print(f"\n  {period}  (score: {score} | {critical} critical, {warning} warning, {info} info)")
        print(f"  {'-'*66}")

        for a in sorted(alerts, key=lambda x: ("critical", "warning", "info").index(x.severity)):
            icon = SEVERITY_ICONS.get(a.severity, "  ")
            print(f"    [{icon}] {a.title}")

    # Grand totals
    all_alerts = [a for alerts in alerts_by_period.values() for a in alerts]
    total_score = sum(SCORE_WEIGHTS.get(a.severity, 1) for a in all_alerts)
    print(f"\n{'='*70}")
    print(f"  TOTAL: {len(all_alerts)} alerts | Score: {total_score}")
    print(f"    Critical: {sum(1 for a in all_alerts if a.severity == 'critical')}")
    print(f"    Warning:  {sum(1 for a in all_alerts if a.severity == 'warning')}")
    print(f"    Info:     {sum(1 for a in all_alerts if a.severity == 'info')}")
    print(f"{'='*70}\n")
