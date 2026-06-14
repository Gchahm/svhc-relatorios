"""Per-page classification staging: the DB-backed seam between the vision skill and apply.

Replaces the former ``<image>.classify.json`` file seam (feature 017). The
``classify-doc-page`` skill records one extraction per page through the
``record-classification`` CLI, which writes a row to the ``page_classifications`` table
(one row per ``(attachment_id, page_label)``). ``apply-extractions`` then reads those
rows — via :class:`D1ExtractionProvider` — to build the authoritative roll-up
(``attachment_analyses`` + ``attachment_analysis_records``). The staging table is the
merge's *input*; the finalized roll-up remains the authoritative analysis.

This module owns: the frozen per-page field contract (ported from the skill's former
``validate_classify.py`` PostToolUse hook, which no longer fires because the skill no
longer writes a file), the deterministic row id, the record-write, and the
D1-backed extraction provider. Stdlib only.
"""

from __future__ import annotations

import json

from common import d1, det_id, now_ms
from common.d1 import Target

TABLE = "page_classifications"

# ─── Frozen per-page field contract ──────────────────────────────────────────
# Mirrors .claude/skills/classify-doc-page/templates/result.json and the page-extraction
# contract the deterministic pipeline consumes. Keep in sync with the skill's template.
REQUIRED_KEYS = {
    "papel_artefato",
    "tipo_documento",
    "valor_total",
    "valor_liquido",
    "valor_pago",
    "cnpj_emitente",
    "nome_emitente",
    "data_emissao",
    "numero_documento",
    "descricao_servico",
}
PAPEL_VALUES = {"invoice", "nfse", "boleto", "payment_proof", "other"}
STRING_OR_NULL = {
    "tipo_documento",
    "cnpj_emitente",
    "nome_emitente",
    "data_emissao",
    "numero_documento",
    "descricao_servico",
}
AMOUNT_KEYS = {"valor_total", "valor_liquido", "valor_pago"}


def is_typed(resp) -> bool:
    """The single typed-vs-flat discriminator (feature 055 / FR-008).

    A stored per-page response is a **typed transcription** (the EXTRACT-001-conformant per-type
    object) when it is a dict carrying a ``doc_type`` key; a dict without ``doc_type`` is a **legacy
    flat record** (the pre-typed reconciliation contract below). Owned here so the store / derive /
    render paths cannot drift on the discriminator (the EXTRACT-003 mapper keys on ``doc_type`` too,
    and the UI mirrors this predicate). Never raises.
    """
    return isinstance(resp, dict) and "doc_type" in resp


def validate_page_fields(obj, *, typed_validator=None) -> str | None:
    """Validate a per-page extraction against the frozen contract (dual-path).

    Returns an error message describing the first violation, or ``None`` when the
    payload is valid. Accepts ONE of:

    - the single permitted error alternative ``{"error": "<non-empty string>"}`` (unchanged);
    - a **typed transcription** payload (a dict carrying ``doc_type``) — validated against the
      EXTRACT-001 schema for its type via ``typed_validator`` (feature 055). ``typed_validator`` is
      injected (default ``None``) so this module stays stdlib-only and import-clean of ``tools/``;
      the ``record-classification`` CLI supplies ``analysis.typed_gate.validate_typed``. When no
      validator is supplied a typed payload is accepted only structurally (it must be a dict) — but
      the CLI always supplies the gate, so typed payloads are always schema-validated in practice;
    - the legacy **flat** fields object (no ``doc_type``: exactly ``REQUIRED_KEYS``,
      ``papel_artefato`` in the allowed set, string-or-null and amount typing) — unchanged.

    This is the canonical validator the ``record-classification`` CLI enforces.
    """
    if not isinstance(obj, dict):
        return f"expected a single JSON object, got {type(obj).__name__}"

    keys = set(obj)

    # An error object is the one allowed alternative to the fields object.
    if "error" in keys:
        if keys != {"error"}:
            return f'an error result must be exactly {{"error": "..."}}, got keys {sorted(keys)}'
        if not isinstance(obj["error"], str) or not obj["error"].strip():
            return '"error" must be a non-empty string'
        return None

    # A typed transcription payload (carries doc_type): validate against the EXTRACT-001 schema.
    if is_typed(obj):
        if typed_validator is None:
            return None
        errors = typed_validator(obj, obj.get("doc_type"))
        if errors:
            return "typed payload does not conform to the EXTRACT-001 schema: " + "; ".join(errors)
        return None

    missing = REQUIRED_KEYS - keys
    extra = keys - REQUIRED_KEYS
    if missing:
        return f"missing required field(s): {sorted(missing)}"
    if extra:
        return f"unexpected field(s) (do not add/rename keys): {sorted(extra)}"

    papel = obj["papel_artefato"]
    if papel not in PAPEL_VALUES:
        return f"papel_artefato must be one of {sorted(PAPEL_VALUES)}, got {papel!r}"

    for k in STRING_OR_NULL:
        v = obj[k]
        if v is not None and not isinstance(v, str):
            return f"{k} must be a string or null, got {type(v).__name__}"

    for k in AMOUNT_KEYS:
        v = obj[k]
        if v is None:
            continue
        # bool is a subclass of int — reject it explicitly.
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            return f"{k} must be a number, a currency string, or null, got {type(v).__name__}"

    return None


def _prune_page_classifications_sql(attachment_ids: list[str]) -> str:
    """Build a DELETE that removes the staging rows of the given attachments — without executing.

    Returns ``DELETE FROM page_classifications WHERE attachment_id IN ('a','b',…);`` for a
    non-empty id list (each id single-quote-escaped, ``'`` → ``''``), or ``""`` for an empty list.
    Mirrors the ``upsert_sql`` / ``documents._prune_sql`` seam ("return SQL, the caller folds it
    into its own ``execute_sql`` batch"), so both cleanup hooks compose this into the single atomic
    batch they already issue (feature 024 convention). Pure — no I/O.

    Used by ``apply-extractions`` (``_merge_and_write`` consumes an attachment's staging rows once
    its authoritative ``attachment_analyses`` write lands) and ``mark-pending`` (clears a re-queued
    attachment's staging rows so reclassification starts clean) — feature 035 / issue #42.
    """
    ids = [i for i in attachment_ids if i]
    if not ids:
        return ""
    quoted = ",".join("'" + str(i).replace("'", "''") + "'" for i in ids)
    return f"DELETE FROM {TABLE} WHERE attachment_id IN ({quoted});"


def page_classification_id(attachment_id: str, page_label: str) -> str:
    """Deterministic row id for one page's classification.

    Keyed on ``(attachment_id, page_label)`` so re-recording the same page replaces the
    same row (idempotent upsert; latest extraction wins).
    """
    return det_id("page_classification", attachment_id, page_label)


def _q(value: str) -> str:
    """Single-quote a value for inline SQL (``'`` → ``''``)."""
    return "'" + str(value).replace("'", "''") + "'"


def staging_rows_from_records(attachment_id: str, records: list[dict]) -> list[dict]:
    """Reconstruct an attachment's ``page_classifications`` staging rows from its stored records.

    Pure transform (no I/O): maps each persisted ``page_extraction`` record dict — as queried from
    ``attachment_analysis_records`` (carrying ``page_label``, ``page_index``, ``response`` (a dict, a
    JSON string, or ``None``), ``parse_error``) — to a staging-table row shaped exactly like
    ``record_classification`` writes (id keyed on ``(attachment_id, page_label)``; ``response`` decoded
    to a dict or ``None``; ``parse_error`` → ``error``; fresh ``recorded_at``). Rows without a
    ``page_label`` are skipped (they cannot key a staging row).

    This is the durable transcription → staging bridge shared by the data-correction snapshot
    (feature 054) and the ``re-derive`` command (feature 056): the staging table is pruned after apply
    (feature 035), but the verbatim per-page transcription survives in ``attachment_analysis_records.response``,
    so restoring it as staging and re-applying re-derives the prior ``attachment_analyses`` byte-for-byte
    (with the CURRENT mappers — which is exactly what ``re-derive`` exploits after a mapper fix).
    """
    out: list[dict] = []
    for r in records or []:
        page_label = r.get("page_label")
        if not page_label:
            continue
        resp = r.get("response")
        if isinstance(resp, str) and resp:
            try:
                resp = json.loads(resp)
            except json.JSONDecodeError:
                resp = None
        out.append(
            {
                "id": page_classification_id(attachment_id, page_label),
                "attachment_id": attachment_id,
                "page_label": page_label,
                "page_index": r.get("page_index"),
                "response": resp if isinstance(resp, dict) else None,
                "error": r.get("parse_error"),
                "recorded_at": now_ms(),
            }
        )
    return out


def load_stored_records(attachment_id: str, target: Target = "local") -> list[dict]:
    """Read an attachment's persisted ``page_extraction`` records (the durable transcription).

    Joins ``attachment_analysis_records`` to the attachment's ``attachment_analyses`` row and returns
    the per-page ``page_label``/``page_index``/``response``/``parse_error`` — the input to
    :func:`staging_rows_from_records`. The durable copy of each page's transcription (feature 035
    prunes the live staging after apply), so this is the source ``re-derive`` and the correction
    snapshot read.
    """
    return d1.query(
        "SELECT rec.page_label AS page_label, rec.page_index AS page_index, "
        "rec.response AS response, rec.parse_error AS parse_error "
        "FROM attachment_analysis_records rec "
        "JOIN attachment_analyses an ON rec.attachment_analysis_id = an.id "
        f"WHERE an.attachment_id = {_q(attachment_id)} AND rec.analysis_type = 'page_extraction'",
        target=target,
    )


def clear_classified_stamp(attachment_id: str, target: Target = "local") -> None:
    """Clear ONLY ``attachment_state.classified_at`` (re-queue the attachment for apply).

    Unlike ``mark_pending``, this does NOT delete the attachment's ``page_classifications`` staging
    rows — the staging we just wrote (a correction snapshot, or a re-derived transcription) IS the
    input apply must roll up. (``mark_pending`` folds a staging DELETE into its batch, which would wipe
    those rows.) The feature-050 staging-driven apply selects from the *pending* plan, so the stamp
    must be NULL for the attachment to be visited.
    """
    d1.execute_sql(
        f"UPDATE attachment_state SET classified_at = NULL WHERE attachment_id = {_q(attachment_id)};",
        target=target,
    )


def record_classification(
    attachment_id: str,
    page_label: str,
    payload: dict,
    *,
    page_index: int | None = None,
    target: Target = "local",
    typed_validator=None,
) -> None:
    """Validate then upsert one page's extraction into ``page_classifications``.

    ``payload`` is a typed transcription object (carrying ``doc_type``), the legacy flat fields
    object, or ``{"error": "<reason>"}`` (already parsed from JSON). Raises :class:`ValueError` on a
    contract violation so the caller (the CLI) can exit non-zero and the classifier can correct and
    re-record. A typed/flat fields object sets ``response`` (stored VERBATIM — the typed JSON,
    carrying ``doc_type``/``schema_version``, survives into ``attachment_analysis_records`` after
    roll-up) and leaves ``error`` NULL; an error result sets ``error`` and leaves ``response`` NULL.

    ``typed_validator`` is the EXTRACT-001 schema validator for typed payloads (the CLI passes
    ``analysis.typed_gate.validate_typed``); it is injected to keep this module import-clean of
    ``tools/``.
    """
    err = validate_page_fields(payload, typed_validator=typed_validator)
    if err is not None:
        raise ValueError(err)

    is_error = "error" in payload
    row = {
        "id": page_classification_id(attachment_id, page_label),
        "attachment_id": attachment_id,
        "page_label": page_label,
        "page_index": page_index,
        # d1._escape_sql JSON-serializes a dict; store None for an error result.
        "response": None if is_error else payload,
        "error": str(payload["error"]) if is_error else None,
        "recorded_at": now_ms(),
    }
    d1.upsert_tables({TABLE: [row]}, target=target)


class D1ExtractionProvider:
    """Extraction provider backed by the loaded ``page_classifications`` rows.

    Built from the period's staging rows (batch-loaded once by the loader), so each
    lookup is in-memory — no per-page ``wrangler`` round trip. Matches the
    ``ExtractionProvider`` seam in ``attachments.build_attachment_analysis``, but keyed by
    ``(attachment_id, page_label)`` (a page-image filename is named by *entry*, not
    attachment, so identity comes from the plan, not the path). Returns:

    - ``(fields, None)`` for a recorded fields object,
    - ``(None, reason)`` for a recorded error result,
    - ``(None, "no classification for page …")`` when no row exists for the page.
    """

    def __init__(self, rows: list[dict] | None = None):
        self._by_key: dict[tuple[str, str], dict] = {}
        for r in rows or []:
            self._by_key[(r["attachment_id"], r["page_label"])] = r

    def __call__(self, attachment_id: str, page_label: str) -> tuple[dict | None, str | None]:
        row = self._by_key.get((attachment_id, page_label))
        if row is None:
            return None, "no classification for page (run classify-doc-page)"
        if row.get("error"):
            return None, str(row["error"])
        resp = row.get("response")
        if not isinstance(resp, dict):
            return None, "invalid classification (no fields recorded)"
        return resp, None
