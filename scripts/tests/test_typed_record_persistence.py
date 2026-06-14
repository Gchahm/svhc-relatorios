"""Feature 055 / EXTRACT-004 + EXTRACT-007: persist typed transcriptions (typed-only).

Covers the pure seams:

- ``build_attachment_analysis`` stores the RAW response verbatim (typed JSON survives) and derives
  the reconciliation view (``recon``) via the EXTRACT-003 mapper.
- the shared-NF fan-out copies the response + recon to siblings unchanged.
- ``page_classifications.validate_page_fields`` typed-only gate: error / typed (schema gate); a
  legacy flat payload (no ``doc_type``) is REJECTED (EXTRACT-007 / FR-008).

No D1, no network, no ``tools/`` heavy validator (a fake typed validator is injected where the schema
gate behavior is the thing under test; the real gate is exercised in the integration suite).
"""

import unittest

from analysis.attachments import _fanout_result, build_attachment_analysis
from analysis.page_classifications import validate_page_fields
from analysis.typed_gate import validate_typed

NFSE_TYPED = {
    "doc_type": "nfse",
    "schema_version": "1",
    "raw_text": "NFS-e ...",
    "numero": "0000123",
    "data_emissao": "05/12/2025",
    "prestador": {"nome": "MANUT SV LTDA", "cnpj": "11.222.333/0001-44"},
    "valores": {"valor_servico": 320.0, "deducoes": 0.0, "valor_liquido": 320.0},
}

DANFE_TYPED = {
    "doc_type": "danfe",
    "schema_version": "1",
    "raw_text": "DANFE ...",
    "numero": "000006227",
    "data_emissao": "01/12/2025",
    "emitente": {"nome": "AGUA MARINHA PISCINAS LTDA", "cnpj": "12.345.678/0001-99"},
    "totais": {"valor_total_nota": 2790.0},
}

# A legacy flat payload (no doc_type) — the retired contract; used only to assert it is REJECTED.
FLAT = {
    "papel_artefato": "nfse",
    "tipo_documento": "nfse",
    "valor_total": 320.0,
    "valor_liquido": 320.0,
    "valor_pago": None,
    "cnpj_emitente": "11.222.333/0001-44",
    "nome_emitente": "MANUT SV LTDA",
    "data_emissao": "05/12/2025",
    "numero_documento": "0000123",
    "descricao_servico": "servico",
}


def provider_from(pages: dict):
    def _provider(attachment_id, page_label):
        if page_label not in pages:
            return None, "no extraction"
        return pages[page_label], None

    return _provider


# --------------------------------------------------------------------------- #
# US1 — typed persists verbatim + reconciles via the mapper
# --------------------------------------------------------------------------- #
class TypedPersistenceTest(unittest.TestCase):
    def test_typed_nfse_stored_verbatim_recon_derives_net(self):
        res = build_attachment_analysis(
            "x/e_p1.png", 320.0, "MANUT SV", "2025-12", "a1", "e1", provider_from({"p1": NFSE_TYPED})
        )
        rec = res.records[0]
        # response is the RAW typed JSON (carries doc_type/schema_version → survives to D1).
        self.assertEqual(rec.response, NFSE_TYPED)
        self.assertEqual(rec.response["doc_type"], "nfse")
        self.assertEqual(rec.response["schema_version"], "1")
        # recon is the derived flat reconciliation view; nfse reconciles on net.
        self.assertEqual(rec.recon["valor_total"], 320.0)
        self.assertEqual(rec.recon["cnpj_emitente"], "11.222.333/0001-44")
        self.assertEqual(rec.artifact_role, "nfse")
        self.assertEqual(res.extracted_amount, 320.0)
        self.assertTrue(res.amount_match)

    def test_typed_danfe_recon_uses_totais_and_emitente(self):
        res = build_attachment_analysis(
            "x/e_p1.png", 2790.0, "AGUA MARINHA", "2025-12", "a1", "e1", provider_from({"p1": DANFE_TYPED})
        )
        self.assertEqual(res.records[0].response["doc_type"], "danfe")
        self.assertEqual(res.extracted_amount, 2790.0)
        self.assertEqual(res.extracted_cnpj, "12.345.678/0001-99")
        self.assertEqual(res.issuer_name, "AGUA MARINHA PISCINAS LTDA")
        self.assertTrue(res.amount_match)

    def test_fanout_copies_response_and_recon_unchanged(self):
        rep = build_attachment_analysis(
            "x/e_p1.png", 2790.0, "AGUA MARINHA", "2025-12", "a1", "e1", provider_from({"p1": DANFE_TYPED})
        )
        sib = _fanout_result(rep, "a2", "e2", 2790.0, "AGUA MARINHA", "2025-12")
        self.assertEqual(sib.records[0].response, rep.records[0].response)
        self.assertEqual(sib.records[0].recon, rep.records[0].recon)
        self.assertEqual(sib.records[0].response["doc_type"], "danfe")


# --------------------------------------------------------------------------- #
# US3 — the typed-only validation gate (EXTRACT-007 / FR-008)
# --------------------------------------------------------------------------- #
class ValidateTypedOnlyGateTest(unittest.TestCase):
    def _fake_validator(self, payload, doc_type):
        # Minimal stand-in for the EXTRACT-001 gate: require a 'valores'/'totais' block per type.
        if doc_type == "nfse" and "valores" not in payload:
            return ["$: missing required field 'valores'"]
        if "unexpected" in payload:
            return ["$: unexpected key 'unexpected'"]
        return []

    def test_valid_typed_accepted(self):
        self.assertIsNone(validate_page_fields(NFSE_TYPED, typed_validator=self._fake_validator))

    def test_typed_missing_required_rejected(self):
        err = validate_page_fields({"doc_type": "nfse"}, typed_validator=self._fake_validator)
        self.assertIsNotNone(err)
        self.assertIn("EXTRACT-001 schema", err)
        self.assertIn("valores", err)

    def test_typed_unexpected_key_rejected(self):
        err = validate_page_fields(
            {"doc_type": "nfse", "valores": {}, "unexpected": 1}, typed_validator=self._fake_validator
        )
        self.assertIsNotNone(err)
        self.assertIn("unexpected", err)

    def test_typed_without_validator_accepted_structurally(self):
        # No injected validator: a typed payload is accepted (the CLI always injects the real gate).
        self.assertIsNone(validate_page_fields({"doc_type": "nfse"}))

    def test_error_result_still_accepted(self):
        self.assertIsNone(validate_page_fields({"error": "page illegible"}, typed_validator=self._fake_validator))

    def test_flat_rejected(self):
        # The retired flat contract (a dict WITHOUT doc_type) is rejected — typed-only (FR-008).
        err = validate_page_fields(FLAT, typed_validator=self._fake_validator)
        self.assertIsNotNone(err)
        self.assertIn("doc_type", err)

    def test_non_dict_rejected(self):
        self.assertIsNotNone(validate_page_fields([1, 2], typed_validator=self._fake_validator))


class RealTypedGateTest(unittest.TestCase):
    """Exercise the real EXTRACT-001 gate (typed_gate -> doc_transcribe). Stdlib-only, no network."""

    def test_valid_typed_nfse_conforms(self):
        self.assertEqual(validate_typed(NFSE_TYPED, "nfse"), [])

    def test_typed_missing_envelope_field_has_errors(self):
        errors = validate_typed({"doc_type": "nfse"}, "nfse")
        self.assertTrue(errors)
        self.assertTrue(any("schema_version" in e or "raw_text" in e for e in errors))

    def test_unknown_doc_type_falls_back_to_outro_schema(self):
        # An unknown type resolves to the outro fallback schema and never raises on the type alone.
        errors = validate_typed({"doc_type": "totally-unknown", "schema_version": "1", "raw_text": "x"}, "totally-unknown")
        self.assertIsInstance(errors, list)

    def test_full_gate_through_validate_page_fields(self):
        self.assertIsNone(validate_page_fields(NFSE_TYPED, typed_validator=validate_typed))
        self.assertIsNotNone(validate_page_fields({"doc_type": "nfse"}, typed_validator=validate_typed))


if __name__ == "__main__":
    unittest.main()
