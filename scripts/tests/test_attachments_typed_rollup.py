"""Roll-up over TYPED transcription records, wired through the per-type mappers (feature 053).

Exercises `build_attachment_analysis` / `nf_total_for_reconciliation` with typed JSON page records
(carrying a `doc_type` discriminator) to prove the documented `rollup-amount-false-positives.md`
Problem A false positives reconcile, that a genuine discrepancy still surfaces (no false negative),
and that a mix of typed + legacy flat records in one group still reconciles.
"""

import unittest

from analysis.attachments import build_attachment_analysis, nf_total_for_reconciliation


def provider_from(pages: dict):
    def _provider(attachment_id, page_label):
        if page_label not in pages:
            return None, "no extraction"
        parsed = pages[page_label]
        if parsed is None:
            return None, "unreadable"
        return parsed, None

    return _provider


class TypedRollupTest(unittest.TestCase):
    def test_nfse_757dedb0_reconciles_to_320_not_800(self):
        # The page legibly shows valor_liquido 320; the entry is 320. Under the old guesswork the
        # model reported 800 (false mismatch). The typed mapper derives 320 → amount_match true.
        pages = {
            "p1": {
                "doc_type": "nfse",
                "numero": "0000123",
                "data_emissao": "05/12/2025",
                "prestador": {"nome": "MANUT SV LTDA", "cnpj": "11.222.333/0001-44"},
                "valores": {"valor_servico": 320.0, "valor_liquido": 320.0},
            }
        }
        res = build_attachment_analysis(
            "x/e_p1.png", 320.0, "MANUT SV", "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertIsNone(res.error)
        self.assertEqual(res.extracted_amount, 320.0)
        self.assertTrue(res.amount_match)
        self.assertEqual(res.document_number, "0000123")
        self.assertEqual(res.extracted_cnpj, "11.222.333/0001-44")
        # Feature 055: the persisted record.response is the RAW typed JSON (verbatim — carrying
        # doc_type, so it survives into attachment_analysis_records.response); the derived flat
        # reconciliation view lives on record.recon.
        self.assertEqual(res.records[0].response["doc_type"], "nfse")
        self.assertEqual(res.records[0].response["valores"]["valor_liquido"], 320.0)
        self.assertNotIn("valor_total", res.records[0].response)
        self.assertEqual(res.records[0].recon["valor_total"], 320.0)
        self.assertEqual(res.records[0].artifact_role, "nfse")

    def test_danfe_total_matches_entry(self):
        pages = {
            "p1": {
                "doc_type": "danfe",
                "numero": "000006227",
                "emitente": {"nome": "AGUA MARINHA PISCINAS LTDA", "cnpj": "12.345.678/0001-99"},
                "totais": {"valor_total_nota": 2790.0},
                "data_emissao": "01/12/2025",
            }
        }
        res = build_attachment_analysis(
            "x/e_p1.png", 2790.0, "AGUA MARINHA", "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 2790.0)
        self.assertTrue(res.amount_match)

    def test_comprovante_paid_value_matches_entry(self):
        # entry 362.50; comprovante records valor 362.50 → derived valor_pago wins.
        pages = {
            "p1": {
                "doc_type": "comprovante_pagamento",
                "valor": 362.50,
                "recebedor": {"nome": "MANUT SV LTDA", "cnpj_cpf": "11.222.333/0001-44"},
                "data": "03/12/2025",
            }
        }
        res = build_attachment_analysis(
            "x/e_p1.png", 362.50, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 362.50)
        self.assertTrue(res.amount_match)

    def test_invoice_plus_payment_proof_group_reconciles(self):
        # A typed danfe (gross 1000) + a typed comprovante (paid 250) — the paid value is the
        # cash-basis amount; nf_total_for_reconciliation reads the danfe gross for group recon.
        pages = {
            "p1": {"doc_type": "danfe", "totais": {"valor_total_nota": 1000.0}, "numero": "NF-9"},
            "p2": {"doc_type": "comprovante_pagamento", "valor": 250.0},
        }
        res = build_attachment_analysis(
            "x/e_p1.png;x/e_p2.png", 250.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 250.0)
        self.assertTrue(res.amount_match)
        nf_total = nf_total_for_reconciliation((r.response for r in res.records), res.extracted_amount)
        self.assertEqual(nf_total, 1000.0)

    def test_no_false_negative_real_discrepancy_still_surfaces(self):
        # entry 100 but the danfe genuinely totals 999 → amount_match must stay False (SC-004).
        pages = {"p1": {"doc_type": "danfe", "totais": {"valor_total_nota": 999.0}}}
        res = build_attachment_analysis(
            "x/e_p1.png", 100.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 999.0)
        self.assertFalse(res.amount_match)

    def test_nf_total_for_reconciliation_over_typed_responses(self):
        # Read-back path (documents.build_documents): typed responses still yield the gross.
        responses = [
            {"doc_type": "danfe", "totais": {"valor_total_nota": 150.0}},
            {"doc_type": "comprovante_pagamento", "valor": 50.0},
        ]
        self.assertEqual(nf_total_for_reconciliation(responses), 150.0)

    def test_multi_typed_invoice_group_sums(self):
        # Two typed danfe pages with distinct numbers → _sum_distinct_invoices sums both grosses
        # (the existing multi-invoice path; EXTRACT-007 is typed-only so both pages are typed).
        pages = {
            "p1": {"doc_type": "danfe", "totais": {"valor_total_nota": 60.0}, "numero": "A"},
            "p2": {"doc_type": "danfe", "totais": {"valor_total_nota": 40.0}, "numero": "B"},
        }
        res = build_attachment_analysis(
            "x/e_p1.png;x/e_p2.png", 100.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 100.0)


if __name__ == "__main__":
    unittest.main()
