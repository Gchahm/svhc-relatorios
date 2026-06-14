"""Tests for analysis.attachments roll-up + helpers (TEST-002 / issue #69).

The heterogeneity-aware roll-up validates an attachment's extraction against the ledger entry.
Driven through the documented `provider` seam (no D1/R2/network/VLM).
"""

import unittest

from analysis.attachments import (
    AttachmentAnalysisResult,
    PageAnalysisRecord,
    _apply_group_amount_match,
    _check_date_in_period,
    _fanout_result,
    _map_artifact_role,
    _page_label_from_path,
    _parse_brl_value,
    build_attachment_analysis,
    nf_total_for_reconciliation,
    select_work,
    summarize_results,
)

from tests._fixtures import attachment, entry, make_period


def provider_from(pages: dict):
    """Build a provider mapping page_label -> parsed dict (or None for an error page)."""

    def _provider(attachment_id, page_label):
        if page_label not in pages:
            return None, "no extraction"
        parsed = pages[page_label]
        if parsed is None:
            return None, "unreadable"
        return parsed, None

    return _provider


class ParseBrlValueTest(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(_parse_brl_value(None))

    def test_numeric_passthrough(self):
        self.assertEqual(_parse_brl_value(12.5), 12.5)
        self.assertEqual(_parse_brl_value(7), 7.0)

    def test_brl_string(self):
        self.assertEqual(_parse_brl_value("R$ 1.234,56"), 1234.56)
        self.assertEqual(_parse_brl_value("1234.56"), 1234.56)

    def test_junk(self):
        self.assertIsNone(_parse_brl_value("abc"))


class PageLabelTest(unittest.TestCase):
    def test_from_pn_suffix(self):
        self.assertEqual(_page_label_from_path("x/y_p3.png", 0), "p3")
        self.assertEqual(_page_label_from_path("x/y_P2.JPG", 0), "p2")

    def test_fallback_to_index(self):
        self.assertEqual(_page_label_from_path("x/y.png", 4), "page5")


class CheckDateInPeriodTest(unittest.TestCase):
    def test_in_period(self):
        self.assertTrue(_check_date_in_period("10/12/2025", "2025-12"))

    def test_prev_month(self):
        self.assertTrue(_check_date_in_period("28/11/2025", "2025-12"))

    def test_january_rolls_to_prev_december(self):
        self.assertTrue(_check_date_in_period("31/12/2024", "2025-01"))

    def test_out_of_period(self):
        self.assertFalse(_check_date_in_period("01/06/2024", "2025-12"))

    def test_no_date(self):
        self.assertIsNone(_check_date_in_period(None, "2025-12"))

    def test_unparseable(self):
        self.assertIsNone(_check_date_in_period("not-a-date", "2025-12"))


class MapArtifactRoleTest(unittest.TestCase):
    def test_explicit_invoice(self):
        self.assertEqual(_map_artifact_role({"papel_artefato": "invoice"}), "invoice")

    def test_alias_danfe(self):
        self.assertEqual(_map_artifact_role({"papel_artefato": "DANFE"}), "invoice")

    def test_payment_proof_override_on_valor_pago(self):
        # labeled boleto but carries a paid value → reclassified as payment_proof.
        role = _map_artifact_role({"papel_artefato": "boleto", "valor_pago": "100,00"})
        self.assertEqual(role, "payment_proof")

    def test_payment_proof_override_on_comprovante_tipo(self):
        role = _map_artifact_role({"papel_artefato": "other", "tipo_documento": "comprovante"})
        self.assertEqual(role, "payment_proof")

    def test_unknown_defaults_other(self):
        self.assertEqual(_map_artifact_role({}), "other")


class NfTotalForReconciliationTest(unittest.TestCase):
    def test_prefers_invoice_gross(self):
        # Typed responses: a danfe gross 150 wins over a comprovante paid 50.
        responses = [
            {"doc_type": "danfe", "totais": {"valor_total_nota": "150,00"}},
            {"doc_type": "comprovante_pagamento", "valor": "50,00"},
        ]
        self.assertEqual(nf_total_for_reconciliation(responses), 150.0)

    def test_falls_back(self):
        self.assertEqual(nf_total_for_reconciliation([{"doc_type": "outro"}], fallback=42.0), 42.0)

    def test_none_when_nothing(self):
        self.assertIsNone(nf_total_for_reconciliation([{"doc_type": "outro"}]))


class BuildAttachmentAnalysisTest(unittest.TestCase):
    def test_no_paths_errors(self):
        res = build_attachment_analysis("", 100.0, "ACME", "2025-12", "a1", "e1", provider_from({}))
        self.assertEqual(res.error, "no page images in file_path")

    def test_all_pages_fail_errors(self):
        res = build_attachment_analysis(
            "x/y_p1.png", 100.0, "ACME", "2025-12", "a1", "e1", provider_from({"p1": None})
        )
        self.assertEqual(res.error, "no page produced a parseable response")

    def test_invoice_gross_matches_entry(self):
        pages = {
            "p1": {
                "doc_type": "danfe",
                "totais": {"valor_total_nota": "100,00"},
                "emitente": {"cnpj": "12345678000199", "nome": "ACME COMERCIO LTDA"},
                "numero": "NF-1",
                "data_emissao": "05/12/2025",
            }
        }
        res = build_attachment_analysis(
            "x/y_p1.png", 100.0, "ACME COMERCIO", "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertIsNone(res.error)
        self.assertEqual(res.extracted_amount, 100.0)
        self.assertTrue(res.amount_match)
        self.assertTrue(res.vendor_match)
        self.assertTrue(res.date_match)
        self.assertEqual(res.document_number, "NF-1")
        self.assertEqual(res.extracted_cnpj, "12345678000199")

    def test_amount_mismatch_beyond_tolerance(self):
        pages = {"p1": {"doc_type": "danfe", "totais": {"valor_total_nota": "200,00"}}}
        res = build_attachment_analysis(
            "x/y_p1.png", 100.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertFalse(res.amount_match)

    def test_payment_proof_paid_wins_over_invoice_gross(self):
        pages = {
            "p1": {"doc_type": "danfe", "totais": {"valor_total_nota": "1000,00"}},
            "p2": {"doc_type": "comprovante_pagamento", "valor": "250,00"},
        }
        res = build_attachment_analysis(
            "x/a_p1.png;x/a_p2.png", 250.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 250.0)
        self.assertTrue(res.amount_match)

    def test_multi_invoice_sum(self):
        pages = {
            "p1": {"doc_type": "danfe", "totais": {"valor_total_nota": "60,00"}, "numero": "A"},
            "p2": {"doc_type": "danfe", "totais": {"valor_total_nota": "40,00"}, "numero": "B"},
        }
        res = build_attachment_analysis(
            "x/a_p1.png;x/a_p2.png", 100.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertEqual(res.extracted_amount, 100.0)

    def test_out_of_period_date(self):
        pages = {"p1": {"doc_type": "danfe", "totais": {"valor_total_nota": "100,00"}, "data_emissao": "01/01/2020"}}
        res = build_attachment_analysis(
            "x/a_p1.png", 100.0, None, "2025-12", "a1", "e1", provider_from(pages)
        )
        self.assertFalse(res.date_match)


class FanoutAndGroupMatchTest(unittest.TestCase):
    def _rep(self):
        rep = AttachmentAnalysisResult(attachment_id="a1", entry_id="e1", entry_amount=60.0)
        rep.extracted_amount = 100.0
        rep.issuer_name = "ACME COMERCIO LTDA"
        rep.document_number = "NF-1"
        rep.records = [
            PageAnalysisRecord(
                attachment_analysis_id="x",
                page_index=0,
                page_label="p1",
                artifact_role="invoice",
                response={"doc_type": "danfe", "totais": {"valor_total_nota": "100,00"},
                          "emitente": {"nome": "ACME COMERCIO LTDA"}, "data_emissao": "05/12/2025"},
                # The roll-up reads the derived reconciliation view (`recon`) — the typed mapper's
                # output for the typed `response` above.
                recon={"valor_total": "100,00", "nome_emitente": "ACME COMERCIO LTDA",
                       "data_emissao": "05/12/2025"},
            )
        ]
        return rep

    def test_fanout_reuses_extraction(self):
        rep = self._rep()
        sib = _fanout_result(rep, "a2", "e2", 40.0, "ACME COMERCIO", "2025-12")
        self.assertEqual(sib.attachment_id, "a2")
        self.assertEqual(sib.extracted_amount, 100.0)
        self.assertEqual(sib.document_number, "NF-1")
        self.assertEqual(len(sib.records), 1)
        self.assertTrue(sib.vendor_match)
        self.assertTrue(sib.date_match)

    def test_apply_group_amount_match_reconciled(self):
        rep = self._rep()
        # sibling sum 100 == NF gross 100 → reconciled
        outcome = _apply_group_amount_match(rep, 100.0)
        self.assertEqual(outcome, "reconciled")
        self.assertTrue(rep.amount_match)

    def test_apply_group_amount_match_over_claim(self):
        rep = self._rep()
        outcome = _apply_group_amount_match(rep, 150.0)
        self.assertEqual(outcome, "over_claim")
        self.assertFalse(rep.amount_match)


class SelectWorkTest(unittest.TestCase):
    def test_pending_filter_and_grouping(self):
        e1 = entry("e1", amount=60.0)
        e2 = entry("e2", amount=40.0)
        e3 = entry("e3", amount=999.0)
        # a1,a2 share content hash H (a group); a3 already classified → excluded
        a1 = attachment("a1", "e1", content_hash="H")
        a2 = attachment("a2", "e2", content_hash="H")
        a3 = attachment("a3", "e3", content_hash="K", classified_at=123)
        pd = make_period("2025-12", entries=[e1, e2, e3], attachments=[a1, a2, a3])
        work = select_work({"2025-12": pd})
        ids = {w.attachment["id"] for w in work}
        self.assertEqual(ids, {"a1", "a2"})  # a3 classified → out
        # both share the same group sibling sum 100
        for w in work:
            self.assertEqual(w.sibling_sum, 100.0)
            self.assertEqual(w.group_size, 2)
        # sorted by amount desc
        self.assertEqual(work[0].attachment["id"], "a1")

    def test_min_amount_and_limit(self):
        e1 = entry("e1", amount=60.0)
        e2 = entry("e2", amount=40.0)
        a1 = attachment("a1", "e1", content_hash="H1")
        a2 = attachment("a2", "e2", content_hash="H2")
        pd = make_period("2025-12", entries=[e1, e2], attachments=[a1, a2])
        work = select_work({"2025-12": pd}, min_amount=50.0)
        self.assertEqual({w.attachment["id"] for w in work}, {"a1"})
        work2 = select_work({"2025-12": pd}, limit=1)
        self.assertEqual(len(work2), 1)
        self.assertEqual(work2[0].attachment["id"], "a1")

    def test_attachment_without_file_path_skipped(self):
        e1 = entry("e1", amount=60.0)
        a1 = attachment("a1", "e1", file_path="")
        pd = make_period("2025-12", entries=[e1], attachments=[a1])
        self.assertEqual(select_work({"2025-12": pd}), [])


class SummarizeResultsTest(unittest.TestCase):
    def test_does_not_raise(self):
        ok = AttachmentAnalysisResult(attachment_id="a1", entry_id="e1", entry_amount=10.0)
        ok.amount_match = True
        ok.vendor_match = True
        bad = AttachmentAnalysisResult(attachment_id="a2", entry_id="e2", entry_amount=20.0)
        bad.amount_match = False
        bad.extracted_amount = 99.0
        bad.vendor_match = False
        bad.issuer_name = "X"
        err = AttachmentAnalysisResult(attachment_id="a3", entry_id="e3")
        err.error = "boom"
        summarize_results([ok, bad, err])  # should print, not raise


if __name__ == "__main__":
    unittest.main()
