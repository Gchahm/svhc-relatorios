"""Surface partial attachment-download failures during a scrape (IMP-004 / issue #41).

A page-fetch failure leaves an attachment persisted with ``file_path = NULL`` — un-groupable and
unviewable — yet the run still reported "success" and nothing named the affected attachments. This
pure, stdlib-only module (importable without ``playwright``, mirroring ``preserve.py`` /
``consistency.py``) holds the three deterministic decisions the scraper runner needs:

- ``failed_attachment_ids`` — which attempted attachments still have no pages this run,
- ``format_failure_note`` — the queryable run-note line recorded on ``scrape_runs.errors``,
- ``resolve_status`` — the run status (``error`` > ``partial`` > ``success`` precedence).

The runner orchestrates (collects the attempted set, accumulates notes, sets the status); the
per-attachment auditor-facing ``attachment_not_downloaded`` alert is raised separately by the
analysis pass (mirror invariant — the scraper does not write the analysis-owned ``alerts`` table).
"""

from __future__ import annotations


def _has_pages(attachment: dict) -> bool:
    """True when the attachment has a stored page linkage (non-empty file_path)."""
    return bool(attachment.get("file_path"))


def failed_attachment_ids(attachments_out: list[dict], attempted_ids: set[str]) -> list[str]:
    """Ids of attachments a download was attempted for that still have no pages this run.

    An attachment counts as failed iff it is in ``attempted_ids`` (a download was attempted) AND its
    row — AFTER the ``preserve_existing_attachment_cols`` merge — still has a falsy ``file_path``.
    Using the post-preserve value means an attachment whose prior successful pages were preserved is
    NOT counted (no evidence was actually lost), while a never-before-fetched attachment that failed
    this run IS counted. Order follows ``attachments_out`` for determinism.
    """
    return [a["id"] for a in attachments_out if a.get("id") in attempted_ids and not _has_pages(a)]


def format_failure_note(period: str, failed_ids: list[str]) -> str | None:
    """One queryable run-note line for a period's failed downloads, or None when there are none."""
    if not failed_ids:
        return None
    n = len(failed_ids)
    plural = "attachment" if n == 1 else "attachments"
    return f"{n} {plural} failed to download in {period}: {', '.join(failed_ids)}"


def resolve_status(has_fatal_errors: bool, any_download_failed: bool) -> str:
    """The terminal scrape-run status.

    Precedence: a fatal scrape error dominates (``error``); else any failed attachment download makes
    the run ``partial``; else ``success``. The ``running`` initial value is set elsewhere.
    """
    if has_fatal_errors:
        return "error"
    if any_download_failed:
        return "partial"
    return "success"
