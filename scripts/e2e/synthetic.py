"""Pure synthetic-dataset builder for the E2E/integration seed (feature 046).

SYNTHETIC ONLY. Every value here is invented — no real condominium name, CNPJ, amount,
or scraped artifact. The module reads nothing from ``data/scrape``; it imports only stdlib
and ``scripts/common`` so it stays a pure, import-only core (mirrors the ``preserve.py`` /
``reconcile.py`` "pure core, thin I/O shell" pattern) and the seed (``seed.py``) is the only
thing that performs I/O.

All ids are derived with ``det_id(...)`` exactly as the production pipeline derives them, so
the seeded rows are byte-identical to what the scraper/analysis would write and the seed is
idempotent (a second run re-mints the same ids → ``INSERT OR REPLACE`` overwrites in place).
"""

from __future__ import annotations

import json

from common import det_id, now_ms

# ─── Synthetic constants (obviously fake on inspection — FR-002 / SC-005) ─────
PERIOD = "2099-01"  # far-future: never collides with a real scraped period
SOURCE_URL = f"https://example.svhc.local/{PERIOD}"
CNPJ_A = "11222333000181"  # fake but 14-digit-shaped
CNPJ_B = "44555666000199"  # fake but 14-digit-shaped
ADMIN_EMAIL = "e2e@svhc.local"
ADMIN_PASSWORD = "E2e-Smoke-2099!"
ADMIN_NAME = "EXEMPLO Reviewer"

# A 1×1 transparent PNG (constant bytes — not a real document).
_TINY_PNG = bytes(
    [
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
        0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
        0x0A, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
        0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
    ]
)


def tiny_png() -> bytes:
    """The constant synthetic PNG bytes uploaded to R2 for every seeded page image."""
    return _TINY_PNG


# ─── Deterministic id helpers (match the pipeline's derivations) ──────────────


def report_id() -> str:
    return det_id("report", PERIOD)


def scrape_run_id() -> str:
    return det_id("scrape_run", PERIOD)


def category_id(name: str) -> str:
    return det_id("category", name)


def subcategory_id(cat_id: str, name: str) -> str:
    return det_id("subcategory", cat_id, name)


def vendor_id(name: str) -> str:
    return det_id("vendor", name)


def unit_id(code: str) -> str:
    return det_id("unit", code)


def entry_id(date: str, description: str, amount: float, subcat_id: str) -> str:
    # Mirrors the natural-key + "1" singleton discriminator (feature 034).
    return det_id("entry", PERIOD, date, description, str(amount), subcat_id, "1")


def attachment_id(eid: str) -> str:
    return det_id("attachment", eid)


def analysis_id(att_id: str) -> str:
    return det_id("attachment_analysis", att_id)


def file_path_for(eid: str) -> str:
    """The R2-key-form file_path (single page p1) — identity under objectKeyFromFilePath."""
    return f"{PERIOD}/{eid}_p1.png"


# ─── The synthetic period (data-model.md) ─────────────────────────────────────


def _entries_spec():
    """(key, date, description, amount, movement, vendor_name|None, with_attachment)."""
    return [
        ("E1", f"{PERIOD}-05", "EXEMPLO Servico A parte 1", 100.00, "D", "EXEMPLO Fornecedor A", True),
        ("E2", f"{PERIOD}-05", "EXEMPLO Servico A parte 2", 100.00, "D", "EXEMPLO Fornecedor A", True),
        ("E3", f"{PERIOD}-10", "EXEMPLO Servico B", 250.00, "D", "EXEMPLO Fornecedor B", True),
        ("E4", f"{PERIOD}-12", "EXEMPLO Servico pendente", 50.00, "D", "EXEMPLO Fornecedor B", True),
        ("E5", f"{PERIOD}-15", "EXEMPLO Servico a sumir", 75.00, "D", "EXEMPLO Fornecedor A", True),
        ("E6", f"{PERIOD}-20", "EXEMPLO Receita condominio", 500.00, "C", None, False),
    ]


def ids() -> dict:
    """Resolved deterministic ids for every keyed row — used by tests + the smoke."""
    cat_d = category_id("EXEMPLO Despesas")
    cat_c = category_id("EXEMPLO Receitas")
    sub_d = subcategory_id(cat_d, "EXEMPLO Sub Despesa")
    sub_c = subcategory_id(cat_c, "EXEMPLO Sub Receita")
    u = unit_id("101A")
    out: dict = {
        "period": PERIOD,
        "report_id": report_id(),
        "scrape_run_id": scrape_run_id(),
        "category_d": cat_d,
        "category_c": cat_c,
        "sub_d": sub_d,
        "sub_c": sub_c,
        "unit": u,
        "entries": {},
        "attachments": {},
        "analyses": {},
    }
    for key, date, desc, amount, mv, vendor_name, with_att in _entries_spec():
        sub = sub_c if mv == "C" else sub_d
        eid = entry_id(date, desc, amount, sub)
        out["entries"][key] = eid
        if with_att:
            aid = attachment_id(eid)
            out["attachments"][key] = aid
            out["analyses"][key] = analysis_id(aid)
    return out


def build_dataset() -> dict[str, list[dict]]:
    """Return the table→rows dict for the synthetic period (FK-ordered keys not required;
    ``d1.upsert_tables`` reorders via TABLE_ORDER)."""
    ts = now_ms()
    i = ids()
    sub_d, sub_c = i["sub_d"], i["sub_c"]
    cat_d, cat_c = i["category_d"], i["category_c"]
    u = i["unit"]
    vid_a = vendor_id("EXEMPLO Fornecedor A")
    vid_b = vendor_id("EXEMPLO Fornecedor B")

    scrape_runs = [
        {"id": i["scrape_run_id"], "executed_at": ts, "status": "success", "errors": None, "duration_seconds": 1.0}
    ]
    accountability_reports = [
        {
            "id": i["report_id"],
            "scrape_run_id": i["scrape_run_id"],
            "period": PERIOD,
            "external_book_id": 99990001,
            "total_revenue": 500.00,
            "total_expenses": 575.00,
            "opening_balance": 0.00,
            "month_balance": -75.00,
            "accumulated_balance": -75.00,
            "source_url": SOURCE_URL,
            "created_at": ts,
            "updated_at": ts,
        }
    ]
    # NOTE: categories / subcategories / vendors / units have NO timestamp columns (schema).
    categories = [
        {"id": cat_d, "name": "EXEMPLO Despesas", "movement_type": "D"},
        {"id": cat_c, "name": "EXEMPLO Receitas", "movement_type": "C"},
    ]
    subcategories = [
        {"id": sub_d, "category_id": cat_d, "name": "EXEMPLO Sub Despesa"},
        {"id": sub_c, "category_id": cat_c, "name": "EXEMPLO Sub Receita"},
    ]
    vendors = [
        {"id": vid_a, "name": "EXEMPLO Fornecedor A"},
        {"id": vid_b, "name": "EXEMPLO Fornecedor B"},
    ]
    units = [{"id": u, "block": "A", "number": 101, "code": "101A"}]

    entries: list[dict] = []
    attachments: list[dict] = []
    attachment_state: list[dict] = []
    vendor_by_name = {"EXEMPLO Fornecedor A": vid_a, "EXEMPLO Fornecedor B": vid_b}
    ext_doc = 99990000

    for key, date, desc, amount, mv, vendor_name, with_att in _entries_spec():
        sub = sub_c if mv == "C" else sub_d
        eid = i["entries"][key]
        vid = vendor_by_name.get(vendor_name) if vendor_name else None
        ext_doc += 1
        entries.append(
            {
                "id": eid,
                "report_id": i["report_id"],
                "date": date,
                "description": desc,
                "amount": amount,
                "raw_amount": f"R$ {amount:.2f}".replace(".", ","),
                "raw_description": desc,
                "movement_type": mv,
                "subcategory_id": sub,
                "unit_id": u if mv == "D" else None,
                "vendor_id": vid,
                "external_document_id": ext_doc if with_att else None,
                "source_url": SOURCE_URL,
                "created_at": ts,
                "updated_at": ts,
            }
        )
        if with_att:
            aid = i["attachments"][key]
            # E1 + E2 share a byte-identical NF (same content_hash) — a shared-NF split.
            chash = "exemplo_hash_nf1001" if key in ("E1", "E2") else f"exemplo_hash_{key}"
            # NOTE: attachments has NO timestamp columns (schema — mirror table).
            attachments.append(
                {
                    "id": aid,
                    "entry_id": eid,
                    "external_document_id": ext_doc,
                    "file_path": file_path_for(eid),
                    "content_hash": chash,
                }
            )
            # E4 is PENDING (no attachment_state row); the rest are classified.
            if key != "E4":
                attachment_state.append({"attachment_id": aid, "classified_at": ts})

    # category_subtotals consistent with the entry sums (D: 575, C: 500).
    category_subtotals = [
        {
            "id": det_id("subtotal", i["report_id"], sub_d, "D"),
            "report_id": i["report_id"],
            "subcategory_id": sub_d,
            "amount": 575.00,
            "movement_type": "D",
            "created_at": ts,
            "updated_at": ts,
        },
        {
            "id": det_id("subtotal", i["report_id"], sub_c, "C"),
            "report_id": i["report_id"],
            "subcategory_id": sub_c,
            "amount": 500.00,
            "movement_type": "C",
            "created_at": ts,
            "updated_at": ts,
        },
    ]
    approvers = [
        {
            "id": det_id("approver", i["report_id"], "EXEMPLO Sindico"),
            "report_id": i["report_id"],
            "name": "EXEMPLO Sindico",
            "status": "approved",
        }
    ]

    # attachment_analyses for E1, E2 (shared NF-1001, over-claim), E3 (NF-1002, within).
    analyses: list[dict] = []
    for key, number, cnpj, total, doc_type, issuer in (
        ("E1", "NF-1001", CNPJ_A, 150.00, "NF", "EXEMPLO Fornecedor A"),
        ("E2", "NF-1001", CNPJ_A, 150.00, "NF", "EXEMPLO Fornecedor A"),
        ("E3", "NF-1002", CNPJ_B, 250.00, "NF", "EXEMPLO Fornecedor B"),
    ):
        aid = i["attachments"][key]
        an_id = i["analyses"][key]
        # E1's roll-up carries an amount mismatch flag (backs the seeded alert).
        amount_match = 0 if key == "E1" else 1
        analyses.append(
            {
                "id": an_id,
                "attachment_id": aid,
                "analyzed_at": ts,
                "document_type": doc_type,
                "extracted_amount": total,
                "amount_match": amount_match,
                "extracted_cnpj": cnpj,
                "issuer_name": issuer,
                "vendor_match": 1,
                "extracted_date": "05/01/2099",
                "date_match": 1,
                "document_number": number,
                "service_description": f"EXEMPLO servico {number}",
                "error": None,
                "analysis_records": [
                    {
                        "id": det_id("analysis_record", an_id, "page_extraction", "p1"),
                        "attachment_analysis_id": an_id,
                        "analysis_type": "page_extraction",
                        "page_index": 0,
                        "page_label": "p1",
                        "artifact_role": "invoice",
                        # Typed EXTRACT-001 danfe payload (EXTRACT-007 typed-only contract).
                        "response": {
                            "doc_type": "danfe",
                            "schema_version": "1",
                            "raw_text": f"DANFE {number} EXEMPLO",
                            "numero": number,
                            "data_emissao": "05/01/2099",
                            "emitente": {"nome": issuer, "cnpj": cnpj},
                            "totais": {"valor_total_nota": total},
                        },
                        "parse_error": None,
                        "analyzed_at": ts,
                    }
                ],
            }
        )

    # A staging page_classifications row for the PENDING E4 attachment — the merge/mark-pending
    # tests assert this row is pruned by the writeback (feature 035).
    e4_aid = i["attachments"]["E4"]
    page_classifications = [
        {
            "id": det_id("page_classification", e4_aid, "p1"),
            "attachment_id": e4_aid,
            "page_label": "p1",
            "page_index": 0,
            "response": json.dumps(
                {
                    "doc_type": "danfe",
                    "schema_version": "1",
                    "raw_text": "DANFE NF-9999 EXEMPLO",
                    "numero": "NF-9999",
                    "data_emissao": "05/01/2099",
                    "emitente": {"nome": "EXEMPLO Fornecedor", "cnpj": CNPJ_A},
                    "totais": {"valor_total_nota": 50.0},
                }
            ),
            "error": None,
            "recorded_at": ts,
        }
    ]

    return {
        "scrape_runs": scrape_runs,
        "accountability_reports": accountability_reports,
        "categories": categories,
        "subcategories": subcategories,
        "vendors": vendors,
        "units": units,
        "entries": entries,
        "category_subtotals": category_subtotals,
        "approvers": approvers,
        "attachments": attachments,
        "page_classifications": page_classifications,
        "attachment_analyses": analyses,
        "attachment_state": attachment_state,
    }


def build_alerts() -> list[dict]:
    """The seeded alerts (deep-link metadata) — written separately so build_dataset stays
    purely the mirror/analysis seed; alerts carry the feature-018 deep links."""
    ts = now_ms()
    i = ids()
    e1 = i["entries"]["E1"]
    e2 = i["entries"]["E2"]
    e1_att = i["attachments"]["E1"]
    doc_id = det_id("document", "NF-1001", CNPJ_A)
    amount_alert = {
        "id": det_id("alert", "attachment_amount_mismatch", e1_att),
        "created_at": ts,
        "type": "attachment_amount_mismatch",
        "severity": "warning",
        "title": "EXEMPLO divergencia de valor",
        "description": "EXEMPLO: valor do anexo difere do lancamento.",
        "reference_period": PERIOD,
        "resolved": 0,
        "resolved_at": None,
        "notes": None,
        "metadata": json.dumps(
            {
                "attachment_id": e1_att,
                "entry_id": e1,
                "kind": "amount",
                "ledger_value": 100.0,
                "extracted_value": 150.0,
            }
        ),
    }
    overpay_alert = {
        "id": det_id("alert", "document_overpayment", doc_id),
        "created_at": ts,
        "type": "document_overpayment",
        "severity": "critical",
        "title": "EXEMPLO documento sobre-cobrado",
        "description": "EXEMPLO: soma dos lancamentos excede o total do documento.",
        "reference_period": PERIOD,
        "resolved": 0,
        "resolved_at": None,
        "notes": None,
        "metadata": json.dumps(
            {
                "document_id": doc_id,
                "document_number": "NF-1001",
                "issuer_cnpj": CNPJ_A,
                "total_value": 150.0,
                "sum_entries": 200.0,
                "over_amount": 50.0,
                "entry_ids": [e1, e2],
            }
        ),
    }
    return [amount_alert, overpay_alert]


def image_plan() -> list[tuple[str, bytes]]:
    """(R2 object key, bytes) for every seeded attachment's page image."""
    i = ids()
    # One image per entry that has an attachment (keyed by the same file_path the row carries).
    return [(file_path_for(i["entries"][key]), _TINY_PNG) for key in i["attachments"]]
