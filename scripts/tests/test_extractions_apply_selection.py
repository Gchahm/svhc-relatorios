"""Unit tests for the feature-050 staging-driven apply selection (issue #84).

`staged_attachment_ids` is the pure predicate that decides which shared-NF groups
`apply_extractions` rolls up: a group is processed iff its REPRESENTATIVE attachment id is in
the set of attachment ids that have at least one `page_classifications` staging row. These tests
exercise the predicate directly (no D1); the destructive-bystander + targeted-reclassify
end-to-end behaviour against real D1 lives in `scripts/integration_tests/test_apply_staging_driven_d1.py`.
"""

import unittest

from analysis.extractions import staged_attachment_ids


class StagedAttachmentIdsTest(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(staged_attachment_ids([]), set())
        self.assertEqual(staged_attachment_ids(None), set())

    def test_collects_distinct_ids(self):
        rows = [
            {"attachment_id": "a1", "page_label": "p1"},
            {"attachment_id": "a1", "page_label": "p2"},
            {"attachment_id": "a2", "page_label": "p1"},
        ]
        self.assertEqual(staged_attachment_ids(rows), {"a1", "a2"})

    def test_error_row_counts_as_staged(self):
        # An {"error": ...} recorded result still means the page was visited/recorded — staged.
        rows = [{"attachment_id": "a1", "page_label": "p1", "response": None, "error": "unreadable"}]
        self.assertEqual(staged_attachment_ids(rows), {"a1"})

    def test_rows_without_attachment_id_ignored(self):
        rows = [{"page_label": "p1"}, {"attachment_id": "", "page_label": "p2"}, {"attachment_id": "a3"}]
        self.assertEqual(staged_attachment_ids(rows), {"a3"})

    def test_selection_semantics(self):
        # The way apply_extractions uses it: representative present -> process; absent -> skip.
        staged = staged_attachment_ids([{"attachment_id": "rep_with_staging", "page_label": "p1"}])
        # A group whose representative has staging is selected.
        self.assertIn("rep_with_staging", staged)
        # A group whose representative has NO staging is skipped — even if a (hypothetical) sibling
        # id were present, the check is keyed on the representative only (FR-003).
        self.assertNotIn("rep_without_staging", staged)


if __name__ == "__main__":
    unittest.main()
