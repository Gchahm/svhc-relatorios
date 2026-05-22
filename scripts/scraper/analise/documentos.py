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
Extract the following information as JSON:

{
  "tipo_documento": "NF-e" or "DANFE" or "boleto" or "recibo" or "comprovante" or "outro",
  "valor_total": numeric total value (use null if not found),
  "cnpj_emitente": "XX.XXX.XXX/XXXX-XX" (use null if not found),
  "nome_emitente": "company name" (use null if not found),
  "data_emissao": "DD/MM/YYYY" (use null if not found),
  "numero_documento": "document number" (use null if not found),
  "descricao_servico": "brief description of service/product" (use null if not found)
}

Return ONLY the JSON, no other text."""


@dataclass
class DocAnalysisResult:
    document_id: str
    entry_id: str
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
    raw_response: str | None = None
    error: str | None = None

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


def analyze_single_document(
    file_path: str,
    entry_amount: float,
    vendor_name: str | None,
    period: str,
    document_id: str,
    entry_id: str,
) -> DocAnalysisResult:
    """Analyze a single document image with VLM and validate against entry data."""
    result = DocAnalysisResult(
        document_id=document_id,
        entry_id=entry_id,
    )

    # Get the first page path (multi-page docs have paths joined by ";")
    first_path = file_path.split(";")[0]
    if not pathlib.Path(first_path).exists():
        result.error = f"file not found: {first_path}"
        return result

    try:
        model, processor = _load_model()

        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template

        formatted_prompt = apply_chat_template(
            processor,
            config=model.config,
            prompt=EXTRACT_PROMPT,
            images=[first_path],
            num_images=1,
        )

        result_obj = generate(
            model,
            processor,
            formatted_prompt,
            image=first_path,
            max_tokens=500,
            verbose=False,
        )
        response = result_obj.text if hasattr(result_obj, "text") else str(result_obj)
        result.raw_response = response

        data = _parse_vlm_response(response)
        if not data:
            result.error = "failed to parse VLM response"
            return result

        # Populate extracted fields
        result.document_type = data.get("tipo_documento")
        result.extracted_amount = _parse_brl_value(data.get("valor_total"))
        result.extracted_cnpj = data.get("cnpj_emitente")
        result.issuer_name = data.get("nome_emitente")
        result.extracted_date = data.get("data_emissao")
        result.document_number = data.get("numero_documento")
        result.service_description = data.get("descricao_servico")

        # Validate: amount match (5% tolerance)
        if result.extracted_amount is not None and entry_amount > 0:
            diff_pct = abs(result.extracted_amount - entry_amount) / entry_amount
            result.amount_match = diff_pct < 0.05

        # Validate: vendor name match (fuzzy)
        if result.issuer_name and vendor_name:
            a = _normalize_name(result.issuer_name)
            b = _normalize_name(vendor_name)
            result.vendor_match = a in b or b in a

        # Validate: date within period
        result.date_match = _check_date_in_period(result.extracted_date, period)

    except Exception as e:
        result.error = str(e)
        logger.warning("VLM analysis failed for doc %s: %s", document_id[:8], e)

    return result


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

    results: list[DocAnalysisResult] = []
    # Group by period for writing back
    results_by_period: dict[str, list[DocAnalysisResult]] = {}

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
        results_by_period.setdefault(period_key, []).append(result)

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

    # Write results back to JSON files
    data_path = Path(data_dir)
    for period_key, period_results in results_by_period.items():
        raw = periods[period_key].raw
        existing_analyses = raw.get("document_analyses", [])
        existing_ids = {a["document_id"] for a in existing_analyses}

        for result in period_results:
            analysis_dict = result.to_dict()
            if result.document_id in existing_ids:
                # Replace existing
                existing_analyses = [
                    a for a in existing_analyses if a["document_id"] != result.document_id
                ]
            existing_analyses.append(analysis_dict)

        raw["document_analyses"] = existing_analyses

        json_file = data_path / f"{period_key}.json"
        json_file.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("%s: %d analyses written", period_key, len(period_results))

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
                flags.append(f"amount: entry R${r.extracted_amount:.2f} vs doc R${r.extracted_amount:.2f}")
            if r.vendor_match is False:
                flags.append(f"vendor: '{r.issuer_name}'")
            if flags:
                print(f"  Doc {r.document_id[:8]}: {', '.join(flags)}")
