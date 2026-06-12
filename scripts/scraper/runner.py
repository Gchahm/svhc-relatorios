import asyncio
import logging
import re
import time
import uuid
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .browser import BRCondosBrowser
from .config import ACCOUNTABILITY_PATH, BRCONDOS_URL
from .consistency import ALERT_TYPE as _CONSISTENCY_ALERT_TYPE, build_consistency_writeback
from .extractors.aprovadores import extract_aprovadores
from .extractors.demonstrativo import extract_demonstrativo
from .extractors.documentos import download_entry_documents
from .extractors.lancamentos import extract_all_lancamentos
from .extractors.periodos import list_periodos
from .preserve import preserve_existing_attachment_cols
from .reconcile import ALERT_TYPE as _VANISHED_ALERT_TYPE, ExistingRows, ScrapedIds, build_reconciliation

from common import det_id as _det_id, now_ms as _now_ms
from common import d1
from common.d1 import Target
from common.hashing import content_hash

DEFAULT_CACHE_DIR = "../.cache/analysis"

logger = logging.getLogger(__name__)

_BLOCO_PATTERN = re.compile(r"BLOCO ([A-Z]), N° (\d+)")
_FORNECEDOR_PATTERN = re.compile(r"^(.+?) - PAGAMENTO")
_STRIP_FORNECEDOR = re.compile(r"^.* - PAGAMENTO\s*")

MAX_RETRIES = 3
RETRY_BASE_DELAY = 5


# ─── Deterministic UUID helpers ──────────────────────────────────────────────

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


def _attachment_id(entry_id: str, external_document_id: int) -> str:
    return _det_id("attachment", entry_id, str(external_document_id))


def _subtotal_id(period: str, subcategory_id: str, movement_type: str) -> str:
    return _det_id("subtotal", period, subcategory_id, movement_type)


def _approver_id(period: str, name: str) -> str:
    return _det_id("approver", period, name)


def _random_id() -> str:
    return str(uuid.uuid4())


# ─── Text helpers ────────────────────────────────────────────────────────────


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
    attachments: list[dict],
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
        "attachments": attachments,
        "attachment_analyses": [],
        "alerts": [],
    }


def _upload_pages_to_r2(local_paths: list[str], periodo: str, target: Target) -> list[str]:
    """Upload each downloaded page to R2 at key ``<period>/<basename>``; return the keys.

    The returned keys are what gets stored in ``attachments.file_path`` (R2-key form), which
    ``src/lib/r2.ts:objectKeyFromFilePath()`` resolves back to the same key for the frontend.
    """
    keys: list[str] = []
    for path in local_paths:
        name = Path(path).name
        key = f"{periodo}/{name}"
        d1.put_object(key, path, d1.content_type_for(name), target=target)
        keys.append(key)
    return keys


async def run_scrape(
    target: Target = "local",
    book_ids: list[int] | None = None,
    periodos_filter: list[str] | None = None,
    download_docs: bool = False,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> None:
    """Run a full scrape, writing each period's rows straight into D1 (+ images to R2).

    Args:
        target: D1/R2 target — "local" (default) or "remote".
        book_ids: Specific accountability book IDs to scrape.
        periodos_filter: Specific periods to scrape (e.g. ["2026-01"]).
        download_docs: Whether to download attachment images (uploaded to R2 during the run).
        cache_dir: Ephemeral local scratch for downloaded images before upload (never the data folder).
    """
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    logger.info("Scrape target: %s", "REMOTE (production)" if target == "remote" else "local")

    # Determine already-scraped periods from D1 (replaces the old on-disk JSON glob)
    existing_periods = {
        row["period"] for row in d1.query("SELECT period FROM accountability_reports", target=target)
    }

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
    # Consistency mismatches are NOT fatal scrape errors — kept in a separate accumulator so they are
    # recorded on the run's `errors` field (queryable) WITHOUT flipping `status` to "error" (IMP-002).
    consistency_notes = []
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
                        browser, periodo_info, scrape_run, download_docs, cache_path, target
                    )
                    # Pop the non-fatal row-level parse-skip notes BEFORE the upsert/reconcile see the
                    # dict (feature 030 / IMP-001) — they are recorded as queryable run notes (IMP-002
                    # channel) but never enter D1 or the reconciliation id sets.
                    period_parse_notes = period_data.pop("_parse_notes", [])
                    # Upsert the period's ledger rows straight into D1 (idempotent INSERT OR REPLACE).
                    counts = d1.upsert_tables(period_data, target=target)
                    summary = ", ".join(f"{t}={n}" for t, n in counts.items())

                    # Make the re-scrape AUTHORITATIVE (BUG-004 / issue #35): rows removed from the
                    # portal since a prior scrape must leave the mirror. Runs ONLY here, on the
                    # scrape-success path, so a failed/retried period never reconciles (FR-008).
                    _reconcile_period(periodo, period_data, target)

                    # Scrape-time consistency validation (IMP-002 / issue #39): cross-check the
                    # period's three views of the money (entries vs subtotals vs demonstrativo). Runs
                    # ONLY on the scrape-success path so a failed/empty period never falsely fires.
                    consistency_summary = _check_consistency(periodo, period_data, target)
                    if consistency_summary:
                        consistency_notes.append(f"Consistency mismatch in {label}: {consistency_summary}")

                    # Surface the row-level parse skips on the run record (queryable; non-fatal).
                    consistency_notes.extend(period_parse_notes)

                    scraped_count += 1
                    logger.info("[%d/%d] %s done -> D1 (%s): %s", i, len(periodos), label, target, summary)
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
        # `status` is driven ONLY by the fatal `errors` list (set above). Consistency notes are
        # merged into the run's `errors` text so a mismatch is queryable on the run row, but they do
        # NOT make a successful-but-inconsistent run report `status == "error"` (IMP-002 / issue #39).
        all_notes = errors + consistency_notes
        scrape_run["errors"] = "\n".join(all_notes) if all_notes else None

    logger.info(
        "Scrape #%s finished: status=%s scraped=%d errors=%d duration=%.1fs",
        run_id[:8], scrape_run["status"], scraped_count, len(errors), scrape_run["duration_seconds"],
    )


def _reconcile_period(periodo: str, period_data: dict, target: Target) -> None:
    """Hard-delete mirror rows the portal no longer returns + record the loss (BUG-004 / issue #35).

    Called after a period's upsert succeeds. Reads the period's current mirror id sets back from D1,
    diffs them against what this scrape produced (``period_data``), and — if anything vanished —
    cascade-deletes the stale mirror rows + their analysis-owned dependents and raises one idempotent
    ``critical`` ``portal_row_vanished`` alert, all in ONE atomic D1 batch (the pure diff/SQL build
    lives in ``reconcile.build_reconciliation``). The mirror tables stay an EXACT portal mirror; the
    evidence lives in the analysis-owned ``alerts`` table.
    """
    scraped = ScrapedIds(
        entry_ids={e["id"] for e in period_data.get("entries", [])},
        attachment_ids={a["id"] for a in period_data.get("attachments", [])},
        subtotal_ids={s["id"] for s in period_data.get("category_subtotals", [])},
        approver_ids={p["id"] for p in period_data.get("approvers", [])},
    )

    period_literal = periodo.replace("'", "''")
    # entries / category_subtotals / approvers hang off the period's report; attachments reach the
    # period only via entries (mirrors the preserve-step join above).
    entries = d1.query(
        "SELECT e.id, e.date, e.description, e.amount FROM entries e "
        "JOIN accountability_reports r ON e.report_id = r.id "
        f"WHERE r.period = '{period_literal}'",
        target=target,
    )
    attachments = d1.query(
        "SELECT d.id, d.entry_id FROM attachments d "
        "JOIN entries e ON d.entry_id = e.id "
        "JOIN accountability_reports r ON e.report_id = r.id "
        f"WHERE r.period = '{period_literal}'",
        target=target,
    )
    subtotal_rows = d1.query(
        "SELECT cs.id FROM category_subtotals cs "
        "JOIN accountability_reports r ON cs.report_id = r.id "
        f"WHERE r.period = '{period_literal}'",
        target=target,
    )
    approver_rows = d1.query(
        "SELECT a.id FROM approvers a "
        "JOIN accountability_reports r ON a.report_id = r.id "
        f"WHERE r.period = '{period_literal}'",
        target=target,
    )

    existing = ExistingRows(
        entries=entries,
        attachments=attachments,
        subtotal_ids={row["id"] for row in subtotal_rows},
        approver_ids={row["id"] for row in approver_rows},
    )

    # Feature-023 invariant (issue #34): the portal_row_vanished alert uses a stable per-period id and
    # re-fires on every re-scrape while rows stay vanished, so read the user's prior resolution/notes
    # for that id and graft it onto the re-emitted alert — otherwise a re-scrape silently wipes a
    # disposition the user set. The read is impure, so it lives here, not in pure build_reconciliation.
    alert_id = _det_id("alert", periodo, _VANISHED_ALERT_TYPE)  # deterministic UUID — no quotes
    prior_rows = d1.query(
        f"SELECT resolved, resolved_at, notes FROM alerts WHERE id = '{alert_id}'",
        target=target,
    )
    prior_resolution = prior_rows[0] if prior_rows else None

    result = build_reconciliation(periodo, existing, scraped, prior_resolution)
    if not result.sql:
        return
    d1.execute_sql(result.sql, target=target)

    if any(result.deleted_counts.values()):
        c = result.deleted_counts
        logger.info(
            "  Reconciled %s: deleted entries=%d attachments=%d category_subtotals=%d approvers=%d; "
            "portal_row_vanished alert raised",
            periodo, c["entries"], c["attachments"], c["category_subtotals"], c["approvers"],
        )
    else:
        logger.info("  Reconciled %s: nothing stale (mirror matches portal)", periodo)


def _check_consistency(periodo: str, period_data: dict, target: Target) -> str | None:
    """Cross-check a period's three views of the money + record any mismatch (IMP-002 / issue #39).

    Called after a period's upsert + reconciliation succeed. Reads the period's demonstrativo totals
    and rows from the in-memory ``period_data`` (no extra portal round-trip), cross-checks
    per-``(subcategory, movement_type)`` entry sums against the recorded subtotals and the subtotal
    sums-by-movement-type against the demonstrativo revenue/expense totals, and — via the pure
    ``build_consistency_writeback`` — writes one idempotent, period-scoped ``scrape_inconsistency``
    ``warning`` alert in a single atomic D1 batch (always a clearing DELETE; an INSERT only when
    inconsistent). A ledger that doesn't add up is itself a finding: a scraper bug OR tampered HTML.

    Returns a one-line summary string when the period is inconsistent (for the run-log warning + the
    ``scrape_runs.errors`` note), else ``None``. The pure detection/SQL build lives in
    ``consistency.py``; the impure prior-resolution read + ``execute_sql`` live here.
    """
    report = period_data["accountability_reports"][0]
    total_receitas = report["total_revenue"]
    total_despesas = report["total_expenses"]

    # Feature-023 invariant (issue #34): the alert uses a stable per-period id and re-fires on every
    # re-scrape while the period stays inconsistent, so read the user's prior resolution/notes for
    # that id and graft it onto the re-emitted alert (build_consistency_writeback does the graft).
    alert_id = _det_id("alert", periodo, _CONSISTENCY_ALERT_TYPE)
    prior_rows = d1.query(
        f"SELECT resolved, resolved_at, notes FROM alerts WHERE id = '{alert_id}'",
        target=target,
    )
    prior_resolution = prior_rows[0] if prior_rows else None

    result = build_consistency_writeback(
        periodo,
        period_data.get("entries", []),
        period_data.get("category_subtotals", []),
        total_receitas,
        total_despesas,
        prior_resolution,
    )
    # One atomic batch: the always-present clearing DELETE + (when inconsistent) the INSERT.
    d1.execute_sql(result.sql, target=target)

    if result.discrepancies:
        logger.warning("  Consistency mismatch in %s: %s", periodo, result.summary)
        return result.summary
    logger.info("  Consistency OK for %s (entries/subtotals/demonstrativo reconcile)", periodo)
    return None


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
    cache_dir: Path,
    target: Target,
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

    # Build entries and attachment refs
    entries_out = []
    attachments_out = []
    doc_download_tasks = []
    # Non-fatal parse-skip notes (feature 030 / IMP-001): a malformed amount cell fails its row, not
    # the period. Surfaced via the run's `errors`/notes channel (IMP-002) — NOT a status=error trigger.
    parse_notes: list[str] = []
    entry_key_counts: dict[tuple, int] = defaultdict(int)  # track duplicates for deterministic IDs
    for lanc in lancamentos_data:
        raw_descricao = lanc["descricao"]
        description = _strip_fornecedor_prefix(raw_descricao)

        # Fail the row, not the period: skip an entry whose amount cell did not parse to a finite
        # number, recording a queryable note with the offending raw text (FR-005/FR-006).
        if lanc.get("valor") is None:
            valor_raw = lanc.get("valor_raw")
            note = (
                f"Parse skipped 1 entry row in {periodo}: amount cell {valor_raw!r} "
                f"(desc {description[:60]!r})"
            )
            logger.warning(note)
            parse_notes.append(note)
            continue

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
            # Scraper-owned raw provenance (feature 030 / IMP-001): verbatim portal cell text, before
            # parsing / whitespace-normalization / fornecedor-prefix stripping. Analysis never writes
            # these (mirror invariant). Nullable for rows scraped before this feature.
            "raw_amount": lanc.get("valor_raw"),
            "raw_description": lanc.get("descricao_raw"),
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
                doc_id = _attachment_id(entry_id, ext_doc_id)
                doc_record = {
                    "id": doc_id,
                    "entry_id": entry_id,
                    "external_document_id": ext_doc_id,
                    "file_path": None,
                    # Shared-NF grouping key; filled below once pages are downloaded.
                    "content_hash": None,
                }
                attachments_out.append(doc_record)
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

    # Download attachments to the local cache, then upload each page to R2. The
    # attachment's file_path stores the R2-key tokens (`<period>/<basename>`), matching
    # objectKeyFromFilePath() in src/lib/r2.ts — nothing rests in the data folder.
    if download_docs and doc_download_tasks:
        total_docs = sum(len(ids) for _, ids, _ in doc_download_tasks)
        logger.info("  Downloading %d attachments for %d entries...", total_docs, len(doc_download_tasks))

        dest_dir = cache_dir / periodo
        downloaded = 0
        for entry_id, documento_ids, doc_records in doc_download_tasks:
            paths_by_id = await download_entry_documents(
                browser.page, documento_ids, entry_id, dest_dir
            )
            for doc_record in doc_records:
                ext_id = doc_record["external_document_id"]
                if ext_id in paths_by_id:
                    local_paths = paths_by_id[ext_id]
                    keys = _upload_pages_to_r2(local_paths, periodo, target)
                    doc_record["file_path"] = ";".join(keys)
                    # Hash the local page bytes we just downloaded (file_path stores R2
                    # keys, not local paths) so the grouping key is the same value the
                    # analysis pipeline expects from nf_groups.content_hash.
                    doc_record["content_hash"] = content_hash(";".join(local_paths))
                    downloaded += 1
        logger.info("  Attachments uploaded to R2 (%s): %d/%d", target, downloaded, total_docs)

    # BUG-001 / issue #32: a re-scrape upserts attachment rows via INSERT OR REPLACE, which would
    # reset the scraper-owned file_path/content_hash to NULL whenever this run did not (re)download
    # the pages. Preserve any existing values for attachments we are about to rewrite — read the
    # current column map for this period from D1 and carry non-NULL values into the rows whose fresh
    # value is NULL (a successful in-run download still wins). attachment_state is untouched.
    if attachments_out:
        period_literal = periodo.replace("'", "''")
        existing_rows = d1.query(
            "SELECT d.id, d.file_path, d.content_hash FROM attachments d "
            "JOIN entries e ON d.entry_id = e.id "
            "JOIN accountability_reports r ON e.report_id = r.id "
            f"WHERE r.period = '{period_literal}'",
            target=target,
        )
        existing_by_id = {row["id"]: row for row in existing_rows}
        preserve_existing_attachment_cols(attachments_out, existing_by_id)

    logger.info(
        "  Period %s: %d entries, %d subtotals, %d approvers, %d docs",
        periodo, len(entries_out), len(subtotals_out), len(approvers_out), len(attachments_out),
    )

    period_data = _build_period_data(
        refs, scrape_run, report, entries_out, subtotals_out, approvers_out, attachments_out
    )
    # Non-table key carrying row-level parse-skip notes (feature 030 / IMP-001). `upsert_tables`
    # iterates TABLE_ORDER and ignores it, but `run_scrape` pops it so it never leaks into the
    # upsert or reconciliation id sets; the notes are merged into the run's queryable notes channel.
    if parse_notes:
        period_data["_parse_notes"] = parse_notes
    return period_data


async def run_download_docs(
    target: Target = "local",
    periodos_filter: list[str] | None = None,
    cache_dir: str = DEFAULT_CACHE_DIR,
) -> None:
    """Download attachments that are missing their R2 images and upload them.

    Finds attachments whose ``file_path`` is still NULL in D1, downloads their pages to the
    local cache, uploads each to R2, and updates ``attachments.file_path`` in D1.

    Args:
        target: D1/R2 target — "local" (default) or "remote".
        periodos_filter: Only process these periods (e.g. ["2024-12"]).
        cache_dir: Ephemeral local scratch for downloaded images before upload.
    """
    logger.info("Download-docs target: %s", "REMOTE (production)" if target == "remote" else "local")
    cache_path = Path(cache_dir)

    where = "d.file_path IS NULL"
    if periodos_filter:
        in_list = ", ".join("'" + p.replace("'", "''") + "'" for p in periodos_filter)
        where += f" AND r.period IN ({in_list})"
    pending = d1.query(
        "SELECT d.id, d.entry_id, d.external_document_id, r.period "
        "FROM attachments d "
        "JOIN entries e ON d.entry_id = e.id "
        "JOIN accountability_reports r ON e.report_id = r.id "
        f"WHERE {where}",
        target=target,
    )

    if not pending:
        logger.info("All attachments already have images in R2")
        return

    # Group by (period, entry_id) for batch downloading
    by_entry: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for doc in pending:
        by_entry[(doc["period"], doc["entry_id"])].append(doc)

    logger.info("Will download %d attachments across %d entries", len(pending), len(by_entry))

    browser = BRCondosBrowser()
    try:
        await browser.start()
        await browser.login()

        updated_docs: list[dict] = []
        for (periodo, entry_id), entry_docs in by_entry.items():
            dest_dir = cache_path / periodo
            ext_doc_ids = [d["external_document_id"] for d in entry_docs]

            paths_by_id = await download_entry_documents(
                browser.page, ext_doc_ids, entry_id, dest_dir
            )

            for doc in entry_docs:
                ext_id = doc["external_document_id"]
                if ext_id in paths_by_id:
                    local_paths = paths_by_id[ext_id]
                    keys = _upload_pages_to_r2(local_paths, periodo, target)
                    updated_docs.append({
                        "id": doc["id"],
                        "entry_id": doc["entry_id"],
                        "external_document_id": ext_id,
                        "file_path": ";".join(keys),
                        # Grouping key from the local page bytes (see _scrape_periodo).
                        "content_hash": content_hash(";".join(local_paths)),
                    })

        if updated_docs:
            d1.upsert_tables({"attachments": updated_docs}, target=target)
        logger.info("Updated %d/%d attachments in D1 (%s)", len(updated_docs), len(pending), target)

    except Exception as e:
        logger.error("Fatal error during attachment download: %s", e, exc_info=True)
    finally:
        await browser.close()
