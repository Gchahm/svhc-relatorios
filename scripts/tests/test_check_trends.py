"""Tests for analysis.checks.trends (TEST-002 / issue #69). Pure over PeriodData/RefIndex."""

import unittest

from analysis.checks.trends import (
    check_missing_recurring_subcategory,
    check_month_over_month,
    check_subcategory_above_average,
    run_trends,
)

from tests._fixtures import make_period, make_refs, make_report


def sub(subcategory_id, amount, movement_type="D"):
    return {"subcategory_id": subcategory_id, "movement_type": movement_type, "amount": amount}


class SubcategoryAboveAverageTest(unittest.TestCase):
    def test_too_few_prior_silent(self):
        cur = make_period("2025-02", category_subtotals=[sub("s1", 999.0)])
        all_periods = {"2025-01": make_period("2025-01", category_subtotals=[sub("s1", 100.0)]), "2025-02": cur}
        self.assertEqual(check_subcategory_above_average(cur, all_periods, make_refs()), [])

    def test_fires_above_threshold(self):
        p1 = make_period("2025-01", category_subtotals=[sub("s1", 100.0)])
        p2 = make_period("2025-02", category_subtotals=[sub("s1", 100.0)])
        cur = make_period("2025-03", category_subtotals=[sub("s1", 200.0)])  # 100% above avg 100
        all_periods = {"2025-01": p1, "2025-02": p2, "2025-03": cur}
        refs = make_refs(subcategories=[{"id": "s1", "name": "X", "category_id": "c"}],
                         categories=[{"id": "c", "name": "C"}])
        alerts = check_subcategory_above_average(cur, all_periods, refs)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "subcategory_above_average")

    def test_within_threshold_silent(self):
        p1 = make_period("2025-01", category_subtotals=[sub("s1", 100.0)])
        p2 = make_period("2025-02", category_subtotals=[sub("s1", 100.0)])
        cur = make_period("2025-03", category_subtotals=[sub("s1", 120.0)])  # 20% < 50%
        all_periods = {"2025-01": p1, "2025-02": p2, "2025-03": cur}
        self.assertEqual(check_subcategory_above_average(cur, all_periods, make_refs()), [])


class MonthOverMonthTest(unittest.TestCase):
    def test_first_period_silent(self):
        cur = make_period("2025-01", report=make_report(total_expenses=100.0))
        self.assertEqual(check_month_over_month(cur, {"2025-01": cur}), [])

    def test_fires_above_30pct(self):
        prev = make_period("2025-01", report=make_report(total_expenses=100.0, total_revenue=100.0))
        cur = make_period("2025-02", report=make_report(total_expenses=200.0, total_revenue=100.0))
        alerts = check_month_over_month(cur, {"2025-01": prev, "2025-02": cur})
        self.assertTrue(any(a.type == "month_variation_despesas" for a in alerts))

    def test_small_variation_silent(self):
        prev = make_period("2025-01", report=make_report(total_expenses=100.0, total_revenue=100.0))
        cur = make_period("2025-02", report=make_report(total_expenses=110.0, total_revenue=110.0))
        self.assertEqual(check_month_over_month(cur, {"2025-01": prev, "2025-02": cur}), [])


class MissingRecurringSubcategoryTest(unittest.TestCase):
    def test_too_few_prior_silent(self):
        cur = make_period("2025-02", category_subtotals=[sub("s1", 1.0)])
        all_periods = {"2025-01": make_period("2025-01", category_subtotals=[sub("s1", 1.0)]), "2025-02": cur}
        self.assertEqual(check_missing_recurring_subcategory(cur, all_periods, make_refs()), [])

    def test_fires_when_recurring_then_absent(self):
        p = [make_period(f"2025-0{i}", category_subtotals=[sub("s1", 1.0)]) for i in range(1, 4)]
        cur = make_period("2025-04", category_subtotals=[sub("s2", 1.0)])  # s1 missing
        all_periods = {pp.period: pp for pp in p}
        all_periods["2025-04"] = cur
        refs = make_refs(subcategories=[{"id": "s1", "name": "X", "category_id": "c"}],
                         categories=[{"id": "c", "name": "C"}])
        alerts = check_missing_recurring_subcategory(cur, all_periods, refs)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "missing_recurring_subcategory")

    def test_present_silent(self):
        p = [make_period(f"2025-0{i}", category_subtotals=[sub("s1", 1.0)]) for i in range(1, 4)]
        cur = make_period("2025-04", category_subtotals=[sub("s1", 1.0)])
        all_periods = {pp.period: pp for pp in p}
        all_periods["2025-04"] = cur
        self.assertEqual(check_missing_recurring_subcategory(cur, all_periods, make_refs()), [])


class RunTrendsTest(unittest.TestCase):
    def test_aggregates(self):
        cur = make_period("2025-01", report=make_report(total_expenses=100.0))
        out = run_trends(cur, {"2025-01": cur}, make_refs())
        self.assertEqual(out, [])  # single period → nothing fires, no raise


if __name__ == "__main__":
    unittest.main()
