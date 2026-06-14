"""Tests for analysis.type_mappers — deterministic per-type mappers (feature 053 / EXTRACT-003).

Pure unit tests over the typed transcription JSON → reconciliation fields function. Covers the
documented 757dedb0 case (yields 320, not 800), every per-type mapper, the dispatch (typed / alias /
unknown / None), the legacy flat pass-through (no regression), and the
`rollup-amount-false-positives.md` Problem A record-selection cases.
"""

import unittest

from analysis.type_mappers import (
    RECONCILIATION_KEYS,
    _canonical_doc_type,
    to_reconciliation_fields,
)


class CanonicalDocTypeTest(unittest.TestCase):
    def test_exact_keys(self):
        for t in ("danfe", "nfse", "boleto", "recibo", "comprovante_pagamento", "outro"):
            self.assertEqual(_canonical_doc_type(t), t)

    def test_aliases(self):
        self.assertEqual(_canonical_doc_type("NFS-e"), "nfse")
        self.assertEqual(_canonical_doc_type("nota fiscal"), "danfe")
        self.assertEqual(_canonical_doc_type("NF-e"), "danfe")
        self.assertEqual(_canonical_doc_type("comprovante"), "comprovante_pagamento")
        self.assertEqual(_canonical_doc_type("PIX"), "comprovante_pagamento")

    def test_unknown_and_none(self):
        self.assertEqual(_canonical_doc_type("guia-municipal"), "outro")
        self.assertEqual(_canonical_doc_type(None), "outro")
        self.assertEqual(_canonical_doc_type(123), "outro")
        self.assertEqual(_canonical_doc_type(""), "outro")


class NfseMapperTest(unittest.TestCase):
    """The canonical 757dedb0 fix: yields the page total 320, never the model's old 800."""

    def _nfse_757dedb0(self):
        return {
            "doc_type": "nfse",
            "numero": "0000123",
            "data_emissao": "05/12/2025",
            "prestador": {"nome": "MANUTENCAO PREDIAL SV LTDA", "cnpj": "11.222.333/0001-44"},
            "tomador": {"nome": "SAO VICENTE HOME CLUB", "cnpj_cpf": "98.765.432/0001-00"},
            "discriminacao_servico": "Servico de manutencao de portao eletronico",
            "valores": {"valor_servico": 320.0, "deducoes": 0.0, "valor_liquido": 320.0},
        }

    def test_total_is_liquido_320_not_800(self):
        out = to_reconciliation_fields(self._nfse_757dedb0())
        self.assertEqual(out["valor_total"], 320.0)
        self.assertEqual(out["valor_liquido"], 320.0)
        self.assertNotEqual(out["valor_total"], 800.0)

    def test_issuer_and_number_from_prestador(self):
        out = to_reconciliation_fields(self._nfse_757dedb0())
        self.assertEqual(out["cnpj_emitente"], "11.222.333/0001-44")
        self.assertEqual(out["nome_emitente"], "MANUTENCAO PREDIAL SV LTDA")
        self.assertEqual(out["numero_documento"], "0000123")
        self.assertEqual(out["papel_artefato"], "nfse")
        self.assertEqual(out["tipo_documento"], "nfse")
        self.assertEqual(out["descricao_servico"], "Servico de manutencao de portao eletronico")

    def test_liquido_distinct_from_servico_when_retencoes(self):
        # When deductions/retentions exist, the líquido (settled amount) is the reconciliation target.
        nfse = {"doc_type": "nfse", "valores": {"valor_servico": 1000.0, "valor_liquido": 950.0}}
        out = to_reconciliation_fields(nfse)
        self.assertEqual(out["valor_total"], 950.0)


class DanfeMapperTest(unittest.TestCase):
    def test_total_from_totais_valor_total_nota(self):
        danfe = {
            "doc_type": "danfe",
            "numero": "000006227",
            "data_emissao": "01/12/2025",
            "emitente": {"nome": "AGUA MARINHA PISCINAS LTDA", "cnpj": "12.345.678/0001-99"},
            "itens": [{"descricao": "CLORO GRANULADO 10KG"}],
            "totais": {"valor_produtos": 2790.0, "valor_total_nota": 2790.0},
        }
        out = to_reconciliation_fields(danfe)
        self.assertEqual(out["valor_total"], 2790.0)
        self.assertEqual(out["cnpj_emitente"], "12.345.678/0001-99")
        self.assertEqual(out["nome_emitente"], "AGUA MARINHA PISCINAS LTDA")
        self.assertEqual(out["numero_documento"], "000006227")
        self.assertEqual(out["descricao_servico"], "CLORO GRANULADO 10KG")
        self.assertEqual(out["papel_artefato"], "invoice")

    def test_missing_totais_yields_none(self):
        out = to_reconciliation_fields({"doc_type": "danfe", "numero": "1"})
        self.assertIsNone(out["valor_total"])
        self.assertEqual(out["numero_documento"], "1")


class BoletoMapperTest(unittest.TestCase):
    def test_total_from_valor_documento(self):
        boleto = {
            "doc_type": "boleto",
            "beneficiario": {"nome": "MANUT SV LTDA", "cnpj_cpf": "11.222.333/0001-44"},
            "valor_documento": 320.0,
            "data_documento": "05/12/2025",
            "numero_documento": "000123",
        }
        out = to_reconciliation_fields(boleto)
        self.assertEqual(out["valor_total"], 320.0)
        self.assertEqual(out["cnpj_emitente"], "11.222.333/0001-44")
        self.assertEqual(out["numero_documento"], "000123")
        self.assertEqual(out["papel_artefato"], "boleto")
        self.assertEqual(out["data_emissao"], "05/12/2025")


class ReciboMapperTest(unittest.TestCase):
    def test_total_from_valor(self):
        recibo = {
            "doc_type": "recibo",
            "numero": "045",
            "data": "02/12/2025",
            "recebedor": {"nome": "JOSE DA SILVA JARDINAGEM ME", "cnpj_cpf": "22.333.444/0001-55"},
            "valor": 500.0,
            "referente_a": "servico de jardinagem",
        }
        out = to_reconciliation_fields(recibo)
        self.assertEqual(out["valor_total"], 500.0)
        self.assertEqual(out["cnpj_emitente"], "22.333.444/0001-55")
        self.assertEqual(out["nome_emitente"], "JOSE DA SILVA JARDINAGEM ME")
        self.assertEqual(out["numero_documento"], "045")
        self.assertEqual(out["descricao_servico"], "servico de jardinagem")
        self.assertEqual(out["papel_artefato"], "payment_proof")


class ComprovanteMapperTest(unittest.TestCase):
    def test_valor_pago_from_valor(self):
        comp = {
            "doc_type": "comprovante_pagamento",
            "tipo": "pix",
            "data": "03/12/2025 09:15:42",
            "recebedor": {"nome": "MANUT SV LTDA", "cnpj_cpf": "11.222.333/0001-44"},
            "valor": 320.0,
            "identificador": "E12345678",
        }
        out = to_reconciliation_fields(comp)
        self.assertEqual(out["valor_pago"], 320.0)
        self.assertIsNone(out["valor_total"])
        self.assertEqual(out["cnpj_emitente"], "11.222.333/0001-44")
        self.assertEqual(out["numero_documento"], "E12345678")
        self.assertEqual(out["papel_artefato"], "payment_proof")
        self.assertEqual(out["tipo_documento"], "comprovante")

    def test_comprovante_alias_resolves(self):
        out = to_reconciliation_fields({"doc_type": "comprovante", "valor": 50.0})
        self.assertEqual(out["valor_pago"], 50.0)


class OutroMapperTest(unittest.TestCase):
    def test_single_identified_amount(self):
        outro = {
            "doc_type": "outro",
            "descricao": "Guia de recolhimento de taxa municipal",
            "valores_identificados": [{"rotulo": "Valor Principal", "valor": 1200.0}],
        }
        out = to_reconciliation_fields(outro)
        self.assertEqual(out["valor_total"], 1200.0)
        self.assertEqual(out["descricao_servico"], "Guia de recolhimento de taxa municipal")
        self.assertEqual(out["papel_artefato"], "other")

    def test_no_amounts_yields_none(self):
        out = to_reconciliation_fields({"doc_type": "outro", "descricao": "x"})
        self.assertIsNone(out["valor_total"])

    def test_unknown_type_routes_to_outro(self):
        out = to_reconciliation_fields({"doc_type": "guia-municipal", "valores_identificados": [{"valor": 9.0}]})
        self.assertEqual(out["tipo_documento"], "outro")
        self.assertEqual(out["valor_total"], 9.0)


class AmountFormParityTest(unittest.TestCase):
    def test_currency_string_passes_through_unparsed(self):
        # The mapper emits the value as-is; downstream _parse_brl_value normalizes it. We assert the
        # mapper does not corrupt a currency string and that numeric/string forms both round-trip.
        out_str = to_reconciliation_fields({"doc_type": "boleto", "valor_documento": "R$ 320,00"})
        self.assertEqual(out_str["valor_total"], "R$ 320,00")
        out_num = to_reconciliation_fields({"doc_type": "boleto", "valor_documento": 320.0})
        self.assertEqual(out_num["valor_total"], 320.0)

    def test_spurious_zero_emitted_as_zero(self):
        # A 0.0 is emitted verbatim; the roll-up's `> 0` guard treats it as missing (preserved rule).
        out = to_reconciliation_fields({"doc_type": "comprovante_pagamento", "valor": 0.0})
        self.assertEqual(out["valor_pago"], 0.0)


class DispatchEdgeTest(unittest.TestCase):
    def test_none_input(self):
        out = to_reconciliation_fields(None)
        self.assertEqual(set(out), set(RECONCILIATION_KEYS))
        self.assertTrue(all(v is None for v in out.values()))

    def test_non_dict_input(self):
        self.assertTrue(all(v is None for v in to_reconciliation_fields("oops").values()))
        self.assertTrue(all(v is None for v in to_reconciliation_fields([1, 2]).values()))

    def test_malformed_nested_does_not_raise(self):
        # prestador is a string, not a dict — must degrade to None, not raise.
        out = to_reconciliation_fields({"doc_type": "nfse", "prestador": "MANUT", "valores": None})
        self.assertIsNone(out["cnpj_emitente"])
        self.assertIsNone(out["valor_total"])

    def test_output_always_has_all_keys(self):
        for resp in (
            {"doc_type": "danfe"},
            {"doc_type": "nfse"},
            {"doc_type": "boleto"},
            {"doc_type": "recibo"},
            {"doc_type": "comprovante_pagamento"},
            {"doc_type": "outro"},
            {},
            None,
        ):
            self.assertEqual(set(to_reconciliation_fields(resp)), set(RECONCILIATION_KEYS))


class TypedOnlyReadFallbackTest(unittest.TestCase):
    """EXTRACT-007: the legacy flat pass-through is removed; a dict without a recognized doc_type is a
    defensive read-path fallback (→ outro), never a supported contract (the write-time gate rejects it).
    """

    def test_dict_without_doc_type_falls_back_to_outro(self):
        # No doc_type → outro mapper: papel 'other', and only outro's best-effort fields populate.
        out = to_reconciliation_fields({"papel_artefato": "invoice", "valor_total": 100.0})
        self.assertEqual(set(out), set(RECONCILIATION_KEYS))
        self.assertEqual(out["papel_artefato"], "other")
        self.assertEqual(out["tipo_documento"], "outro")

    def test_never_raises_on_odd_input(self):
        for resp in ({}, {"x": 1}, {"doc_type": None}, {"doc_type": "no-such-type"}):
            self.assertEqual(set(to_reconciliation_fields(resp)), set(RECONCILIATION_KEYS))


class RollupFalsePositiveCasesTest(unittest.TestCase):
    """`rollup-amount-false-positives.md` §Problem A: the matching value is derived, not guessed.

    These cases used to fire false `amount_match` mismatches because the roll-up picked the first
    record of a role. With the typed mapper the reconciliation total comes deterministically from
    the type's total field, so it matches the entry.
    """

    def test_nfse_320_matches_entry(self):
        # entry 320; nfse líquido 320 → reconciliation total 320 (the 757dedb0 family).
        out = to_reconciliation_fields({"doc_type": "nfse", "valores": {"valor_liquido": 320.0}})
        self.assertEqual(out["valor_total"], 320.0)

    def test_comprovante_paid_value_matches_entry(self):
        # entry 362.50; the comprovante records valor 362.50 → derived valor_pago 362.50.
        out = to_reconciliation_fields({"doc_type": "comprovante_pagamento", "valor": 362.50})
        self.assertEqual(out["valor_pago"], 362.50)

    def test_no_false_negative_real_discrepancy_preserved(self):
        # A document that genuinely carries a total != entry still surfaces the true value
        # (the mapper does not hide a discrepancy — SC-004).
        out = to_reconciliation_fields({"doc_type": "danfe", "totais": {"valor_total_nota": 999.0}})
        self.assertEqual(out["valor_total"], 999.0)


if __name__ == "__main__":
    unittest.main()
