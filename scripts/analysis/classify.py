"""Headless typed document classification (EXTRACT-007 / feature 066).

The vision step as a plain CLI command. ``classify_period`` builds the same pending plan as
``docs-plan`` (DB-controlled selection + ``--min-amount``/``--limit`` filters), then for each pending
page that is not already ``recorded`` it transcribes the page image into typed EXTRACT-001 JSON by
running ``tools/doc_transcribe`` **as a subprocess** and records the typed ``fields`` to the
``page_classifications`` staging table via :func:`record_classification`.

This replaces the former ``classify-period`` / ``classify-doc-page`` skill fan-out and the
``analyze-docs`` agent: there is no in-context page-image reading, so a caller (e.g.
``improve-classification``) stays context-clean by simply running the CLI step.

**Boundary (FR-005):** ``doc_transcribe`` is reached ONLY via subprocess — never an import. The
analysis library stays import-clean of ``tools/`` except the existing ``typed_gate`` validator seam
(used here only to schema-validate the recorded typed payload, exactly as ``record-classification``
does).

Pages are processed **serially, one at a time** (FR-004) — simple and cost-predictable. A per-page
transcription failure (the subprocess exits 0 but the result carries ``parse_errors`` / no usable
``fields``) records an ``{"error": ...}`` row and the run continues (FR-007). A config/environment
error (the subprocess exits non-zero, e.g. ``claude`` not on PATH) raises :class:`ClassifyConfigError`
and stops the run with the subprocess's message — no silent backend fallback (FR-006).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from common.d1 import Target

from .extractions import DEFAULT_CACHE_DIR, build_plan
from .images import materialize_period_images
from .loader import load_all_periods
from .page_classifications import record_classification

logger = logging.getLogger(__name__)

# <repo>/tools — resolved the same way scripts/analysis/typed_gate.py resolves it (parents[2]),
# so the doc_transcribe subprocess can ``import doc_transcribe`` even though the analysis CLI runs
# with cwd=scripts/ (where tools/ is off the path).
_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


class ClassifyConfigError(Exception):
    """A config/environment error from the transcriber (e.g. ``claude`` not on PATH).

    Distinct from a per-page transcription failure: a config error stops the whole run (FR-006),
    whereas a per-page failure records an error row and continues (FR-007).
    """


def _run_doc_transcribe(read_path: str, *, backend: str = "cli", model: str | None = None) -> dict:
    """Run ``python -m doc_transcribe --image <read_path> --type auto`` as a subprocess.

    Returns the parsed JSON envelope (``{doc_type, schema_version, fields[, parse_errors]}``) on a
    zero exit. Raises :class:`ClassifyConfigError` on a non-zero exit (a config/usage error —
    ``doc_transcribe`` exits 2 on ``TranscribeError``), surfacing the subprocess's stderr.

    The subprocess runs with ``cwd=<repo>/tools`` and ``tools/`` on ``PYTHONPATH`` so
    ``import doc_transcribe`` resolves; ``doc_transcribe`` is invoked ONLY here, never imported into
    the analysis library.
    """
    cmd = [sys.executable, "-m", "doc_transcribe", "--image", read_path, "--type", "auto", "--backend", backend]
    if model:
        cmd += ["--model", model]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_TOOLS_DIR) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(cmd, cwd=str(_TOOLS_DIR), env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"doc_transcribe exited {proc.returncode}"
        raise ClassifyConfigError(msg)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        # A zero exit with unparseable stdout is itself a config/wrapper fault, not a model misread.
        raise ClassifyConfigError(f"doc_transcribe returned unparseable JSON: {exc}") from exc


def _default_transcribe_page(read_path: str, *, backend: str = "cli", model: str | None = None) -> dict:
    """Transcribe one page image into its typed ``fields`` object (the real backend).

    Returns the typed ``fields`` dict on success, or ``{"error": "<reason>"}`` for a per-page
    transcription failure (the envelope carries non-empty ``parse_errors`` or no usable ``fields``).
    Raises :class:`ClassifyConfigError` for a config error (propagated from the subprocess).
    """
    envelope = _run_doc_transcribe(read_path, backend=backend, model=model)
    return _fields_or_error(envelope)


def _fields_or_error(envelope: dict) -> dict:
    """Map a ``doc_transcribe`` result envelope to a typed ``fields`` dict or an error sentinel.

    A non-empty ``parse_errors`` list (or a missing/empty/non-dict ``fields``) is a per-page
    transcription failure → ``{"error": "<joined reasons>"}``. Otherwise the typed ``fields`` object
    (self-describing: it carries its own ``doc_type``/``schema_version``) is returned for recording.
    """
    parse_errors = envelope.get("parse_errors") if isinstance(envelope, dict) else None
    fields = envelope.get("fields") if isinstance(envelope, dict) else None
    if parse_errors:
        reason = "; ".join(str(e) for e in parse_errors) if isinstance(parse_errors, list) else str(parse_errors)
        return {"error": f"transcription failed: {reason}"}
    if not isinstance(fields, dict) or not fields:
        return {"error": "transcription returned no usable fields"}
    return fields


def classify_period(
    target: Target = "local",
    periods_filter: list[str] | None = None,
    *,
    cache_dir: str = DEFAULT_CACHE_DIR,
    min_amount: float | None = None,
    limit: int | None = None,
    attachment_ids: list[str] | None = None,
    backend: str = "cli",
    model: str | None = None,
    transcribe_page=None,
    typed_validator=None,
) -> dict:
    """Classify a period's pending, non-``recorded`` pages — headless, typed-only (vision only).

    Builds the pending plan (``build_plan``), materializes the period's page images, and for each
    page with ``recorded == False`` transcribes it (serially) and records the typed result (or an
    ``{"error": ...}`` row) to ``page_classifications``. Does NOT run apply/analyze.

    ``attachment_ids`` scopes the run to those attachments: only plan groups whose representative
    OR a member matches one of the ids are transcribed (the rest of the pending set is left
    untouched). It intersects the pending set — an id that is not pending contributes no pages, so
    ``mark-pending`` it first to force a fresh read. Empty/None ⇒ the whole pending set (default).

    ``transcribe_page`` is injectable for testing: a callable ``transcribe_page(read_path) ->
    fields-dict | {"error": ...}`` that raises :class:`ClassifyConfigError` on a config error. The
    default wraps the real ``doc_transcribe`` subprocess (threading ``backend``/``model``).
    ``typed_validator`` is the EXTRACT-001 schema validator injected into ``record_classification``
    (default: ``analysis.typed_gate.validate_typed``, lazily imported).

    Returns a summary dict ``{recorded, errors, skipped, periods, remote}``. Raises
    :class:`ClassifyConfigError` (stopping the run) on a config/environment error.
    """
    if transcribe_page is None:
        transcribe_page = lambda rp: _default_transcribe_page(rp, backend=backend, model=model)  # noqa: E731
    if typed_validator is None:
        from .typed_gate import validate_typed

        typed_validator = validate_typed

    periods, refs = load_all_periods(target, periods_filter)
    if not periods:
        logger.info("No periods to classify")
        return {"recorded": 0, "errors": 0, "skipped": 0, "periods": [], "remote": target == "remote"}

    # Bring the period's images local (R2 -> cache) so each page's read_path points at a file the
    # transcriber subprocess can open (and grouping can hash legacy rows). Read-only here.
    materialize_period_images(periods, cache_dir, target, backfill_hash=False)

    envelopes = build_plan(periods, refs, cache_dir=cache_dir, min_amount=min_amount, limit=limit)

    wanted = set(attachment_ids or [])

    recorded = errors = skipped = 0
    affected_periods: set[str] = set()
    for env in envelopes:
        period = env["period"]
        for group in env["groups"]:
            attachment_id = group["representative_attachment_id"]
            if wanted and not (
                attachment_id in wanted
                or any(m.get("attachment_id") in wanted for m in group.get("members", []))
            ):
                continue
            for page in group["pages"]:
                if page.get("recorded"):
                    skipped += 1
                    continue
                read_path = page.get("read_path") or page["path"]
                page_label = page["page_label"]
                # A config error stops the WHOLE run (propagates out) — no fallback (FR-006).
                payload = transcribe_page(read_path)
                record_classification(
                    attachment_id,
                    page_label,
                    payload,
                    page_index=page.get("page_index"),
                    target=target,
                    typed_validator=typed_validator,
                )
                if "error" in payload:
                    errors += 1
                    logger.warning("classify %s %s: recorded error row (%s)", attachment_id, page_label, payload["error"])
                else:
                    recorded += 1
                affected_periods.add(period)

    logger.info(
        "Classified %s: %d typed page(s), %d error row(s), %d already-recorded skipped",
        ",".join(sorted(affected_periods)) or "(none)", recorded, errors, skipped,
    )
    return {
        "recorded": recorded,
        "errors": errors,
        "skipped": skipped,
        "periods": sorted(affected_periods),
        "remote": target == "remote",
    }
