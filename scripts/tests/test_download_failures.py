"""Tests for the pure partial-download-failure helpers (IMP-004 / issue #41).

The scraper runner delegates three deterministic decisions to ``scraper.download_failures``:
which attempted attachments still have no pages, how the run-note line is formatted, and the run
status precedence. These are stdlib-only (no ``playwright``) and unit-tested here.

Covers (per the spec's user stories):
- US1 — run-level signal: failed-id selection (FR-001/002/008), the queryable note (FR-002/004),
  and the ``partial`` status precedence (FR-003/005).

Run: ``python -m unittest discover -s scripts/tests -t scripts``
"""

import unittest

from scraper.download_failures import (
    failed_attachment_ids,
    format_failure_note,
    resolve_status,
)


def _att(aid, *, file_path=None):
    return {"id": aid, "file_path": file_path}


class FailedAttachmentIdsTest(unittest.TestCase):
    def test_attempted_and_no_pages_counts(self):
        rows = [_att("a1"), _att("a2", file_path="2025-12/a2_p1.png")]
        self.assertEqual(failed_attachment_ids(rows, {"a1", "a2"}), ["a1"])

    def test_not_attempted_is_never_counted(self):
        # a1 has no pages but was NOT attempted this run (e.g. download disabled) → not a failure.
        rows = [_att("a1")]
        self.assertEqual(failed_attachment_ids(rows, set()), [])

    def test_preserved_pages_not_counted(self):
        # Attempted but the preserve merge restored prior pages → file_path present → no loss.
        rows = [_att("a1", file_path="2025-12/a1_p1.png")]
        self.assertEqual(failed_attachment_ids(rows, {"a1"}), [])

    def test_empty_string_file_path_is_missing(self):
        rows = [_att("a1", file_path="")]
        self.assertEqual(failed_attachment_ids(rows, {"a1"}), ["a1"])

    def test_order_follows_input(self):
        rows = [_att("a3"), _att("a1"), _att("a2")]
        self.assertEqual(failed_attachment_ids(rows, {"a1", "a2", "a3"}), ["a3", "a1", "a2"])

    def test_all_failed(self):
        rows = [_att("a1"), _att("a2")]
        self.assertEqual(failed_attachment_ids(rows, {"a1", "a2"}), ["a1", "a2"])


class FormatFailureNoteTest(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(format_failure_note("2025-12", []))

    def test_singular(self):
        self.assertEqual(
            format_failure_note("2025-12", ["a1"]),
            "1 attachment failed to download in 2025-12: a1",
        )

    def test_plural_and_joined(self):
        self.assertEqual(
            format_failure_note("2025-12", ["a1", "a2"]),
            "2 attachments failed to download in 2025-12: a1, a2",
        )


class ResolveStatusTest(unittest.TestCase):
    def test_clean_is_success(self):
        self.assertEqual(resolve_status(False, False), "success")

    def test_failed_download_is_partial(self):
        self.assertEqual(resolve_status(False, True), "partial")

    def test_fatal_error_dominates(self):
        self.assertEqual(resolve_status(True, False), "error")
        self.assertEqual(resolve_status(True, True), "error")


if __name__ == "__main__":
    unittest.main()
