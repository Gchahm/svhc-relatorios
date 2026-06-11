"""Tests for the authoritative documents writeback (feature 025 / issue #36).

Drives ``analysis.documents.build_documents`` with the analysis loader stubbed and the D1 seam
intercepted, so the test exercises ONLY the prune + upsert sequencing. Asserts: a re-classification
prunes the stale document/link and inserts the new ones in ONE batch; an empty desired state removes
all rows (prune-only batch); the prune predicate lists the DESIRED ids; a true no-op issues no write;
and a non-zero pruned count is logged.

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import logging
import unittest

from analysis import documents


def _analysis(an_id, attachment_id, entry_id, number, cnpj, amount=100.0):
    """A rolled-up attachment analysis shaped like _load_analyses_global returns."""
    return {
        "id": an_id,
        "attachment_id": attachment_id,
        "entry_id": entry_id,
        "document_number": number,
        "extracted_cnpj": cnpj,
        "extracted_amount": amount,
        "issuer_name": "ACME",
        "document_type": "NF",
        "analysis_records": [],
    }


class _Patches:
    """Stub the global loader + D1 reads/writes; record the batch SQL build_documents executes."""

    def __init__(self, analyses, existing_docs=(), existing_links=()):
        self.analyses = analyses
        self.existing_docs = list(existing_docs)
        self.existing_links = list(existing_links)
        self.executed = []  # list of executed batch SQL strings
        self._orig = {}

    def __enter__(self):
        def fake_query(sql, *, target):
            if "FROM documents" in sql:
                return [{"id": i} for i in self.existing_docs]
            if "FROM document_entries" in sql:
                return [{"id": i} for i in self.existing_links]
            return []

        def fake_execute(sql, *, target):
            self.executed.append(sql)

        self._patch(documents, "_load_analyses_global", lambda target: list(self.analyses))
        # _analysis_total reads nf_total_for_reconciliation off the (empty) records; stub to a number.
        self._patch(documents, "_analysis_total", lambda a: a.get("extracted_amount"))
        self._patch(documents.d1, "query", fake_query)
        self._patch(documents.d1, "execute_sql", fake_execute)
        return self

    def _patch(self, obj, name, value):
        self._orig[(obj, name)] = getattr(obj, name)
        setattr(obj, name, value)

    def __exit__(self, *exc):
        for (obj, name), value in self._orig.items():
            setattr(obj, name, value)
        return False

    @property
    def batch(self):
        return self.executed[0] if self.executed else ""


class DocumentPruneTest(unittest.TestCase):
    def _ids(self, number, cnpj, entry_id):
        from common import det_id

        doc_id = det_id("document", documents.normalize_number(number), documents.normalize_cnpj(cnpj))
        link_id = det_id("document_entry", doc_id, entry_id)
        return doc_id, link_id

    def test_reclassification_prunes_stale_and_inserts_new_in_one_batch(self):
        # Analyses now produce the NEW key only; the OLD doc/link are persisted (stale).
        new_doc, new_link = self._ids("456", "11222333000181", "E1")
        old_doc, old_link = self._ids("123", "11222333000181", "E1")
        with _Patches(
            [_analysis("an1", "A1", "E1", "456", "11222333000181")],
            existing_docs=[old_doc, new_doc],
            existing_links=[old_link, new_link],
        ) as p:
            documents.build_documents(target="local")
        # Exactly one execute_sql call (one atomic batch).
        self.assertEqual(len(p.executed), 1)
        batch = p.batch
        # Prune both tables with NOT IN (<desired ids>), then INSERT OR REPLACE the desired rows.
        self.assertIn("DELETE FROM document_entries WHERE id NOT IN (", batch)
        self.assertIn("DELETE FROM documents WHERE id NOT IN (", batch)
        self.assertIn('INSERT OR REPLACE INTO "documents"', batch)
        self.assertIn('INSERT OR REPLACE INTO "document_entries"', batch)
        # The DELETE predicate lists the DESIRED (new) ids — so the old stale ids are pruned.
        self.assertIn(new_doc, batch)
        self.assertIn(new_link, batch)

    def test_empty_desired_state_removes_all_rows_prune_only(self):
        # No confident analysis (missing CNPJ) → desired state empty → unconditional DELETE FROM both.
        with _Patches(
            [_analysis("an1", "A1", "E1", "123", None)],  # no CNPJ → not confident
            existing_docs=["d_old"],
            existing_links=["l_old"],
        ) as p:
            documents.build_documents(target="local")
        self.assertEqual(len(p.executed), 1)
        batch = p.batch
        self.assertIn("DELETE FROM document_entries;", batch)
        self.assertIn("DELETE FROM documents;", batch)
        self.assertNotIn("INSERT OR REPLACE", batch)

    def test_prune_predicate_lists_desired_ids_not_stale(self):
        new_doc, new_link = self._ids("456", "11222333000181", "E1")
        with _Patches(
            [_analysis("an1", "A1", "E1", "456", "11222333000181")],
            existing_docs=["zombie_doc", new_doc],
            existing_links=["zombie_link", new_link],
        ) as p:
            documents.build_documents(target="local")
        batch = p.batch
        # The stale ids must NOT appear inside the NOT IN predicate (we list the desired set).
        self.assertNotIn("zombie_doc", batch)
        self.assertNotIn("zombie_link", batch)

    def test_true_noop_issues_no_write(self):
        # Nothing persisted, nothing confident → no prune, no upsert → no execute_sql.
        with _Patches([], existing_docs=[], existing_links=[]) as p:
            documents.build_documents(target="local")
        self.assertEqual(p.executed, [])

    def test_pruned_count_is_logged(self):
        new_doc, new_link = self._ids("456", "11222333000181", "E1")
        with _Patches(
            [_analysis("an1", "A1", "E1", "456", "11222333000181")],
            existing_docs=["zombie_doc", new_doc],
            existing_links=["zombie_link", new_link],
        ) as p:
            with self.assertLogs("analysis.documents", level="INFO") as cm:
                documents.build_documents(target="local")
        log = "\n".join(cm.output)
        self.assertIn("pruned 1 document(s), 1 link(s)", log)


if __name__ == "__main__":
    unittest.main()
