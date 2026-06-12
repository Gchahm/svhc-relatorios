"""Tests for the tolerant BRL currency parser (feature 030 / IMP-001 / issue #38).

``parse_brl`` must convert well-formed BRL strings to floats AND fail soft (return ``None``, never
raise) on malformed input, so a single bad ledger cell fails its row, not the whole period. Covers:

- US1 — round-trip: well-formed portal strings parse to the expected float (SC-003).
- US2 — robustness: empty/whitespace/junk and NaN/inf-source strings → ``None``, never raise
  (FR-004, SC-002, SC-004).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import math
import unittest

from scraper.extractors.demonstrativo import parse_brl


class TestParseBrlValid(unittest.TestCase):
    def test_with_currency_symbol(self):
        self.assertEqual(parse_brl("R$ 1.234,56"), 1234.56)

    def test_without_currency_symbol(self):
        self.assertEqual(parse_brl("443.995,17"), 443995.17)

    def test_zero(self):
        self.assertEqual(parse_brl("0,00"), 0.0)

    def test_small_value_no_thousands(self):
        self.assertEqual(parse_brl("50,00"), 50.0)

    def test_large_value_multiple_thousands(self):
        self.assertEqual(parse_brl("1.234.567,89"), 1234567.89)

    def test_extra_whitespace(self):
        self.assertEqual(parse_brl("  R$  12,00  "), 12.0)

    def test_negative(self):
        self.assertEqual(parse_brl("-50,00"), -50.0)


class TestParseBrlInvalid(unittest.TestCase):
    def test_empty_string(self):
        self.assertIsNone(parse_brl(""))

    def test_whitespace_only(self):
        self.assertIsNone(parse_brl("   "))

    def test_currency_symbol_only(self):
        self.assertIsNone(parse_brl("R$"))

    def test_dashes_placeholder(self):
        self.assertIsNone(parse_brl("R$ --,--"))

    def test_pure_junk(self):
        self.assertIsNone(parse_brl("abc"))

    def test_none_input(self):
        self.assertIsNone(parse_brl(None))

    def test_does_not_raise_on_junk(self):
        # The point of the feature: never raise for a str input.
        for bad in ["", "   ", "??", "R$ x,yz", "1,2,3,4"]:
            with self.subTest(bad=bad):
                try:
                    result = parse_brl(bad)
                except Exception as exc:  # pragma: no cover - failure path
                    self.fail(f"parse_brl raised on {bad!r}: {exc}")
                # result may be a float or None, but must be finite when a float
                if result is not None:
                    self.assertTrue(math.isfinite(result))


class TestParseBrlNonFinite(unittest.TestCase):
    def test_nan_source(self):
        self.assertIsNone(parse_brl("nan"))

    def test_inf_source(self):
        self.assertIsNone(parse_brl("inf"))

    def test_negative_inf_source(self):
        self.assertIsNone(parse_brl("-inf"))


if __name__ == "__main__":
    unittest.main()
