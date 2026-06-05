"""Document analysis using Vision Language Model.

Extracts structured data from receipt/invoice images and validates
against entry data to detect mismatches and potential fraud.
"""

import json
import logging
import pathlib
import re
from dataclasses import dataclass, field
from datetime import date

from ..utils import det_id, now_ms

logger = logging.getLogger(__name__)

_model = None
_processor = None


def _load_model():
    """Lazy-load the VLM model on first use."""
    global _model, _processor
    if _model is not None:
        return _model, _processor

    from mlx_vlm import load

    model_name = "mlx-community/Qwen2.5-VL-7B-Instruct-8bit"
    logger.info("Loading VLM model: %s", model_name)
    _model, _processor = load(model_name)
    logger.info("VLM model loaded")
    return _model, _processor


EXTRACT_PROMPT = """Analyze this fiscal document image (Brazilian receipt/invoice/DANFE/boleto).
This is ONE page of a document; classify what THIS page is and extract its values.
Extract the following information as JSON:

{
  "papel_artefato": "invoice" or "nfse" or "boleto" or "payment_proof" or "other",
  "tipo_documento": "NF-e" or "DANFE" or "boleto" or "recibo" or "comprovante" or "outro",
  "valor_total": numeric gross/total value (use null if not found),
  "valor_liquido": numeric net value after retentions (ISS/INSS/IR) (use null if not present),
  "valor_pago": numeric amount actually paid, for payment proofs (use null if not a payment artifact),
  "cnpj_emitente": "XX.XXX.XXX/XXXX-XX" (use null if not found),
  "nome_emitente": "company name" (use null if not found),
  "data_emissao": "DD/MM/YYYY" (use null if not found),
  "numero_documento": "document number" (use null if not found),
  "descricao_servico": "brief description of service/product" (use null if not found)
}

Return ONLY the JSON, no other text."""


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


def _parse_vlm_response(text: str) -> dict | None:
    """Extract JSON from VLM response, handling markdown fences."""
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


def _normalize_name(s: str) -> str:
    """Normalize a name for fuzzy comparison."""
    from unicodedata import normalize, category
    s = normalize("NFD", s)
    s = "".join(c for c in s if category(c) != "Mn")
    return s.upper().strip()


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

    Prefers the explicit `papel_artefato`; falls back to `tipo_documento`.
    Returns one of invoice/nfse/boleto/payment_proof/other.
    """
    valid = {"invoice", "nfse", "boleto", "payment_proof", "other"}
    role = str(parsed.get("papel_artefato") or "").strip().lower()
    if role in valid:
        return role
    if role in _ROLE_ALIASES:
        return _ROLE_ALIASES[role]
    tipo = str(parsed.get("tipo_documento") or "").strip().lower()
    return _ROLE_ALIASES.get(tipo, "other")


def _analyze_page(model, processor, path: str) -> tuple[dict | None, str, str | None]:
    """Run one VLM pass on a single image.

    Returns (parsed_dict | None, raw_text, error | None). A failure here never
    raises — the caller records it per page and continues with the next page.
    """
    try:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted_prompt = apply_chat_template(
            processor,
            config=model.config,
            prompt=EXTRACT_PROMPT,
            images=[path],
            num_images=1,
        )
        result_obj = generate(
            model,
            processor,
            formatted_prompt,
            image=path,
            max_tokens=500,
            verbose=False,
        )
        raw_text = result_obj.text if hasattr(result_obj, "text") else str(result_obj)
    except Exception as e:  # noqa: BLE001 - one bad page must not abort the document
        return None, "", str(e)

    parsed = _parse_vlm_response(raw_text)
    if parsed is None:
        return None, raw_text, "failed to parse VLM response"
    return parsed, raw_text, None


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
    result.issuer_name = first_field("nome_emitente")
    result.extracted_date = first_field("data_emissao")
    result.document_number = first_field("numero_documento")
    result.service_description = first_field("descricao_servico")

    # Amount precedence: payment_proof paid -> boleto -> invoice net -> gross.
    def pick(records, *keys):
        for r in records:
            for key in keys:
                val = _parse_brl_value(r.response.get(key))
                if val is not None:
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


def analyze_single_document(
    file_path: str,
    entry_amount: float,
    vendor_name: str | None,
    period: str,
    document_id: str,
    entry_id: str,
) -> DocAnalysisResult:
    """Analyze every page of a document with the VLM and validate against entry data.

    Runs one VLM pass per page image (paths joined by ";"), emits one
    page_extraction record per page, then derives the document-level roll-up
    across all pages. A missing/unreadable or unparseable page is recorded and
    skipped — it does not abort the document.
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

    try:
        model, processor = _load_model()
    except Exception as e:
        result.error = f"failed to load model: {e}"
        logger.warning("VLM model load failed for doc %s: %s", document_id[:8], e)
        return result

    multipage = len(paths) > 1
    any_success = False
    for idx, path in enumerate(paths):
        page_label = _page_label_from_path(path, idx)
        record = PageAnalysisRecord(
            document_analysis_id=doc_analysis_id,
            page_index=idx,
            page_label=page_label,
        )

        if not pathlib.Path(path).exists():
            record.parse_error = f"file not found: {path}"
            result.records.append(record)
            continue

        # One VLM call per page; log progress so multi-page docs don't look stuck.
        if multipage:
            logger.info("    page %d/%d (%s)...", idx + 1, len(paths), page_label)

        parsed, raw_text, error = _analyze_page(model, processor, path)
        record.raw_text = raw_text or None
        if parsed is None:
            record.parse_error = error or "failed to parse VLM response"
        else:
            record.response = parsed
            record.artifact_role = _map_artifact_role(parsed)
            any_success = True
        result.records.append(record)

    if not any_success:
        result.error = "no page produced a parseable response"
        logger.warning("VLM analysis produced no parseable page for doc %s", document_id[:8])
        return result

    # Roll up document-level fields from the per-page records (heterogeneity-aware).
    _rollup_document_fields(result)

    # Validate against the entry on the rolled-up fields (existing tolerances).
    if result.extracted_amount is not None and entry_amount > 0:
        diff_pct = abs(result.extracted_amount - entry_amount) / entry_amount
        result.amount_match = diff_pct < 0.05

    if result.issuer_name and vendor_name:
        a = _normalize_name(result.issuer_name)
        b = _normalize_name(vendor_name)
        result.vendor_match = a in b or b in a

    result.date_match = _check_date_in_period(result.extracted_date, period)

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


def run_document_analysis(
    data_dir: str,
    periods_filter: list[str] | None = None,
    limit: int | None = None,
    min_amount: float | None = None,
    reanalyze: bool = False,
) -> None:
    """Analyze document images for scraped periods.

    Reads period JSONs, finds documents with file_path set,
    runs VLM analysis, and writes results to document_analyses in the JSON.
    """
    from pathlib import Path

    from .loader import load_all_periods

    periods, refs = load_all_periods(data_dir, periods_filter)
    if not periods:
        logger.info("No periods to analyze")
        return

    # Collect documents to analyze
    work: list[tuple[str, dict, dict, dict]] = []  # (period, doc, entry, period_data.raw)
    for period_key, period_data in periods.items():
        # Build entry lookup
        entry_map = {e["id"]: e for e in period_data.entries}
        # Build existing analyses set
        existing = set()
        if not reanalyze:
            existing = {a["document_id"] for a in period_data.raw.get("document_analyses", [])}

        for doc in period_data.documents:
            if not doc.get("file_path"):
                continue
            if doc["id"] in existing:
                continue
            entry = entry_map.get(doc["entry_id"])
            if not entry:
                continue
            if min_amount and entry["amount"] < min_amount:
                continue
            work.append((period_key, doc, entry, period_data.raw))

    # Sort by amount descending (analyze most expensive first)
    work.sort(key=lambda x: x[2]["amount"], reverse=True)

    if limit:
        work = work[:limit]

    if not work:
        logger.info("No documents to analyze")
        return

    logger.info("Will analyze %d document(s)", len(work))

    data_path = Path(data_dir)
    results: list[DocAnalysisResult] = []

    for i, (period_key, doc, entry, raw) in enumerate(work, 1):
        vendor_name = None
        if entry.get("vendor_id"):
            vendor_name = refs.vendor_name(entry["vendor_id"])

        logger.info(
            "[%d/%d] Analyzing doc %s (R$ %.2f, %s)...",
            i, len(work), doc["id"][:8], entry["amount"],
            entry["description"][:40],
        )

        result = analyze_single_document(
            file_path=doc["file_path"],
            entry_amount=entry["amount"],
            vendor_name=vendor_name,
            period=period_key,
            document_id=doc["id"],
            entry_id=entry["id"],
        )
        results.append(result)

        # Write back immediately so partial results are inspectable mid-run
        # and survive an interruption.
        _merge_and_write(data_path, period_key, raw, result)

        # Log status
        status = []
        if result.amount_match is not None:
            status.append(f"amount={'OK' if result.amount_match else 'MISMATCH'}")
        if result.vendor_match is not None:
            status.append(f"vendor={'OK' if result.vendor_match else 'MISMATCH'}")
        if result.date_match is not None:
            status.append(f"date={'OK' if result.date_match else 'MISMATCH'}")
        if result.error:
            status.append(f"error={result.error}")
        logger.info("  -> %s %s", result.document_type or "?", " | ".join(status))

    # Print summary
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
