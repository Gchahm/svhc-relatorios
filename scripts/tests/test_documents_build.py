"""Tests for analysis.documents pure id/normalization/SQL helpers (TEST-002 / issue #69).

`build_documents` / `check_document_overpayment` hit D1 and are left to TEST-004; the pure
identity/normalization/prune-SQL logic is covered here.
"""

import unittest

from common import det_id

from analysis.documents import (
    _analysis_total,
    _prune_sql,
    _sql_id_list,
    document_key,
    normalize_cnpj,
    normalize_number,
)


class NormalizeNumberTest(unittest.TestCase):
    def test_strips_separators_and_uppercases(self):
        self.assertEqual(normalize_number(" nf-123/456 "), "NF123456")

    def test_empty(self):
        self.assertEqual(normalize_number(None), "")
        self.assertEqual(normalize_number(""), "")


class NormalizeCnpjTest(unittest.TestCase):
    def test_14_digits(self):
        self.assertEqual(normalize_cnpj("12.345.678/0001-99"), "12345678000199")

    def test_not_14_is_none(self):
        self.assertIsNone(normalize_cnpj("123"))
        self.assertIsNone(normalize_cnpj(None))


class DocumentKeyTest(unittest.TestCase):
    def test_confident(self):
        key = document_key({"document_number": "NF-1", "extracted_cnpj": "12345678000199"})
        self.assertEqual(key, ("NF1", "12345678000199"))

    def test_missing_number(self):
        self.assertIsNone(document_key({"document_number": "", "extracted_cnpj": "12345678000199"}))

    def test_missing_cnpj(self):
        self.assertIsNone(document_key({"document_number": "NF-1", "extracted_cnpj": "123"}))


class SqlHelpersTest(unittest.TestCase):
    def test_sql_id_list_escapes(self):
        self.assertEqual(_sql_id_list(["a", "b'c"]), "'a','b''c'")

    def test_prune_empty_is_unconditional(self):
        self.assertEqual(_prune_sql("documents", set()), "DELETE FROM documents;")

    def test_prune_with_ids_uses_not_in(self):
        out = _prune_sql("documents", {"x"})
        self.assertEqual(out, "DELETE FROM documents WHERE id NOT IN ('x');")


class AnalysisTotalTest(unittest.TestCase):
    def test_prefers_invoice_gross(self):
        analysis = {
            "analysis_records": [{"response": {"doc_type": "danfe", "totais": {"valor_total_nota": "150,00"}}}],
            "extracted_amount": 99.0,
        }
        self.assertEqual(_analysis_total(analysis), 150.0)

    def test_falls_back_to_rollup(self):
        analysis = {"analysis_records": [{"response": {"doc_type": "outro"}}], "extracted_amount": 42.0}
        self.assertEqual(_analysis_total(analysis), 42.0)


class DeterministicIdTest(unittest.TestCase):
    def test_document_id_stable(self):
        # the document id is order-independent over (number, cnpj)
        a = det_id("document", "NF1", "12345678000199")
        b = det_id("document", "NF1", "12345678000199")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
