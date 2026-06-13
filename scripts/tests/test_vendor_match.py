"""Tests for analysis.vendor_match reconciliation (TEST-002 / issue #69). Pure, stdlib-only."""

import unittest

from analysis.vendor_match import (
    is_payer_name,
    names_match,
    normalize_company_name,
    normalize_tokens,
    reconcile_vendor,
)


class NormalizeTest(unittest.TestCase):
    def test_accents_and_case(self):
        self.assertEqual(normalize_company_name("Comércio LTDA"), "COMERCIO")

    def test_abbreviation_expansion(self):
        self.assertEqual(normalize_tokens("COM. de Tintas"), ["COMERCIO", "TINTAS"])

    def test_legal_suffix_and_stopwords_dropped(self):
        self.assertEqual(normalize_tokens("ACME E FILHOS LTDA"), ["ACME", "FILHOS"])

    def test_single_letter_join(self):
        self.assertEqual(normalize_tokens("M G 2 Servicos"), ["MG2", "SERVICOS"])

    def test_empty(self):
        self.assertEqual(normalize_tokens(None), [])
        self.assertEqual(normalize_company_name(""), "")


class IsPayerNameTest(unittest.TestCase):
    def test_denylist(self):
        self.assertTrue(is_payer_name("São Vicente Home Club"))
        self.assertTrue(is_payer_name("CONDOMINIO SAO VICENTE HOME CLUB"))

    def test_other_name(self):
        self.assertFalse(is_payer_name("ACME LTDA"))

    def test_empty(self):
        self.assertFalse(is_payer_name(None))


class NamesMatchTest(unittest.TestCase):
    def test_equality(self):
        self.assertTrue(names_match("ACME COMERCIO LTDA", "Acme Comercio"))

    def test_substring_long(self):
        self.assertTrue(names_match("ESCRISUL DISTRIBUIDORA DE PAPEIS", "Escrisul"))

    def test_alias_group(self):
        self.assertTrue(names_match("COPAGAZ", "COPA ENERGIA"))

    def test_payer_never_matches(self):
        self.assertFalse(names_match("Sao Vicente Home Club", "Sao Vicente Home Club"))

    def test_distinct_entities(self):
        self.assertFalse(names_match("ACME TINTAS", "BETA SERVICOS"))

    def test_empty(self):
        self.assertFalse(names_match(None, "X"))
        self.assertFalse(names_match("X", None))

    def test_short_name_requires_strong_match(self):
        # A short fragment must not match a longer unrelated name by bare substring.
        self.assertFalse(names_match("AB", "ABACAXI COMERCIO"))


class ReconcileVendorTest(unittest.TestCase):
    def test_none_when_no_vendor(self):
        self.assertIsNone(reconcile_vendor(None, ["ACME"]))

    def test_none_when_no_candidate(self):
        self.assertIsNone(reconcile_vendor("ACME", []))
        # only a payer name present → nothing to compare
        self.assertIsNone(reconcile_vendor("ACME", ["Sao Vicente Home Club"]))

    def test_true_when_any_matches(self):
        self.assertTrue(reconcile_vendor("ACME COMERCIO", ["OTHER", "Acme Comercio LTDA"]))

    def test_false_when_none_match(self):
        self.assertFalse(reconcile_vendor("ACME COMERCIO", ["BETA SERVICOS"]))


if __name__ == "__main__":
    unittest.main()
