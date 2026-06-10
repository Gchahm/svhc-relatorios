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


def build_documents(target: Target = "local") -> tuple[int, int]:
    """Derive ``documents`` + ``document_entries`` from analyses, GLOBALLY and idempotently.

    For every analysis confidently carrying (number, cnpj): upsert one ``documents`` row
    per unique key (deterministic id ``det_id("document", number, cnpj)``; ``total_value``
    = the MAX confident reconciliation total across the key's analyses — order-independent
    and conservative) and one ``document_entries`` link per analysis (deterministic id, with
    the source attachment for provenance). Analyses missing either field create nothing.

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

    if docs or links:
        d1.upsert_tables(
            {"documents": list(docs.values()), "document_entries": list(links.values())},
            target=target,
        )
    logger.info(
        "build-documents (%s): %d document(s), %d link(s) upserted; %d analysis(es) skipped (no number/CNPJ)",
        target, len(docs), len(links), skipped,
    )
    return len(docs), len(links)


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
