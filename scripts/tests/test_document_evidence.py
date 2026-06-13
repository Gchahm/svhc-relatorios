"""Tests for the document→attachment(s) evidence resolver (TRIAGE-002 / issue #85).

The resolver (`resolve_document_attachment_ids`) and the one-shot wrapper (`document_evidence`) are
pure given an injected `query` callable and a stubbed `summarize_mismatches`, so they are unit-tested
here with no D1/R2/network (the project's no-mock, pure-seam convention; `unittest.mock.patch` stubs
the two seams — `analysis.documents.d1.query` and `analysis.extractions.summarize_mismatches`).
"""

import unittest
from unittest.mock import patch

from analysis.documents import (
    DocumentNotFound,
    document_evidence,
    resolve_document_attachment_ids,
)


def _fake_query(documents_rows, link_rows):
    """Build a fake ``d1.query`` that answers the resolver's two SELECTs by inspecting the SQL.

    The existence query selects ``FROM documents``; the resolution query selects
    ``FROM document_entries``. We branch on which table the SQL names.
    """

    def query(sql, *, target):
        if "FROM documents" in sql:
            return documents_rows
        if "FROM document_entries" in sql:
            return link_rows
        raise AssertionError(f"unexpected SQL: {sql}")

    return query


class ResolveTest(unittest.TestCase):
    def test_distinct_sorted_nonnull(self):
        # document_entries returns a DISTINCT non-NULL set from D1; we still assert the helper
        # sorts deterministically and passes rows straight through.
        q = _fake_query(
            documents_rows=[{"id": "doc-1"}],
            link_rows=[{"source_attachment_id": "att-b"}, {"source_attachment_id": "att-a"}],
        )
        with patch("analysis.documents.d1.query", q):
            self.assertEqual(resolve_document_attachment_ids("doc-1"), ["att-a", "att-b"])

    def test_unknown_id_raises(self):
        q = _fake_query(documents_rows=[], link_rows=[])
        with patch("analysis.documents.d1.query", q):
            with self.assertRaises(DocumentNotFound):
                resolve_document_attachment_ids("nope")

    def test_existing_doc_no_attachments_returns_empty(self):
        q = _fake_query(documents_rows=[{"id": "doc-1"}], link_rows=[])
        with patch("analysis.documents.d1.query", q):
            self.assertEqual(resolve_document_attachment_ids("doc-1"), [])

    def test_id_with_apostrophe_is_escaped(self):
        captured = {}

        def query(sql, *, target):
            captured.setdefault("sqls", []).append(sql)
            return [{"id": "o'doc"}] if "FROM documents" in sql else []

        with patch("analysis.documents.d1.query", query):
            resolve_document_attachment_ids("o'doc")
        # The apostrophe is doubled for SQL safety, never left raw.
        self.assertTrue(any("'o''doc'" in s for s in captured["sqls"]))


class DocumentEvidenceTest(unittest.TestCase):
    def test_passes_resolved_ids_and_returns_findings(self):
        sentinel_findings = [{"kind": "amount", "attachment_id": "att-a", "page_refs": []}]
        q = _fake_query(
            documents_rows=[{"id": "doc-1"}],
            link_rows=[{"source_attachment_id": "att-a"}],
        )
        with patch("analysis.documents.d1.query", q), patch(
            "analysis.extractions.summarize_mismatches", return_value=sentinel_findings
        ) as sm:
            result = document_evidence("doc-1")
        sm.assert_called_once()
        _, kwargs = sm.call_args
        self.assertEqual(kwargs["attachment_ids"], ["att-a"])
        self.assertEqual(
            result,
            {"document_id": "doc-1", "attachment_ids": ["att-a"], "findings": sentinel_findings},
        )

    def test_empty_attachment_set_does_not_call_summary(self):
        # Critical: summarize_mismatches treats a falsy attachment_ids as "no scope" (returns ALL
        # findings), so document_evidence MUST short-circuit and never call it with [] (FR-006/008).
        q = _fake_query(documents_rows=[{"id": "doc-1"}], link_rows=[])
        with patch("analysis.documents.d1.query", q), patch(
            "analysis.extractions.summarize_mismatches"
        ) as sm:
            result = document_evidence("doc-1")
        sm.assert_not_called()
        self.assertEqual(
            result, {"document_id": "doc-1", "attachment_ids": [], "findings": []}
        )

    def test_unknown_id_propagates(self):
        q = _fake_query(documents_rows=[], link_rows=[])
        with patch("analysis.documents.d1.query", q):
            with self.assertRaises(DocumentNotFound):
                document_evidence("nope")


if __name__ == "__main__":
    unittest.main()
