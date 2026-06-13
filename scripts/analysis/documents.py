"""Real fiscal documents — build the global entity + detect overpayment.

A *document* is one real fiscal document (NF / NFS-e / receipt / boleto) identified
inside attachment pages, keyed by the semantic pair (normalized document number,
issuer CNPJ). Unlike an ``attachment`` (the per-entry page bundle, one per entry), a
document is GLOBAL: the same invoice re-submitted in another period — even as a
different scan — resolves to one row. Documents link N:N to ledger entries via
``document_entries``.

This module owns:
  - identity/normalization (``normalize_number`` / ``normalize_cnpj`` / ``document_key``),
  - ``build_documents`` — derive documents + links from ``attachment_analyses`` across
    ALL periods (global, idempotent upsert via deterministic ids),
  - ``check_document_overpayment`` — raise a ``document_overpayment`` alert when the
    linked entries' live amounts sum above the document total (supersedes the old
    transient ``duplicate_billing`` over-claim signal).

Both read D1 directly (global, independent of any ``--periodo`` filter); period-scoped
loading would mis-dedup an NF that recurs across months. See specs/020-documents-entity.
"""

import json
import logging
from collections import defaultdict

from common import det_id, now_ms, d1
from common.d1 import Target

from .attachments import nf_total_for_reconciliation
from .models import Alert
from .nf_groups import reconcile_group

logger = logging.getLogger(__name__)

# Non-alphanumeric separators stripped from a document number for the identity key.
_SEP = str.maketrans("", "", " . /-\\_")


def normalize_number(value) -> str:
    """Normalize a document number for keying: trim, strip separators, uppercase.

    Returns ``""`` when the input is empty/None (i.e. not confident).
    """
    if value is None:
        return ""
    return str(value).strip().translate(_SEP).upper()


def normalize_cnpj(value) -> str | None:
    """Reduce a CNPJ to its 14 digits; ``None`` when not exactly 14 (not confident)."""
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits if len(digits) == 14 else None


def document_key(analysis: dict) -> tuple[str, str] | None:
    """The ``(number, cnpj)`` identity for an analysis, or ``None`` when not confident.

    Confident iff the normalized document number is non-empty AND the issuer CNPJ
    reduces to exactly 14 digits (FR-004/FR-005). Sourced from the rolled-up
    ``attachment_analyses`` fields ``document_number`` / ``extracted_cnpj``.
    """
    number = normalize_number(analysis.get("document_number"))
    cnpj = normalize_cnpj(analysis.get("extracted_cnpj"))
    if not number or not cnpj:
        return None
    return number, cnpj


def _load_analyses_global(target: Target) -> list[dict]:
    """Every attachment analysis (with its entry + per-page records), across all periods.

    Joins ``attachment_analyses → attachments → entries`` so each row carries the
    attachment id, entry id, and live entry amount; nests the per-page records'
    decoded ``response`` so ``nf_total_for_reconciliation`` can read the invoice gross.
    """
    analyses = d1.query(
        "SELECT da.*, d.id AS attachment_id, d.entry_id AS entry_id, e.amount AS entry_amount "
        "FROM attachment_analyses da "
        "JOIN attachments d ON da.attachment_id = d.id "
        "JOIN entries e ON d.entry_id = e.id",
        target=target,
    )
    if not analyses:
        return []
    an_ids = ",".join("'" + str(a["id"]).replace("'", "''") + "'" for a in analyses)
    records = d1.query(
        f"SELECT * FROM attachment_analysis_records WHERE attachment_analysis_id IN ({an_ids})",
        target=target,
    )
    by_analysis: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        resp = r.get("response")
        if isinstance(resp, str):
            try:
                r["response"] = json.loads(resp) if resp else None
            except json.JSONDecodeError:
                r["response"] = None
        by_analysis[r["attachment_analysis_id"]].append(r)
    for a in analyses:
        a["analysis_records"] = by_analysis.get(a["id"], [])
    return analyses


def _analysis_total(analysis: dict) -> float | None:
    """The confident reconciliation total for one analysis (invoice gross, else roll-up)."""
    responses = [r.get("response") for r in analysis.get("analysis_records", [])]
    return nf_total_for_reconciliation(responses, analysis.get("extracted_amount"))


def _sql_id_list(ids) -> str:
    """SQL single-quoted, escaped, comma-joined id list for an ``IN (...)`` clause."""
    return ",".join("'" + str(i).replace("'", "''") + "'" for i in ids)


def _prune_sql(table: str, desired_ids: set[str]) -> str:
    """One authoritative DELETE for ``table``: remove every row not in ``desired_ids``.

    When ``desired_ids`` is empty the desired state for the table is empty, so this becomes an
    unconditional ``DELETE FROM <table>`` (``NOT IN ()`` is invalid SQLite). Otherwise it deletes
    only the rows whose id is not in the desired set — the stale rows a re-classification orphaned.
    """
    if not desired_ids:
        return f"DELETE FROM {table};"
    return f"DELETE FROM {table} WHERE id NOT IN ({_sql_id_list(desired_ids)});"


def build_documents(target: Target = "local") -> tuple[int, int]:
    """Derive ``documents`` + ``document_entries`` from analyses, GLOBALLY and AUTHORITATIVELY.

    For every analysis confidently carrying (number, cnpj): upsert one ``documents`` row
    per unique key (deterministic id ``det_id("document", number, cnpj)``; ``total_value``
    = the MAX confident reconciliation total across the key's analyses — order-independent
    and conservative) and one ``document_entries`` link per analysis (deterministic id, with
    the source attachment for provenance). Analyses missing either field create nothing.

    The write is AUTHORITATIVE (feature 025 / issue #36): these are pure derived tables with no
    user-owned state, so any persisted document/link whose id the current analyses no longer
    produce is PRUNED — otherwise a re-classification that changes an analysis's (number, cnpj)
    leaves a zombie document + link that distorts the documents list and can fire a false
    ``document_overpayment`` alert. The prune DELETEs and the upsert INSERTs are submitted as ONE
    atomic D1 batch (single ``execute_sql`` — one implicit transaction), mirroring the alert
    writeback (feature 024), so a partial failure can never remove stale rows without writing the
    new ones (or vice versa). When the desired state is empty, all documents and links are removed.

    Returns ``(documents_upserted, links_upserted)``.
    """
    analyses = _load_analyses_global(target)
    ts = now_ms()  # the raw-SQL upsert path does not get Drizzle's $defaultFn timestamps.

    docs: dict[tuple[str, str], dict] = {}
    links: dict[str, dict] = {}
    skipped = 0

    for a in analyses:
        key = document_key(a)
        if key is None:
            skipped += 1
            continue
        number, cnpj = key
        doc_id = det_id("document", number, cnpj)
        total = _analysis_total(a)

        doc = docs.get(key)
        if doc is None:
            doc = {
                "id": doc_id,
                "document_number": number,
                "issuer_cnpj": cnpj,
                "issuer_name": a.get("issuer_name") or None,
                "document_type": a.get("document_type") or None,
                "total_value": total,
                "created_at": ts,
                "updated_at": ts,
            }
            docs[key] = doc
        else:
            # First non-empty display fields win; total_value = max confident total.
            if not doc["issuer_name"] and a.get("issuer_name"):
                doc["issuer_name"] = a.get("issuer_name")
            if not doc["document_type"] and a.get("document_type"):
                doc["document_type"] = a.get("document_type")
            if total is not None and (doc["total_value"] is None or total > doc["total_value"]):
                doc["total_value"] = total

        link_id = det_id("document_entry", doc_id, a["entry_id"])
        links[link_id] = {
            "id": link_id,
            "document_id": doc_id,
            "entry_id": a["entry_id"],
            "source_attachment_id": a.get("attachment_id"),
            "created_at": ts,
        }

    desired_doc_ids = {d["id"] for d in docs.values()}
    desired_link_ids = set(links)

    # Pre-read the persisted ids so we can report a real pruned count (FR-008). Id-only reads
    # are cheap; the prune itself is driven by `NOT IN (<desired>)`, not by this read.
    existing_doc_ids = {r["id"] for r in d1.query("SELECT id FROM documents", target=target)}
    existing_link_ids = {r["id"] for r in d1.query("SELECT id FROM document_entries", target=target)}
    pruned_docs = existing_doc_ids - desired_doc_ids
    pruned_links = existing_link_ids - desired_link_ids

    # Authoritative write in ONE atomic batch (feature 024 idiom): DELETE the stale rows (links
    # before documents — FK-safe order), then INSERT OR REPLACE the desired rows. `upsert_sql`
    # returns "" when there are no desired rows, so an empty desired state yields prune-only SQL
    # (unconditional DELETE FROM both tables). Skip the call only when there is nothing to do.
    prune_sql = ""
    if pruned_links:
        prune_sql += _prune_sql("document_entries", desired_link_ids) + "\n"
    if pruned_docs:
        prune_sql += _prune_sql("documents", desired_doc_ids) + "\n"
    upsert_sql = d1.upsert_sql(
        {"documents": list(docs.values()), "document_entries": list(links.values())}
    )
    batch = prune_sql + upsert_sql
    if batch:
        d1.execute_sql(batch, target=target)

    logger.info(
        "build-documents (%s): %d document(s), %d link(s) upserted; pruned %d document(s), %d link(s); "
        "%d analysis(es) skipped (no number/CNPJ)",
        target, len(docs), len(links), len(pruned_docs), len(pruned_links), skipped,
    )
    return len(docs), len(links)


class DocumentNotFound(LookupError):
    """Raised when a document id has no row in ``documents`` (TRIAGE-002 / issue #85)."""


def resolve_document_attachment_ids(document_id: str, target: Target = "local") -> list[str]:
    """Resolve a document id to its distinct source attachment ids (read-only).

    A document is global and N:N with entries via ``document_entries``; each link row carries
    ``source_attachment_id`` provenance — the attachment that produced it (feature 020). Correction
    happens at the attachment level, so the triage agent needs the document's source attachments.

    Returns the **sorted, distinct, non-NULL** ``source_attachment_id`` set for ``document_id``.
    Raises :class:`DocumentNotFound` when the id has no ``documents`` row (so an unknown id is a
    clear error, never a misleading empty result — FR-005). An existing document with no resolvable
    source attachments returns ``[]`` (FR-006). Issues only ``SELECT``s — mutates nothing (FR-004).
    """
    quoted = "'" + str(document_id).replace("'", "''") + "'"
    exists = d1.query(f"SELECT id FROM documents WHERE id = {quoted}", target=target)
    if not exists:
        raise DocumentNotFound(document_id)
    rows = d1.query(
        "SELECT DISTINCT source_attachment_id FROM document_entries "
        f"WHERE document_id = {quoted} AND source_attachment_id IS NOT NULL",
        target=target,
    )
    return sorted(r["source_attachment_id"] for r in rows)


def document_evidence(
    document_id: str,
    target: Target = "local",
    *,
    cache_dir: str | None = None,
) -> dict:
    """One-shot triage evidence for a document id: resolved attachments + scoped findings.

    Maps the document id to its source attachment ids (:func:`resolve_document_attachment_ids`),
    then delegates to the existing ``summarize_mismatches`` engine scoped to those attachments, so
    the per-finding shape + ``page_refs`` (materialized image ``read_path`` s) are identical to the
    ``mismatches`` command — no drift (FR-003). Read-only (the only side effect is the image
    materialization ``summarize_mismatches`` already performs into the ephemeral local cache).

    Returns ``{"document_id", "attachment_ids", "findings"}``. When the document resolves to no
    source attachments the findings list is empty (FR-006/FR-008) — the summary is scoped to the
    empty attachment set, never to "all attachments".
    """
    # Imported here to avoid a module import cycle (``extractions`` imports from several analysis
    # modules; ``documents`` is the entity owner and must stay importable independently).
    from .extractions import DEFAULT_CACHE_DIR, summarize_mismatches

    attachment_ids = resolve_document_attachment_ids(document_id, target=target)
    # No source attachments ⇒ nothing to triage. Short-circuit: ``summarize_mismatches`` treats a
    # falsy ``attachment_ids`` as "no scope" and would return EVERY period's findings, so never call
    # it with an empty list (FR-006/FR-008).
    findings: list[dict] = (
        summarize_mismatches(
            target=target,
            cache_dir=cache_dir or DEFAULT_CACHE_DIR,
            attachment_ids=attachment_ids,
        )
        if attachment_ids
        else []
    )
    return {
        "document_id": document_id,
        "attachment_ids": attachment_ids,
        "findings": findings,
    }


def _load_documents_with_links(target: Target) -> list[dict]:
    """Each document with its linked entries' live amounts + periods (global)."""
    documents = d1.query("SELECT * FROM documents", target=target)
    if not documents:
        return []
    links = d1.query(
        "SELECT de.document_id AS document_id, de.entry_id AS entry_id, "
        "e.amount AS amount, r.period AS period "
        "FROM document_entries de "
        "JOIN entries e ON de.entry_id = e.id "
        "JOIN accountability_reports r ON e.report_id = r.id",
        target=target,
    )
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for ln in links:
        by_doc[ln["document_id"]].append(ln)
    for doc in documents:
        doc["links"] = by_doc.get(doc["id"], [])
    return documents


def check_document_overpayment(target: Target = "local") -> list[Alert]:
    """Raise a ``document_overpayment`` (critical) alert per over-claimed document.

    Over-claim = the linked entries' LIVE amounts sum above the document ``total_value``
    beyond the shared tolerance (``reconcile_group``). Global (cross-period): the alert's
    ``reference_period`` is the latest period among the linked entries. A document with no
    confident total is skipped (graceful — no spurious alert). Supersedes the retired
    ``duplicate_billing`` over-claim check.
    """
    alerts: list[Alert] = []
    for doc in _load_documents_with_links(target):
        links = doc.get("links", [])
        if not links:
            continue
        total = doc.get("total_value")
        sibling_sum = sum(ln["amount"] for ln in links)
        if reconcile_group(sibling_sum, total) != "over_claim":
            continue

        entry_ids = [ln["entry_id"] for ln in links]
        periods = [ln["period"] for ln in links if ln.get("period")]
        reference_period = max(periods) if periods else ""
        over = round(sibling_sum - total, 2)
        number = doc.get("document_number")
        alerts.append(Alert(
            id=det_id("alert", reference_period, "document_overpayment", doc["id"]),
            type="document_overpayment",
            severity="critical",
            title=f"Nota fiscal {number} cobrada acima do valor",
            description=(
                f"A nota fiscal {number} (total R$ {total:.2f}) está vinculada a "
                f"{len(entry_ids)} lançamentos que somam R$ {sibling_sum:.2f} — "
                f"cobrança de R$ {over:.2f} acima do valor da nota."
            ),
            reference_period=reference_period,
            metadata={
                "document_id": doc["id"],
                "document_number": number,
                "issuer_cnpj": doc.get("issuer_cnpj"),
                "total_value": round(total, 2),
                "sum_entries": round(sibling_sum, 2),
                "over_amount": over,
                "entry_ids": entry_ids,
            },
        ))
    logger.info("document-overpayment (%s): %d alert(s)", target, len(alerts))
    return alerts
