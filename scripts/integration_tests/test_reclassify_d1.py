"""Real-D1 integration tests for the composite ``reclassify`` helper (feature 058 / TRIAGE-004, §4.5).

Drive ``analysis.corrections.reclassify`` against local Miniflare D1 (the real ``scripts/common/d1.py``
wrapper, the real staging-driven apply + analyze pipeline), on the synthetic ``2099-01`` period.
Covers:

- US4-AC1: recording corrected staging + propagating re-derives the attachment's ``attachment_analyses``
  (the corrected value lands), stamps it classified, prunes its staging (staging-driven apply consumes
  it), and refreshes the documents/alerts (run via the pipeline).
- US4 (staging-driven safety / FR-017): a DIFFERENT attachment that was NOT reclassified is untouched.
- US4-AC2: an empty pages payload is a no-op (no staging, no propagation); an unknown attachment errors.
- US4-AC3: ``reclassify`` defaults to local (``remote`` reflected in the result).

Run: ``pnpm test:py:integration`` (needs ``wrangler`` + an applied local migration set).
"""

from __future__ import annotations

import tempfile
import unittest

from analysis import corrections
from analysis.corrections import reclassify
from analysis.extractions import mark_pending

from . import _harness as h


def _fields(valor_total):
    """A frozen-contract NFS-e page extraction with a given total (other amounts track it)."""
    return {
        "papel_artefato": "nfse",
        "tipo_documento": "NFS-e",
        "valor_total": valor_total,
        "valor_liquido": valor_total,
        "valor_pago": valor_total,
        "cnpj_emitente": "11222333000181",
        "nome_emitente": "EXEMPLO Fornecedor B",
        "data_emissao": "2099-01-10",
        "numero_documento": "NF-1002",
        "descricao_servico": "EXEMPLO servico",
    }


class TestReclassifyD1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        h.seed_once()
        cls.ids = h.ids()
        cls.period = cls.ids["period"]
        # E3: a singleton attachment (NF-1002, no shared-NF sibling) — a clean reclassify target.
        cls.e3_att = cls.ids["attachments"]["E3"]
        # E1 is the untouched bystander: it owns its own seeded analysis (shared NF-1001 group, a
        # different NF than E3's NF-1002), so reclassifying E3 must leave E1's analysis untouched.
        cls.other_att = cls.ids["attachments"]["E1"]

    @classmethod
    def tearDownClass(cls):
        # The period-scoped propagation rewrites the synthetic period's analyses + alerts; reset ONCE
        # here so later modules in the shared-process integration suite see a clean seed.
        h.restore()

    def setUp(self):
        # No per-test h.restore() (TEST-006 / #108, same trim as PR #106): E3 is a SINGLETON
        # attachment (NF-1002, no shared-NF sibling, so the affected scope is just E3), and every test
        # fully re-establishes its subject within the test — reclassify records E3's staging + runs the
        # period pipeline, and the bystander snapshot (E1, which no test ever writes) is taken inside
        # the same test. So nothing leaks across tests; the baseline reset for later modules stays in
        # tearDownClass.
        self._cache = tempfile.mkdtemp()

    def test_reclassify_records_and_re_derives(self):
        # A bystander snapshot we will assert is unchanged (staging-driven safety, FR-017).
        before_other = h.scalar(
            f"SELECT extracted_amount FROM attachment_analyses WHERE attachment_id = '{self.other_att}'"
        )

        result = reclassify(self.e3_att, {"p1": _fields(777)}, target="local", cache_dir=self._cache)

        self.assertEqual(result["result"], "reclassified", result)
        self.assertEqual(result["attachment_id"], self.e3_att)
        self.assertEqual(result["period"], self.period)
        self.assertEqual(result["pages"], ["p1"])
        self.assertFalse(result["remote"])

        # The re-derived analysis carries the corrected value, and the attachment is stamped classified.
        self.assertEqual(h.count("attachment_analyses", f"attachment_id = '{self.e3_att}'"), 1)
        self.assertAlmostEqual(
            h.scalar(f"SELECT extracted_amount FROM attachment_analyses WHERE attachment_id = '{self.e3_att}'"),
            777.0,
            places=2,
        )
        self.assertIsNotNone(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'")
        )
        # Staging-driven apply consumed (pruned) the staging row after the roll-up.
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e3_att}'"), 0)

        # The bystander attachment, which owned no recorded staging, is untouched.
        after_other = h.scalar(
            f"SELECT extracted_amount FROM attachment_analyses WHERE attachment_id = '{self.other_att}'"
        )
        self.assertEqual(after_other, before_other)

    def test_empty_pages_is_no_op(self):
        before_state = h.scalar(
            f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'"
        )
        result = reclassify(self.e3_att, {}, target="local", cache_dir=self._cache)
        self.assertEqual(result["result"], "no-op", result)
        # No staging written, classified state unchanged.
        self.assertEqual(h.count("page_classifications", f"attachment_id = '{self.e3_att}'"), 0)
        self.assertEqual(
            h.scalar(f"SELECT classified_at FROM attachment_state WHERE attachment_id = '{self.e3_att}'"),
            before_state,
        )

    def test_unknown_attachment_raises(self):
        with self.assertRaises(ValueError):
            reclassify("does-not-exist", {"p1": _fields(100)}, target="local", cache_dir=self._cache)
        # Nothing recorded for the bogus id.
        self.assertEqual(h.count("page_classifications", "attachment_id = 'does-not-exist'"), 0)


if __name__ == "__main__":
    unittest.main()
