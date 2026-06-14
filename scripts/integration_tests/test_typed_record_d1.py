"""Feature 055 / EXTRACT-004 + EXTRACT-007: typed-record persistence against real local D1.

Drives the real ``record-classification`` gate (with the EXTRACT-001 ``typed_gate`` validator) and
``apply-extractions`` over the feature-046 synthetic seed, asserting:

- a valid TYPED payload is recorded and, after roll-up, the ``attachment_analysis_records.response``
  carries the typed JSON verbatim (``doc_type``/``schema_version`` present) and the
  ``attachment_analyses`` reconciliation total = the per-type mapper value (nfse net);
- a LEGACY FLAT payload (no ``doc_type``) is REJECTED at the typed-only gate and writes no staging row
  (EXTRACT-007 / FR-008);
- a SCHEMA-INVALID typed payload is rejected at the gate and writes no staging row.

E4 is the seeded PENDING single-entry attachment (its own shared-NF representative, page ``p1``), so
recording its staging then applying rolls up exactly E4 (feature-050 staging-driven selection).
Assertions are scoped to the synthetic ids only (shared local D1 — memory: never whole-table counts).
"""

from __future__ import annotations

import json
import unittest

from analysis.extractions import apply_extractions, mark_pending
from analysis.page_classifications import record_classification
from analysis.typed_gate import validate_typed

from . import _harness as h

NFSE_TYPED = {
    "doc_type": "nfse",
    "schema_version": "1",
    "raw_text": "NFS-e EXEMPLO ...",
    "numero": "EX-0001",
    "data_emissao": "2099-01-12",
    "prestador": {"nome": "EXEMPLO Fornecedor B", "cnpj": "11.222.333/0001-44"},
    "valores": {"valor_servico": 50.0, "deducoes": 0.0, "valor_liquido": 50.0},
}

# A legacy flat payload (no doc_type) — the retired contract; used only to assert it is REJECTED.
FLAT = {
    "papel_artefato": "nfse",
    "tipo_documento": "nfse",
    "valor_total": 50.0,
    "valor_liquido": 50.0,
    "valor_pago": None,
    "cnpj_emitente": "11.222.333/0001-44",
    "nome_emitente": "EXEMPLO Fornecedor B",
    "data_emissao": "2099-01-12",
    "numero_documento": "EX-0001",
    "descricao_servico": "EXEMPLO servico",
}


def _record(att_id, payload):
    record_classification(att_id, "p1", payload, page_index=0, target="local", typed_validator=validate_typed)


class TestTypedRecordD1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()
        cls.ids = h.ids()
        cls.period = cls.ids["period"]
        cls.e4_att = cls.ids["attachments"]["E4"]
        cls.e4_an = cls.ids["analyses"]["E4"]

    @classmethod
    def tearDownClass(cls):
        # apply_extractions rewrites E4's analysis (+ its records); reset the synthetic baseline ONCE
        # here so later modules in the shared-process integration suite see a clean seed.
        h.restore()

    def setUp(self):
        # No per-test h.restore() (TEST-006 / #108, same trim as PR #106): E4 is its OWN shared-NF
        # representative (single-entry, page p1), and every test re-establishes it within the test —
        # record_classification (INSERT OR REPLACE on its staging) + apply_extractions, or mark_pending
        # (which clears its staging + stamp) before asserting no write. Every assertion reads E4's own
        # ids, so nothing leaks across tests; the baseline reset for later modules is in tearDownClass.
        pass

    def _e4_record_response(self):
        resp = h.scalar(
            f"SELECT response FROM attachment_analysis_records WHERE attachment_analysis_id = '{self.e4_an}'"
        )
        return json.loads(resp) if isinstance(resp, str) and resp else resp

    def test_typed_payload_persists_verbatim_and_reconciles(self):
        # E4 ships seeded with a flat staging row; overwrite it with a TYPED nfse payload, then apply.
        _record(self.e4_att, NFSE_TYPED)
        apply_extractions("local", [self.period])

        # The rolled-up record carries the typed JSON verbatim (survived staging -> records).
        stored = self._e4_record_response()
        self.assertEqual(stored["doc_type"], "nfse")
        self.assertEqual(stored["schema_version"], "1")
        self.assertEqual(stored["valores"]["valor_liquido"], 50.0)
        self.assertNotIn("valor_total", stored)  # raw typed shape, not the flat dict

        # The reconciliation column is the mapper-derived net; E4 entry is 50 -> amount_match true.
        amt = h.scalar(f"SELECT extracted_amount FROM attachment_analyses WHERE attachment_id = '{self.e4_att}'")
        self.assertEqual(float(amt), 50.0)
        match = h.scalar(f"SELECT amount_match FROM attachment_analyses WHERE attachment_id = '{self.e4_att}'")
        self.assertEqual(int(match), 1)
        self.assertEqual(
            h.scalar(f"SELECT extracted_cnpj FROM attachment_analyses WHERE attachment_id = '{self.e4_att}'"),
            "11.222.333/0001-44",
        )

    def test_legacy_flat_payload_rejected_no_staging_write(self):
        # EXTRACT-007 typed-only: a flat payload (no doc_type) is rejected at the gate, nothing written.
        mark_pending("local", attachment_ids=[self.e4_att])
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)

        with self.assertRaises(ValueError):
            _record(self.e4_att, FLAT)

        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)

    def test_schema_invalid_typed_rejected_no_staging_write(self):
        # Clear E4 staging so we can assert NOTHING is written by an invalid record.
        mark_pending("local", attachment_ids=[self.e4_att])
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)

        with self.assertRaises(ValueError):
            _record(self.e4_att, {"doc_type": "nfse"})  # missing required schema_version/raw_text

        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e4_att}'"), 0)


if __name__ == "__main__":
    unittest.main()
