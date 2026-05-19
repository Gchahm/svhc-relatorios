import asyncio
import json
import logging
import re
import time
import uuid
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .browser import BRCondosBrowser
from .config import ACCOUNTABILITY_PATH, BRCONDOS_URL
from .extractors.aprovadores import extract_aprovadores
from .extractors.demonstrativo import extract_demonstrativo
from .extractors.documentos import download_entry_documents
from .extractors.lancamentos import extract_all_lancamentos
from .extractors.periodos import list_periodos

logger = logging.getLogger(__name__)

# Fixed namespace for deterministic UUIDs on reference data
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "svhc.fiscal")

_BLOCO_PATTERN = re.compile(r"BLOCO ([A-Z]), N° (\d+)")
_FORNECEDOR_PATTERN = re.compile(r"^(.+?) - PAGAMENTO")
_STRIP_FORNECEDOR = re.compile(r"^.* - PAGAMENTO\s*")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 5


# ─── Deterministic UUID helpers ──────────────────────────────────────────────

def _det_id(*parts: str) -> str:
    """Generate a deterministic UUID from string parts."""
    return str(uuid.uuid5(NAMESPACE, ":".join(parts)))


def _category_id(name: str) -> str:
    return _det_id("category", name)


def _subcategory_id(category_id: str, name: str) -> str:
    return _det_id("subcategory", category_id, name)


def _vendor_id(name: str) -> str:
    return _det_id("vendor", name)


def _unit_id(code: str) -> str:
    return _det_id("unit", code)


def _report_id(period: str) -> str:
    return _det_id("report", period)


def _entry_id(period: str, date_str: str, description: str, amount: float, subcategory_id: str, index: int) -> str:
    return _det_id("entry", period, date_str, description, str(amount), subcategory_id, str(index))


def _document_id(entry_id: str, external_document_id: int) -> str:
    return _det_id("document", entry_id, str(external_document_id))


def _subtotal_id(period: str, subcategory_id: str, movement_type: str) -> str:
    return _det_id("subtotal", period, subcategory_id, movement_type)


def _approver_id(period: str, name: str) -> str:
    return _det_id("approver", period, name)


def _random_id() -> str:
    return str(uuid.uuid4())


# ─── Text helpers ────────────────────────────────────────────────────────────

def _now_ms() -> int:
    return int(datetime.now().timestamp() * 1000)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _strip_fornecedor_prefix(descricao: str) -> str:
    if " - PAGAMENTO" not in descricao:
        return descricao
    cleaned = _STRIP_FORNECEDOR.sub("", descricao)
    cleaned = re.sub(r"^[\s\-]+", "", cleaned)
    return cleaned or descricao


def _consolidate_subtotais(subtotais_data: list[dict]) -> list[dict]:
    grouped: dict[tuple, float] = defaultdict(float)
    meta: dict[tuple, dict] = {}
    for sub in subtotais_data:
        key = (sub["categoria"], sub["subcategoria"], sub["tipo_movimento"])
        grouped[key] += sub["valor"]
        meta[key] = sub
    consolidated = []
    for key, total in grouped.items():
        entry = meta[key].copy()
        entry["valor"] = round(total, 2)
        consolidated.append(entry)
    if len(consolidated) < len(subtotais_data):
        logger.info(
            "  Consolidated subtotais: %d -> %d (merged %d duplicates)",
            len(subtotais_data), len(consolidated), len(subtotais_data) - len(consolidated),
        )
    return consolidated


# ─── Entity resolution (deterministic UUIDs) ─────────────────────────────────

class RefStore:
    """Resolves reference entities to deterministic UUIDs, collecting unique records."""

    def __init__(self):
        self.categories: dict[str, dict] = {}       # id -> record
        self.subcategories: dict[str, dict] = {}     # id -> record
        self.vendors: dict[str, dict] = {}           # id -> record
        self.units: dict[str, dict] = {}             # id -> record

    def resolve_subcategory(self, categoria: str, subcategoria: str, movement_type: str) -> str:
        cat_name = _normalize_whitespace(categoria)
        sub_name = _normalize_whitespace(subcategoria)

        cat_id = _category_id(cat_name)
        if cat_id not in self.categories:
            self.categories[cat_id] = {"id": cat_id, "name": cat_name, "movement_type": movement_type}

        sub_id = _subcategory_id(cat_id, sub_name)
        if sub_id not in self.subcategories:
            self.subcategories[sub_id] = {"id": sub_id, "category_id": cat_id, "name": sub_name}
        return sub_id

    def resolve_vendor(self, descricao: str) -> str | None:
        m = _FORNECEDOR_PATTERN.search(descricao)
        if not m:
            return None
        name = _normalize_whitespace(m.group(1))
        vid = _vendor_id(name)
        if vid not in self.vendors:
            self.vendors[vid] = {"id": vid, "name": name}
        return vid

    def resolve_unit(self, descricao: str) -> str | None:
        m = _BLOCO_PATTERN.search(descricao)
        if not m:
            return None
        bloco, numero_str = m.group(1), m.group(2)
        code = f"{numero_str}{bloco}"
        uid = _unit_id(code)
        if uid not in self.units:
            self.units[uid] = {"id": uid, "block": bloco, "number": int(numero_str), "code": code}
        return uid


def _build_period_data(
    refs: RefStore,
    scrape_run: dict,
    report: dict,
    entries: list[dict],
    category_subtotals: list[dict],
    approvers: list[dict],
    documents: list[dict],
) -> dict:
    """Build the JSON structure for a single period file."""
    return {
        "scrape_runs": [scrape_run],
        "categories": list(refs.categories.values()),
        "vendors": list(refs.vendors.values()),
        "units": list(refs.units.values()),
        "subcategories": list(refs.subcategories.values()),
        "accountability_reports": [report],
        "entries": entries,
        "category_subtotals": category_subtotals,
        "approvers": approvers,
        "documents": documents,
        "document_analyses": [],
        "alerts": [],
    }


async def run_scrape(
    output_dir: str,
    book_ids: list[int] | None = None,
    periodos_filter: list[str] | None = None,
    download_docs: bool = False,
) -> None:
    """Run a full scrape, writing one JSON file per period.

    Args:
        output_dir: Directory to write period JSON files.
        book_ids: Specific accountability book IDs to scrape.
        periodos_filter: Specific periods to scrape (e.g. ["2026-01"]).
        download_docs: Whether to download document files.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Determine already-scraped periods from existing files
    existing_periods = {p.stem for p in out_path.glob("*.json") if p.stem != "_run"}

    run_id = _random_id()
    scrape_run = {
        "id": run_id,
        "executed_at": _now_ms(),
        "status": "running",
        "errors": None,
        "duration_seconds": None,
    }

    browser = BRCondosBrowser()
    start = time.time()
    errors = []
    scraped_count = 0

    try:
        await browser.start()
        await browser.login()
        await browser.navigate_to_accountability()
        all_periodos = await list_periodos(browser.page)

        periodos = _filter_periodos(all_periodos, book_ids, periodos_filter, existing_periods)

        if not periodos:
            logger.info("No periods to scrape")
        else:
            logger.info(
                "Will scrape %d period(s): %s",
                len(periodos), ", ".join(p["label"] for p in periodos),
            )

        for i, periodo_info in enumerate(periodos, 1):
            label = periodo_info["label"]
            periodo = periodo_info["periodo"]
            logger.info("[%d/%d] Scraping %s...", i, len(periodos), label)

            last_error = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    period_data = await _scrape_periodo(
                        browser, periodo_info, scrape_run, download_docs, out_path
                    )
                    # Write period file immediately to free memory
                    period_file = out_path / f"{periodo}.json"
                    period_file.write_text(json.dumps(period_data, ensure_ascii=False, indent=2))

                    scraped_count += 1
                    logger.info("[%d/%d] %s done -> %s", i, len(periodos), label, period_file)
                    last_error = None
                    break
                except Exception as e:
                    last_error = e
                    if attempt < MAX_RETRIES:
                        delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                        logger.warning(
                            "[%d/%d] %s attempt %d/%d failed: %s. Retrying in %ds...",
                            i, len(periodos), label, attempt, MAX_RETRIES, e, delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "[%d/%d] %s failed after %d attempts: %s",
                            i, len(periodos), label, MAX_RETRIES, e, exc_info=True,
                        )

            if last_error:
                errors.append(f"Error scraping {label}: {last_error}")
                try:
                    await browser.screenshot(f"data/error_{periodo}.png")
                except Exception:
                    pass

        scrape_run["status"] = "error" if errors else "success"
    except Exception as e:
        msg = f"Fatal error: {e}"
        logger.error(msg, exc_info=True)
        errors.append(msg)
        scrape_run["status"] = "error"
    finally:
        await browser.close()
        scrape_run["duration_seconds"] = round(time.time() - start, 2)
        scrape_run["errors"] = "\n".join(errors) if errors else None

    logger.info(
        "Scrape #%s finished: status=%s scraped=%d errors=%d duration=%.1fs",
        run_id[:8], scrape_run["status"], scraped_count, len(errors), scrape_run["duration_seconds"],
    )


def _filter_periodos(
    all_periodos: list[dict],
    book_ids: list[int] | None,
    periodos_filter: list[str] | None,
    existing_periods: set[str],
) -> list[dict]:
    if book_ids:
        return [p for p in all_periodos if p["book_id"] in book_ids]
    if periodos_filter:
        return [p for p in all_periodos if p["periodo"] in periodos_filter]
    # Default: skip periods that already have a JSON file
    return [p for p in all_periodos if p["periodo"] not in existing_periods]


async def _scrape_periodo(
    browser: BRCondosBrowser,
    periodo_info: dict,
    scrape_run: dict,
    download_docs: bool,
    output_dir: Path | None = None,
) -> dict:
    """Scrape a single period and return the JSON data dict."""
    book_id = periodo_info["book_id"]
    periodo = periodo_info["periodo"]
    now = _now_ms()
    refs = RefStore()

    await browser.navigate_to_accountability(book_id)
    source_url = f"{BRCONDOS_URL}{ACCOUNTABILITY_PATH}?q={book_id}&list=true"

    # Extract financial summary
    demonstrativo = await extract_demonstrativo(browser.page)
    logger.info(
        "  Demonstrativo: receitas=%.2f despesas=%.2f saldo=%.2f",
        demonstrativo["total_receitas"], demonstrativo["total_despesas"], demonstrativo["saldo_acumulado"],
    )

    # Extract lancamentos and subtotals
    lancamentos_data, subtotais_data = await extract_all_lancamentos(browser.page)
    logger.info("  Extracted %d lancamentos, %d subtotais", len(lancamentos_data), len(subtotais_data))

    # Normalize text fields
    for lanc in lancamentos_data:
        lanc["descricao"] = _normalize_whitespace(lanc["descricao"])
        lanc["categoria"] = _normalize_whitespace(lanc["categoria"])
        lanc["subcategoria"] = _normalize_whitespace(lanc["subcategoria"])
    for sub in subtotais_data:
        sub["categoria"] = _normalize_whitespace(sub["categoria"])
        sub["subcategoria"] = _normalize_whitespace(sub["subcategoria"])

    subtotais_data = _consolidate_subtotais(subtotais_data)
    aprovadores_data = await extract_aprovadores(browser.page)

    # Build report
    report_id = _report_id(periodo)
    report = {
        "id": report_id,
        "scrape_run_id": scrape_run["id"],
        "period": periodo,
        "external_book_id": book_id,
        "total_revenue": demonstrativo["total_receitas"],
        "total_expenses": demonstrativo["total_despesas"],
        "opening_balance": demonstrativo["saldo_inicial"],
        "month_balance": demonstrativo["saldo_mes"],
        "accumulated_balance": demonstrativo["saldo_acumulado"],
        "source_url": source_url,
        "created_at": now,
        "updated_at": now,
    }

    # Build entries and document refs
    entries_out = []
    documents_out = []
    doc_download_tasks = []
    entry_key_counts: dict[tuple, int] = defaultdict(int)  # track duplicates for deterministic IDs
    for lanc in lancamentos_data:
        raw_descricao = lanc["descricao"]
        description = _strip_fornecedor_prefix(raw_descricao)
        documento_ids = lanc.get("documento_ids") or []
        # Backward compat: single documento_id field
        if not documento_ids and lanc.get("documento_id"):
            documento_ids = [lanc["documento_id"]]

        subcategory_id = refs.resolve_subcategory(
            lanc["categoria"], lanc["subcategoria"], lanc["tipo_movimento"]
        )
        date_str = lanc["data"].isoformat()

        # Occurrence index handles entries with identical natural keys
        natural_key = (date_str, description, lanc["valor"], subcategory_id)
        entry_key_counts[natural_key] += 1
        entry_id = _entry_id(periodo, date_str, description, lanc["valor"], subcategory_id, entry_key_counts[natural_key])

        entries_out.append({
            "id": entry_id,
            "report_id": report_id,
            "date": date_str,
            "description": description,
            "amount": lanc["valor"],
            "movement_type": lanc["tipo_movimento"],
            "subcategory_id": subcategory_id,
            "unit_id": refs.resolve_unit(raw_descricao),
            "vendor_id": refs.resolve_vendor(raw_descricao),
            "external_document_id": documento_ids[0] if documento_ids else None,
            "source_url": source_url,
            "created_at": now,
            "updated_at": now,
        })

        if documento_ids:
            entry_doc_records = []
            for ext_doc_id in documento_ids:
                doc_id = _document_id(entry_id, ext_doc_id)
                doc_record = {
                    "id": doc_id,
                    "entry_id": entry_id,
                    "external_document_id": ext_doc_id,
                    "file_path": None,
                }
                documents_out.append(doc_record)
                entry_doc_records.append(doc_record)
            doc_download_tasks.append((entry_id, documento_ids, entry_doc_records))

    # Build category subtotals
    subtotals_out = []
    for sub in subtotais_data:
        sub_id = refs.resolve_subcategory(
            sub["categoria"], sub["subcategoria"], sub["tipo_movimento"]
        )
        subtotals_out.append({
            "id": _subtotal_id(periodo, sub_id, sub["tipo_movimento"]),
            "report_id": report_id,
            "subcategory_id": sub_id,
            "amount": sub["valor"],
            "movement_type": sub["tipo_movimento"],
            "created_at": now,
            "updated_at": now,
        })

    # Build approvers
    approvers_out = []
    for aprov in aprovadores_data:
        name = _normalize_whitespace(aprov["nome"])
        approvers_out.append({
            "id": _approver_id(periodo, name),
            "report_id": report_id,
            "name": name,
            "status": aprov["status"],
        })

    # Download documents
    if download_docs and doc_download_tasks:
        total_docs = sum(len(ids) for _, ids, _ in doc_download_tasks)
        logger.info("  Downloading %d documents for %d entries...", total_docs, len(doc_download_tasks))

        dest_dir = output_dir / periodo if output_dir else Path(f"data/scrape/{periodo}")
        downloaded = 0
        for entry_id, documento_ids, doc_records in doc_download_tasks:
            paths_by_id = await download_entry_documents(
                browser.page, documento_ids, entry_id, dest_dir
            )
            for doc_record in doc_records:
                ext_id = doc_record["external_document_id"]
                if ext_id in paths_by_id:
                    doc_record["file_path"] = ";".join(paths_by_id[ext_id])
                    downloaded += 1
        logger.info("  Documents saved: %d/%d", downloaded, total_docs)

    logger.info(
        "  Period %s: %d entries, %d subtotals, %d approvers, %d docs",
        periodo, len(entries_out), len(subtotals_out), len(approvers_out), len(documents_out),
    )

    return _build_period_data(
        refs, scrape_run, report, entries_out, subtotals_out, approvers_out, documents_out
    )


async def run_download_docs(
    data_dir: str,
    periodos_filter: list[str] | None = None,
) -> None:
    """Download documents for existing scraped JSON files.

    Reads each period JSON, downloads documents that don't have a file_path yet,
    and updates the JSON files in-place.

    Args:
        data_dir: Directory containing period JSON files (e.g. data/scrape).
        periodos_filter: Only process these periods (e.g. ["2024-12"]).
    """
    data_path = Path(data_dir)
    json_files = sorted(data_path.glob("*.json"))

    if periodos_filter:
        json_files = [f for f in json_files if f.stem in periodos_filter]

    if not json_files:
        logger.info("No JSON files found in %s", data_path)
        return

    # Build work list: figure out which files have documents to download
    work = []
    for json_file in json_files:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        docs = data.get("documents", [])
        pending = [d for d in docs if not d.get("file_path")]
        if not pending:
            logger.info("%s: all %d documents already downloaded, skipping", json_file.stem, len(docs))
            continue

        work.append((json_file, data, pending))
        logger.info("%s: %d/%d documents to download", json_file.stem, len(pending), len(docs))

    if not work:
        logger.info("All documents already downloaded")
        return

    total_pending = sum(len(pending) for _, _, pending in work)
    logger.info("Will download %d documents across %d period(s)", total_pending, len(work))

    browser = BRCondosBrowser()
    try:
        await browser.start()
        await browser.login()

        for json_file, data, pending in work:
            periodo = json_file.stem
            dest_dir = data_path / periodo
            logger.info("Processing %s (%d documents)...", periodo, len(pending))

            # Group pending docs by entry_id for batch downloading
            by_entry: dict[str, list[dict]] = defaultdict(list)
            for doc in pending:
                by_entry[doc["entry_id"]].append(doc)

            downloaded = 0
            for entry_id, entry_docs in by_entry.items():
                ext_doc_ids = [d["external_document_id"] for d in entry_docs]

                paths_by_id = await download_entry_documents(
                    browser.page, ext_doc_ids, entry_id, dest_dir
                )

                for doc in entry_docs:
                    ext_id = doc["external_document_id"]
                    if ext_id in paths_by_id:
                        doc["file_path"] = ";".join(paths_by_id[ext_id])
                        downloaded += 1

            # Write updated JSON back
            json_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("%s: downloaded %d/%d documents", periodo, downloaded, len(pending))

    except Exception as e:
        logger.error("Fatal error during document download: %s", e, exc_info=True)
    finally:
        await browser.close()
