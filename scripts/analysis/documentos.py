"""Document analysis using Vision Language Model.

Extracts structured data from receipt/invoice images and validates
against entry data to detect mismatches and potential fraud.
"""

import json
import logging
import pathlib
import re
from dataclasses import dataclass, field
from common import det_id, now_ms
from .nf_groups import group_documents, reconcile_group
from .vendor_match import is_payer_name, reconcile_vendor

logger = logging.getLogger(__name__)


@dataclass
class PageAnalysisRecord:
    """A single per-page (per analysis kind) analysis record for a document.

    Persisted nested under its document analysis in the period JSON and
    normalized into the `document_analysis_records` table on import. Many per
    document and more than one per page are allowed (distinguished by
    `analysis_type`) so future analysis kinds attach without a schema change.
    """

    document_analysis_id: str
    analysis_type: str = "page_extraction"
    page_index: int | None = None
    page_label: str | None = None
    artifact_role: str | None = None
    response: dict | None = None  # parsed page values (stored JSON-serialized on import)
    raw_text: str | None = None  # VLM raw text, kept when parsing failed
    parse_error: str | None = None  # set when image missing/unreadable or unparseable

    def to_dict(self) -> dict:
        page_ref = self.page_label or (str(self.page_index) if self.page_index is not None else "?")
        return {
            "id": det_id("analysis_record", self.document_analysis_id, self.analysis_type, page_ref),
            "document_analysis_id": self.document_analysis_id,
            "analysis_type": self.analysis_type,
            "page_index": self.page_index,
            "page_label": self.page_label,
            "artifact_role": self.artifact_role,
            "response": self.response,
            "raw_text": self.raw_text,
            "parse_error": self.parse_error,
            "analyzed_at": now_ms(),
        }


@dataclass
class DocAnalysisResult:
    document_id: str
    entry_id: str
    entry_amount: float | None = None
    document_type: str | None = None
    extracted_amount: float | None = None
    amount_match: bool | None = None
    extracted_cnpj: str | None = None
    issuer_name: str | None = None
    vendor_match: bool | None = None
    extracted_date: str | None = None
    date_match: bool | None = None
    document_number: str | None = None
    service_description: str | None = None
    raw_response: str | None = None  # legacy: no longer carries per-page detail (see records)
    error: str | None = None
    records: list[PageAnalysisRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": det_id("doc_analysis", self.document_id),
            "document_id": self.document_id,
            "analyzed_at": now_ms(),
            "document_type": self.document_type,
            "extracted_amount": self.extracted_amount,
            "amount_match": 1 if self.amount_match else 0 if self.amount_match is not None else None,
            "extracted_cnpj": self.extracted_cnpj,
            "issuer_name": self.issuer_name,
            "vendor_match": 1 if self.vendor_match else 0 if self.vendor_match is not None else None,
            "extracted_date": self.extracted_date,
            "date_match": 1 if self.date_match else 0 if self.date_match is not None else None,
            "document_number": self.document_number,
            "service_description": self.service_description,
            "raw_response": self.raw_response,
            "error": self.error,
            "analysis_records": [r.to_dict() for r in self.records],
        }


def _parse_json_blob(text: str) -> dict | None:
    """Extract a JSON object from free text, handling markdown fences.

    Tolerant parser shared by the (legacy) VLM path and any caller that needs to
    recover a JSON object from a string-wrapped extraction.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _parse_brl_value(text) -> float | None:
    """Parse a Brazilian currency value to float."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    text = str(text).strip().replace("R$", "").strip()
    text = re.sub(r"[^\d,.]", "", text)
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _check_date_in_period(date_str: str | None, period: str) -> bool | None:
    """Check if extracted date falls within the period month or previous month."""
    if not date_str:
        return None
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str)
    if not match:
        return None
    day, month, year = match.groups()
    doc_period = f"{year}-{month}"
    y, m = int(period[:4]), int(period[5:])
    prev_m = m - 1
    prev_y = y
    if prev_m < 1:
        prev_m = 12
        prev_y -= 1
    prev_period = f"{prev_y:04d}-{prev_m:02d}"
    return doc_period in (period, prev_period)


def _document_in_period(records, period: str) -> bool | None:
    """Cash-basis period membership across ALL of a document's page records.

    The condominium books on a cash basis: a document bundles an invoice issued
    in an earlier month plus a payment artifact (boleto vencimento / PIX / Sicredi
    comprovante) settled inside the period. A document therefore belongs to the
    period if ANY of its pages carries an in-period date — the in-period payment,
    vencimento, or issue date establishes membership, regardless of which page it
    is on. This removes the false out-of-period flags on the normal lag between an
    invoice's issue date and its in-period payment, while preserving detection: a
    document with no in-period date on ANY page is still flagged.

    Returns True if any page date is in the period window (period month or the
    previous month), False if at least one page has a date but none is in window,
    and None if no page carries a date.
    """
    seen_date = False
    for r in records:
        resp = getattr(r, "response", None) or {}
        date_str = resp.get("data_emissao")
        if not date_str:
            continue
        in_period = _check_date_in_period(date_str, period)
        if in_period is None:
            continue
        seen_date = True
        if in_period:
            return True
    return False if seen_date else None


def _page_label_from_path(path: str, index: int) -> str:
    """Derive a page label from the `_pN` filename suffix, else `page{index+1}`.

    Extension-agnostic (handles mixed .jpg/.png). E.g. `<id>_p3.png` -> `p3`.
    """
    stem = pathlib.Path(path).stem
    match = re.search(r"_p(\d+)$", stem, re.IGNORECASE)
    if match:
        return f"p{int(match.group(1))}"
    return f"page{index + 1}"


# Aliases the VLM may emit for `papel_artefato` / fall back from `tipo_documento`.
_ROLE_ALIASES = {
    "nota fiscal": "invoice",
    "nota fiscal eletronica": "invoice",
    "nf-e": "invoice",
    "nfe": "invoice",
    "danfe": "invoice",
    "nfs-e": "nfse",
    "nfse": "nfse",
    "nota fiscal de servico": "nfse",
    "boleto": "boleto",
    "bank slip": "boleto",
    "comprovante": "payment_proof",
    "comprovante de pagamento": "payment_proof",
    "recibo": "payment_proof",
    "payment": "payment_proof",
}


def _map_artifact_role(parsed: dict) -> str:
    """Map the VLM classification to a normalized artifact role.

    Prefers the explicit `papel_artefato`, falling back to `tipo_documento`, then
    reconciles against stronger signals: a populated `valor_pago` or a
    comprovante/recibo `tipo_documento` means a payment proof even if the model
    mislabeled `papel_artefato` (observed: a payment proof tagged "boleto"). This
    matters because the amount roll-up prefers payment_proof over boleto — a
    misclassified payment proof would let a boleto's value win when it shouldn't.
    Returns one of invoice/nfse/boleto/payment_proof/other.
    """
    valid = {"invoice", "nfse", "boleto", "payment_proof", "other"}
    role = str(parsed.get("papel_artefato") or "").strip().lower()
    if role not in valid:
        role = _ROLE_ALIASES.get(role)
    tipo = str(parsed.get("tipo_documento") or "").strip().lower()
    if role is None:
        role = _ROLE_ALIASES.get(tipo, "other")

    # Reconcile: payment-proof signals override a non-payment label.
    has_paid = _parse_brl_value(parsed.get("valor_pago")) is not None
    if role != "payment_proof" and (has_paid or tipo in ("comprovante", "recibo")):
        role = "payment_proof"
    return role


def _issuer_names_of(records) -> list[str]:
    """Per-page ``nome_emitente`` values (non-empty), preserving order."""
    names: list[str] = []
    for r in records:
        val = (r.response or {}).get("nome_emitente")
        if val not in (None, ""):
            names.append(val)
    return names


def _pick_issuer_name(payment_recs, boleto_recs, invoice_recs, parsed_records):
    """Choose the document-level issuer name.

    Prefers the party actually paid: a payment-artifact (payment_proof/boleto)
    beneficiary, then the invoice/nfse header, then any record. The condominium payer
    (see the payer denylist) is never selected — the reader sometimes captures the
    destinatário/payer block as the issuer. Falls back to a payer name only if no
    non-payer name exists anywhere, so the field is not silently dropped.
    """
    ordered = list(payment_recs) + list(boleto_recs) + list(invoice_recs)
    ordered += [r for r in parsed_records if r not in ordered]
    fallback = None
    for r in ordered:
        val = (r.response or {}).get("nome_emitente")
        if val in (None, ""):
            continue
        if is_payer_name(val):
            fallback = fallback or val
            continue
        return val
    return fallback


def _pick_document_date(records) -> str | None:
    """Choose the document-level date for display, preferring the payment date.

    A document bundles an invoice issued in an earlier month plus an in-period
    payment artifact; the meaningful date for a cash-basis entry is the
    settlement/competência date, not the upstream invoice issue date. This mirrors
    the amount/issuer roll-up precedence (which prefers the payment artifact).
    Preference order (first dated page wins): a ``comprovante`` page reporting
    ``valor_pago`` -> any ``comprovante`` page -> any page reporting ``valor_pago``
    -> a ``recibo`` page -> a boleto page -> the invoice/nfse issue date -> any
    remaining dated page. Returns ``None`` if no page carries a date.

    Note this is for the surfaced ``extracted_date`` only; period membership is
    decided across ALL page dates by ``_document_in_period`` (a stale receipt date
    can never by itself create an out-of-period flag).
    """

    def date_of(r) -> str | None:
        val = (r.response or {}).get("data_emissao")
        return val if val not in (None, "") else None

    def tipo(r) -> str:
        return str((r.response or {}).get("tipo_documento") or "").strip().lower()

    def has_paid(r) -> bool:
        return _parse_brl_value((r.response or {}).get("valor_pago")) is not None

    def role(r) -> str:
        return r.artifact_role or "other"

    dated = [r for r in records if date_of(r)]
    if not dated:
        return None

    def rank(r) -> int:
        t = tipo(r)
        paid = has_paid(r)
        if t == "comprovante" and paid:
            return 0
        if t == "comprovante":
            return 1
        if paid:
            return 2
        if t == "recibo":
            return 3
        if role(r) == "boleto":
            return 4
        if role(r) in ("invoice", "nfse"):
            return 5
        return 6

    best = min(dated, key=rank)
    return date_of(best)


def _rollup_document_fields(result: "DocAnalysisResult") -> None:
    """Derive the document-level summary from the per-page records.

    Heterogeneity-aware (a document may bundle invoice + boleto + payment proof):
    - identity fields prefer the invoice/nfse record, else the first record that
      has each field;
    - the amount used for amount_match follows the precedence
      payment_proof paid -> boleto -> invoice net -> invoice gross.
    Gross and net are NOT collapsed here; both remain in each record's response.
    """
    parsed_records = [r for r in result.records if r.response]
    if not parsed_records:
        return

    def role(r: PageAnalysisRecord) -> str:
        return r.artifact_role or "other"

    invoice_recs = [r for r in parsed_records if role(r) in ("invoice", "nfse")]
    boleto_recs = [r for r in parsed_records if role(r) == "boleto"]
    payment_recs = [r for r in parsed_records if role(r) == "payment_proof"]

    # Identity fields: prefer invoice/nfse, then any record exposing the field.
    id_priority = invoice_recs + [r for r in parsed_records if r not in invoice_recs]

    def first_field(key: str):
        for r in id_priority:
            val = r.response.get(key)
            if val not in (None, ""):
                return val
        return None

    result.document_type = first_field("tipo_documento")
    result.extracted_cnpj = first_field("cnpj_emitente")
    result.issuer_name = _pick_issuer_name(payment_recs, boleto_recs, invoice_recs, parsed_records)
    # Date: prefer the payment-artifact (settlement/competência) date over the
    # upstream invoice issue date, mirroring the amount/issuer precedence above.
    result.extracted_date = _pick_document_date(parsed_records)
    result.document_number = first_field("numero_documento")
    result.service_description = first_field("descricao_servico")

    # Amount precedence: payment_proof paid -> boleto -> invoice net -> gross.
    # Treat non-positive as missing: a spurious `valor_pago: 0.0` must not win
    # and force extracted_amount to 0 when a real value is present elsewhere.
    def pick(records, *keys):
        for r in records:
            for key in keys:
                val = _parse_brl_value(r.response.get(key))
                if val is not None and val > 0:
                    return val
        return None

    amount = pick(payment_recs, "valor_pago", "valor_total")
    if amount is None:
        amount = pick(boleto_recs, "valor_total", "valor_pago")
    if amount is None:
        amount = pick(invoice_recs, "valor_liquido")
    if amount is None:
        amount = pick(invoice_recs or parsed_records, "valor_total")
    result.extracted_amount = amount


def nf_total_for_reconciliation(record_responses, fallback: float | None = None) -> float | None:
    """The NF face value to reconcile a shared-NF group's sibling sum against.

    Prefers the invoice's GROSS ``valor_total`` (entries on a split are gross
    allocations of the invoice, so gross is the correct target — the roll-up
    ``extracted_amount`` may be a net/paid value that would never sum to the
    siblings). Falls back to the rolled-up amount, then ``None``.

    ``record_responses`` is an iterable of per-page parsed response dicts (the
    same shape produced by the VLM and persisted under ``analysis_records``), so
    this is shared by the analysis stage and the duplicate-billing check.
    """
    for resp in record_responses:
        if not resp:
            continue
        gross = _parse_brl_value(resp.get("valor_total"))
        if gross is not None and gross > 0:
            return gross
    return fallback


def _apply_group_amount_match(result: "DocAnalysisResult", sibling_sum: float) -> str | None:
    """Override ``amount_match`` from group reconciliation; returns the outcome.

    For a shared NF the meaningful question is whether the sibling entries sum to
    the NF total, not whether each fractional entry equals the full total. A
    non-reconcilable group (no extractable NF total) is left untouched so it
    degrades gracefully rather than falsely reconciling.
    """
    nf_total = nf_total_for_reconciliation((r.response for r in result.records), result.extracted_amount)
    outcome = reconcile_group(sibling_sum, nf_total)
    if outcome == "reconciled":
        result.amount_match = True
    elif outcome in ("over_claim", "under_claim"):
        result.amount_match = False
    return outcome


def _fanout_result(
    rep: "DocAnalysisResult",
    document_id: str,
    entry_id: str,
    entry_amount: float,
    vendor_name: str | None,
    period: str,
) -> "DocAnalysisResult":
    """Build a sibling's analysis by reusing a representative's VLM extraction.

    Siblings sharing one byte-identical NF need not be re-analyzed (Story 3): we
    copy the representative's page records and roll-up, re-key the records to the
    sibling's own analysis id, and re-derive the entry-specific vendor/date
    checks against the sibling's entry. ``amount_match`` is set later from group
    reconciliation, so it is not computed here.
    """
    new = DocAnalysisResult(document_id=document_id, entry_id=entry_id, entry_amount=entry_amount)
    new.error = rep.error
    new.document_type = rep.document_type
    new.extracted_amount = rep.extracted_amount
    new.extracted_cnpj = rep.extracted_cnpj
    new.issuer_name = rep.issuer_name
    new.extracted_date = rep.extracted_date
    new.document_number = rep.document_number
    new.service_description = rep.service_description

    new_analysis_id = det_id("doc_analysis", document_id)
    for r in rep.records:
        new.records.append(
            PageAnalysisRecord(
                document_analysis_id=new_analysis_id,
                analysis_type=r.analysis_type,
                page_index=r.page_index,
                page_label=r.page_label,
                artifact_role=r.artifact_role,
                response=r.response,
                raw_text=r.raw_text,
                parse_error=r.parse_error,
            )
        )

    # Entry-specific validations re-derived for this sibling, reconciling against every
    # copied page's issuer name (same cross-page logic as the representative).
    issuer_names = _issuer_names_of(new.records) or ([new.issuer_name] if new.issuer_name else [])
    new.vendor_match = reconcile_vendor(vendor_name, issuer_names)
    # Cash-basis period membership across every copied page (an in-period payment
    # date establishes membership even if the invoice issue date is earlier).
    new.date_match = _document_in_period(new.records, period)
    return new


# An extraction provider maps a page image path to its parsed fields. It returns
# (parsed_fields, None) on success or (None, error_reason) on failure. This is the
# single seam that decouples the deterministic analysis from where the extraction
# comes from (a Claude vision agent's extractions file today; the VLM previously).
ExtractionProvider = "Callable[[str], tuple[dict | None, str | None]]"


def build_document_analysis(
    file_path: str,
    entry_amount: float,
    vendor_name: str | None,
    period: str,
    document_id: str,
    entry_id: str,
    provider,
) -> DocAnalysisResult:
    """Build a document's analysis from per-page extractions supplied by ``provider``.

    Emits one page_extraction record per page image (paths joined by ";"), then
    derives the document-level roll-up across all pages and validates it against
    the entry. A page the provider cannot extract is recorded with a parse_error
    and skipped — it does not abort the document.
    """
    result = DocAnalysisResult(
        document_id=document_id,
        entry_id=entry_id,
        entry_amount=entry_amount,
    )
    doc_analysis_id = det_id("doc_analysis", document_id)

    paths = [p.strip() for p in file_path.split(";") if p.strip()]
    if not paths:
        result.error = "no page images in file_path"
        return result

    any_success = False
    for idx, path in enumerate(paths):
        page_label = _page_label_from_path(path, idx)
        record = PageAnalysisRecord(
            document_analysis_id=doc_analysis_id,
            page_index=idx,
            page_label=page_label,
        )

        parsed, error = provider(path)
        if parsed is None:
            record.parse_error = error or "no extraction for page"
        else:
            record.response = parsed
            record.artifact_role = _map_artifact_role(parsed)
            any_success = True
        result.records.append(record)

    if not any_success:
        result.error = "no page produced a parseable response"
        return result

    # Roll up document-level fields from the per-page records (heterogeneity-aware).
    _rollup_document_fields(result)

    # Validate against the entry on the rolled-up fields (existing tolerances).
    if result.extracted_amount is not None and entry_amount > 0:
        diff_pct = abs(result.extracted_amount - entry_amount) / entry_amount
        result.amount_match = diff_pct < 0.05

    # Reconcile the ledger vendor against EVERY page's issuer name (a document bundles
    # invoice/boleto/payment-proof pages naming the same entity under different forms);
    # excludes the condominium payer. Falls back to the rolled-up issuer if no page name.
    issuer_names = _issuer_names_of(result.records) or ([result.issuer_name] if result.issuer_name else [])
    result.vendor_match = reconcile_vendor(vendor_name, issuer_names)

    # Cash-basis period membership across every page: the document is in period if
    # ANY page carries an in-period date (the in-period payment/vencimento/issue
    # date), so the normal lag between an earlier-month invoice and its in-period
    # payment no longer flags out-of-period; a truly stale document (no in-period
    # date on any page) still flags. A stale date on one page cannot by itself
    # create an out-of-period flag.
    result.date_match = _document_in_period(result.records, period)

    return result


def _merge_and_write(data_path, period_key: str, raw: dict, result: "DocAnalysisResult") -> None:
    """Merge a single analysis result into its period JSON and write to disk.

    Called after each document so partial results are inspectable mid-run and
    survive an interruption. Replaces any prior analysis for the same document.
    """
    existing_analyses = [
        a for a in raw.get("document_analyses", [])
        if a["document_id"] != result.document_id
    ]
    existing_analyses.append(result.to_dict())
    raw["document_analyses"] = existing_analyses

    json_file = data_path / f"{period_key}.json"
    json_file.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@dataclass
class WorkItem:
    """One document selected for analysis, with its shared-NF group context."""

    period: str
    document: dict
    entry: dict
    raw: dict
    group_key: str
    sibling_sum: float  # sum of entry amounts over the FULL group (pre-filter)
    group_size: int


def select_work(
    periods,
    *,
    min_amount: float | None = None,
    limit: int | None = None,
    reanalyze: bool = False,
    document_ids: list[str] | None = None,
    entry_ids: list[str] | None = None,
) -> list[WorkItem]:
    """Select documents to analyze, grouped by byte-identical NF content.

    The single source of truth for "what to analyze", shared by the legacy VLM
    runner and the agent-flow planner. Applies the id/min-amount filters and
    skip-already-analyzed (unless ``reanalyze`` or specific ids are targeted),
    computes each group's FULL sibling sum + size (so a sibling dropped by a
    filter still counts toward reconciliation), sorts by entry amount descending,
    and truncates to ``limit``.
    """
    document_id_filter = set(document_ids) if document_ids else None
    entry_id_filter = set(entry_ids) if entry_ids else None
    targeted = document_id_filter is not None or entry_id_filter is not None

    work: list[WorkItem] = []
    for period_key, period_data in periods.items():
        entry_map = {e["id"]: e for e in period_data.entries}
        # Targeting specific ids implies reanalyze for them, so they are never
        # skipped as "already analyzed".
        existing = set()
        if not reanalyze and not targeted:
            existing = {a["document_id"] for a in period_data.raw.get("document_analyses", [])}

        with_path = [d for d in period_data.documents if d.get("file_path")]
        groups = group_documents(with_path)
        group_of: dict[str, str] = {}
        group_sum: dict[str, float] = {}
        group_size: dict[str, int] = {}
        for gkey, gdocs in groups.items():
            group_size[gkey] = len(gdocs)
            total = 0.0
            for gdoc in gdocs:
                group_of[gdoc["id"]] = gkey
                gentry = entry_map.get(gdoc["entry_id"])
                if gentry:
                    total += gentry["amount"]
            group_sum[gkey] = total

        for doc in period_data.documents:
            if not doc.get("file_path"):
                continue
            if document_id_filter is not None and doc["id"] not in document_id_filter:
                continue
            if entry_id_filter is not None and doc["entry_id"] not in entry_id_filter:
                continue
            if doc["id"] in existing:
                continue
            entry = entry_map.get(doc["entry_id"])
            if not entry:
                continue
            if min_amount and entry["amount"] < min_amount:
                continue
            gkey = group_of[doc["id"]]
            work.append(
                WorkItem(period_key, doc, entry, period_data.raw, gkey, group_sum[gkey], group_size[gkey])
            )

    work.sort(key=lambda w: w.entry["amount"], reverse=True)
    if limit:
        work = work[:limit]
    return work


def summarize_results(results: list["DocAnalysisResult"]) -> None:
    """Print the document-analysis summary + mismatch list to stdout."""
    analyzed = [r for r in results if not r.error]
    errors = [r for r in results if r.error]
    amount_ok = sum(1 for r in analyzed if r.amount_match is True)
    amount_bad = sum(1 for r in analyzed if r.amount_match is False)
    vendor_ok = sum(1 for r in analyzed if r.vendor_match is True)
    vendor_bad = sum(1 for r in analyzed if r.vendor_match is False)

    print(f"\nDocument Analysis Complete: {len(analyzed)}/{len(results)} analyzed")
    if errors:
        print(f"  Errors: {len(errors)}")
    print(f"  Amount:  {amount_ok} OK, {amount_bad} mismatch")
    print(f"  Vendor:  {vendor_ok} OK, {vendor_bad} mismatch")

    if amount_bad or vendor_bad:
        print("\nMismatches:")
        for r in analyzed:
            flags = []
            if r.amount_match is False:
                entry_amt = f"R${r.entry_amount:.2f}" if r.entry_amount is not None else "?"
                doc_amt = f"R${r.extracted_amount:.2f}" if r.extracted_amount is not None else "?"
                flags.append(f"amount: entry {entry_amt} vs doc {doc_amt}")
            if r.vendor_match is False:
                flags.append(f"vendor: '{r.issuer_name}'")
            if flags:
                print(f"  Doc {r.document_id[:8]}: {', '.join(flags)}")
