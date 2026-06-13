"""Tests for analysis.checks.advanced (TEST-002 / issue #69). Pure over PeriodData/RefIndex."""

import unittest

from analysis.checks.advanced import (
    CONCENTRATION_LIMIT,
    check_category_growth,
    check_delinquency,
    check_seasonality,
    check_vendor_concentration,
    run_advanced,
)

from tests._fixtures import entry, make_period, make_refs, make_report


class VendorConcentrationTest(unittest.TestCase):
    def test_fires_above_limit(self):
        # v1 = 400 of 1000 expenses = 40% > 30%; v2/v3 each below the limit.
        entries = [
            entry("e1", amount=400.0, vendor_id="v1"),
            entry("e2", amount=300.0, vendor_id="v2"),
            entry("e3", amount=300.0, vendor_id="v3"),
        ]
        pd = make_period("2025-12", report=make_report(total_expenses=1000.0), entries=entries)
        refs = make_refs(vendors=[{"id": "v1", "name": "BIG"}, {"id": "v2", "name": "M"}, {"id": "v3", "name": "S"}])
        alerts = check_vendor_concentration(pd, refs)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "vendor_concentration")
        self.assertEqual(alerts[0].metadata["vendor_id"], "v1")

    def test_silent_at_or_below_limit(self):
        # three vendors each at ~33% — exactly at/below the 30% boundary uses <=, so 0.30 is silent;
        # use shares strictly under 0.30 to be unambiguous.
        entries = [
            entry("e1", amount=300.0, vendor_id="v1"),
            entry("e2", amount=300.0, vendor_id="v2"),
            entry("e3", amount=400.0, vendor_id="v3"),
        ]
        pd = make_period("2025-12", report=make_report(total_expenses=1000.0), entries=entries)
        refs = make_refs(vendors=[{"id": "v1", "name": "A"}, {"id": "v2", "name": "B"}, {"id": "v3", "name": "C"}])
        # v3 is 40% → fires; adjust so all are below limit.
        entries = [entry("e1", amount=300.0, vendor_id="v1"), entry("e2", amount=300.0, vendor_id="v2"),
                   entry("e3", amount=300.0, vendor_id="v3"), entry("e4", amount=100.0, vendor_id="v4")]
        pd = make_period("2025-12", report=make_report(total_expenses=1000.0), entries=entries)
        refs = make_refs(vendors=[{"id": f"v{i}", "name": str(i)} for i in range(1, 5)])
        self.assertEqual(check_vendor_concentration(pd, refs), [])

    def test_zero_expenses_silent(self):
        pd = make_period("2025-12", report=make_report(total_expenses=0.0))
        self.assertEqual(check_vendor_concentration(pd, make_refs()), [])

    def test_limit_constant(self):
        self.assertEqual(CONCENTRATION_LIMIT, 0.30)


class CategoryGrowthTest(unittest.TestCase):
    def _periods_with_history(self, current_amount):
        # 6 prior periods, each subcategory s1 at 100; first period total_expenses 100.
        all_periods = {}
        for i in range(6):
            key = f"2025-{i + 1:02d}"
            all_periods[key] = make_period(
                key,
                report=make_report(total_expenses=100.0),
                category_subtotals=[{"subcategory_id": "s1", "movement_type": "D", "amount": 100.0}],
            )
        cur = make_period(
            "2025-07",
            report=make_report(total_expenses=110.0),  # overall growth small
            category_subtotals=[{"subcategory_id": "s1", "movement_type": "D", "amount": current_amount}],
        )
        all_periods["2025-07"] = cur
        return cur, all_periods

    def test_too_few_prior_periods_silent(self):
        cur = make_period("2025-02", category_subtotals=[{"subcategory_id": "s1", "movement_type": "D", "amount": 999.0}])
        all_periods = {"2025-01": make_period("2025-01"), "2025-02": cur}
        self.assertEqual(check_category_growth(cur, all_periods, make_refs()), [])

    def test_fires_on_outlier_growth(self):
        cur, all_periods = self._periods_with_history(current_amount=500.0)  # 400% vs avg 100
        refs = make_refs(subcategories=[{"id": "s1", "name": "LIMPEZA", "category_id": "c1"}],
                         categories=[{"id": "c1", "name": "MANUT"}])
        alerts = check_category_growth(cur, all_periods, refs)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "category_growth_outlier")

    def test_normal_growth_silent(self):
        cur, all_periods = self._periods_with_history(current_amount=120.0)
        self.assertEqual(check_category_growth(cur, all_periods, make_refs()), [])


class SeasonalityTest(unittest.TestCase):
    def test_fires_on_large_yoy_change(self):
        prev = make_period("2024-12", report=make_report(total_expenses=100.0, total_revenue=100.0))
        cur = make_period("2025-12", report=make_report(total_expenses=300.0, total_revenue=100.0))
        all_periods = {"2024-12": prev, "2025-12": cur}
        alerts = check_seasonality(cur, all_periods)
        # 200% jump in expenses (>100 → warning), revenue unchanged
        self.assertTrue(any(a.type == "seasonality_despesas" for a in alerts))
        despesa = next(a for a in alerts if a.type == "seasonality_despesas")
        self.assertEqual(despesa.severity, "warning")

    def test_no_prior_year_silent(self):
        cur = make_period("2025-12", report=make_report(total_expenses=300.0))
        self.assertEqual(check_seasonality(cur, {"2025-12": cur}), [])

    def test_small_change_silent(self):
        prev = make_period("2024-12", report=make_report(total_expenses=100.0, total_revenue=100.0))
        cur = make_period("2025-12", report=make_report(total_expenses=120.0, total_revenue=120.0))
        self.assertEqual(check_seasonality(cur, {"2024-12": prev, "2025-12": cur}), [])


class DelinquencyTest(unittest.TestCase):
    def _refs(self, n_units):
        return make_refs(
            units=[{"id": f"u{i}", "name": str(i)} for i in range(n_units)],
            subcategories=[{"id": "taxa", "name": "TAXA DE CONDOMINIO", "category_id": "c"}],
        )

    def test_no_units_silent(self):
        pd = make_period("2025-12")
        self.assertEqual(check_delinquency(pd, make_refs()), [])

    def test_no_taxa_subcategory_silent(self):
        pd = make_period("2025-12")
        refs = make_refs(units=[{"id": "u0", "name": "0"}])
        self.assertEqual(check_delinquency(pd, refs), [])

    def test_fires_with_severity_bands(self):
        refs = self._refs(10)
        # only 1 unit paid → 9/10 delinquent (90%) → critical (>15%)
        entries = [entry("e1", amount=50.0, unit_id="u0", subcategory_id="taxa", movement_type="C")]
        pd = make_period("2025-12", entries=entries)
        alerts = check_delinquency(pd, refs)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].type, "unit_delinquency")
        self.assertEqual(alerts[0].severity, "critical")
        self.assertEqual(alerts[0].metadata["delinquent"], 9)

    def test_no_delinquency_silent(self):
        refs = self._refs(2)
        entries = [
            entry("e1", amount=50.0, unit_id="u0", subcategory_id="taxa", movement_type="C"),
            entry("e2", amount=50.0, unit_id="u1", subcategory_id="taxa", movement_type="C"),
        ]
        pd = make_period("2025-12", entries=entries)
        self.assertEqual(check_delinquency(pd, refs), [])


class RunAdvancedTest(unittest.TestCase):
    def test_aggregates_without_raising(self):
        entries = [entry("e1", amount=400.0, vendor_id="v1"), entry("e2", amount=600.0, vendor_id="v2")]
        pd = make_period("2025-12", report=make_report(total_expenses=1000.0), entries=entries)
        refs = make_refs(vendors=[{"id": "v1", "name": "BIG"}, {"id": "v2", "name": "S"}])
        alerts = run_advanced(pd, {"2025-12": pd}, refs)
        self.assertTrue(any(a.type == "vendor_concentration" for a in alerts))


if __name__ == "__main__":
    unittest.main()
