"""US2: ``build-documents`` derives documents from analyses and prunes stale ones on re-run (real D1).

``build_documents`` is GLOBAL (reads every ``attachment_analyses`` row in D1), so these assertions
target the synthetic NF keys specifically rather than total row counts (the local DB may carry other
data). The prune check uses a uniquely-synthetic number so no unrelated analysis can keep it alive.
"""

from __future__ import annotations

import unittest

from analysis.documents import build_documents, normalize_number
from common import d1, det_id

from . import _harness as h

CNPJ_A = "11222333000181"
CNPJ_B = "44555666000199"


def _doc_id(number: str, cnpj: str) -> str:
    # Mirror build_documents' key derivation (number is normalized; cnpj is 14 digits).
    return det_id("document", normalize_number(number), cnpj)


class TestBuildDocuments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = h.ids()

    def setUp(self):
        h.seed_once()  # restores E3's analysis to NF-1002

    def test_derives_synthetic_documents(self):
        build_documents("local")
        # The over-claim NF-1001 and the within NF-1002 exist with their links.
        nf1001 = _doc_id("NF-1001", CNPJ_A)
        nf1002 = _doc_id("NF-1002", CNPJ_B)
        self.assertEqual(h.count("documents", f"id = '{nf1001}'"), 1)
        self.assertEqual(h.count("documents", f"id = '{nf1002}'"), 1)
        # NF-1001 links both E1 and E2 (shared NF); NF-1002 links E3.
        self.assertGreaterEqual(h.count("document_entries", f"document_id = '{nf1001}'"), 2)
        self.assertGreaterEqual(h.count("document_entries", f"document_id = '{nf1002}'"), 1)

    def test_prune_on_key_change(self):
        build_documents("local")
        nf1002 = _doc_id("NF-1002", CNPJ_B)
        self.assertEqual(h.count("documents", f"id = '{nf1002}'"), 1)

        # Mutate E3's analysis to a uniquely-synthetic new key, then rebuild.
        e3_att = self.ids["attachments"]["E3"]
        new_number = "NF-PRUNE-7777"
        d1.execute_sql(
            f"UPDATE attachment_analyses SET document_number = '{new_number}' WHERE attachment_id = '{e3_att}';",
            target="local",
        )
        build_documents("local")

        # The old NF-1002 document is PRUNED (no analysis produces it anymore — no zombie).
        self.assertEqual(h.count("documents", f"id = '{nf1002}'"), 0)
        # The new key's document appears.
        new_doc = _doc_id(new_number, CNPJ_B)
        self.assertEqual(h.count("documents", f"id = '{new_doc}'"), 1)

    def test_idempotent(self):
        a, b = build_documents("local")
        c, d = build_documents("local")
        self.assertEqual((a, b), (c, d))


if __name__ == "__main__":
    unittest.main()
