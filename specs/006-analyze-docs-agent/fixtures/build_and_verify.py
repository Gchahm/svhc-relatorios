"""Synthetic, VLM-free verification of the agent-extraction flow (US2 / SC-002).

Builds a self-contained period in a temp dir (with byte-identical NF siblings),
runs ``plan_extractions`` then ``apply_extractions`` against a hand-authored
extractions file, and asserts the deterministic pipeline behaves exactly as the
old flow would for the same extracted values — including the duplicate-billing
alert. No real images and no model are needed.

Run from the ``scripts/`` directory so the ``scraper`` package imports:

    cd scripts && uv run python ../specs/006-analyze-docs-agent/fixtures/build_and_verify.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Allow running from the repo root too.
_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from scraper.analise.checks.advanced import check_duplicate_billing  # noqa: E402
from scraper.analise.extractions import (  # noqa: E402
    apply_extractions,
    extractions_path,
    plan_extractions,
)
from scraper.analise.loader import load_all_periods  # noqa: E402

PERIOD = "2099-01"


def _write_image(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def build_fixture(data_dir: Path) -> dict:
    """Create the synthetic period JSON + page files. Returns the period dict."""
    img_dir = data_dir / PERIOD
    # Byte-identical content for shared-NF siblings (grouped by content hash).
    b_bytes = b"SHARED-NF-B-PAGE-CONTENT"
    c_bytes = b"SHARED-NF-C-PAGE-CONTENT"

    files = {
        "A_p1": (img_dir / "A_p1.png", b"A-INVOICE-PAGE"),
        "B1_p1": (img_dir / "B1_p1.png", b_bytes),
        "B2_p1": (img_dir / "B2_p1.png", b_bytes),  # identical bytes -> same NF group
        "C1_p1": (img_dir / "C1_p1.png", c_bytes),
        "C2_p1": (img_dir / "C2_p1.png", c_bytes),  # identical bytes -> same NF group
        "D_p1": (img_dir / "D_p1.png", b"D-INVOICE"),
        "D_p2": (img_dir / "D_p2.png", b"D-BOLETO"),
        "D_p3": (img_dir / "D_p3.png", b"D-PAYMENT"),
        "E_p1": (img_dir / "E_p1.png", b"E-UNREADABLE"),
    }
    for path, content in files.values():
        _write_image(path, content)

    def fp(*keys: str) -> str:
        return ";".join(str(files[k][0].resolve()) for k in keys)

    vendors = [{"id": "v1", "name": "ACME LIMPEZA LTDA"}]
    entries = [
        {"id": "e_A", "amount": 500.0, "movement_type": "D", "vendor_id": "v1", "description": "Limpeza A"},
        {"id": "e_B1", "amount": 600.0, "movement_type": "D", "vendor_id": "v1", "description": "Split B1"},
        {"id": "e_B2", "amount": 400.0, "movement_type": "D", "vendor_id": "v1", "description": "Split B2"},
        {"id": "e_C1", "amount": 900.0, "movement_type": "D", "vendor_id": "v1", "description": "Split C1"},
        {"id": "e_C2", "amount": 800.0, "movement_type": "D", "vendor_id": "v1", "description": "Split C2"},
        {"id": "e_D", "amount": 900.0, "movement_type": "D", "vendor_id": "v1", "description": "Heterogeneous D"},
        {"id": "e_E", "amount": 300.0, "movement_type": "D", "vendor_id": "v1", "description": "Unreadable E"},
    ]
    documents = [
        {"id": "d_A", "entry_id": "e_A", "file_path": fp("A_p1")},
        {"id": "d_B1", "entry_id": "e_B1", "file_path": fp("B1_p1")},
        {"id": "d_B2", "entry_id": "e_B2", "file_path": fp("B2_p1")},
        {"id": "d_C1", "entry_id": "e_C1", "file_path": fp("C1_p1")},
        {"id": "d_C2", "entry_id": "e_C2", "file_path": fp("C2_p1")},
        {"id": "d_D", "entry_id": "e_D", "file_path": fp("D_p1", "D_p2", "D_p3")},
        {"id": "d_E", "entry_id": "e_E", "file_path": fp("E_p1")},
    ]
    period = {
        "accountability_reports": [{"id": "rep1"}],
        "categories": [],
        "subcategories": [],
        "units": [],
        "vendors": vendors,
        "entries": entries,
        "documents": documents,
        "document_analyses": [],
        "alerts": [],
    }
    (data_dir / f"{PERIOD}.json").write_text(json.dumps(period, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"documents": documents}


def author_extractions(data_dir: Path) -> None:
    """Read the manifest and write the synthetic extractions keyed by page path.

    Keys MUST be the manifest `path` strings, so derive them from the manifest.
    """
    manifest = json.loads((data_dir / f"{PERIOD}.extract-todo.json").read_text(encoding="utf-8"))
    rep_by_doc = {g["representative_document_id"]: g for g in manifest["groups"]}

    # Map each representative document -> its page extractions (by page_index).
    def pages_of(doc_id: str) -> list[str]:
        return [p["path"] for p in rep_by_doc[doc_id]["pages"]]

    extractions: dict[str, dict] = {}

    # A: single invoice, gross 500, issuer matches vendor, in-period date.
    (a_p1,) = pages_of("d_A")
    extractions[a_p1] = {
        "papel_artefato": "invoice", "tipo_documento": "NF-e", "valor_total": 500.0,
        "valor_liquido": None, "valor_pago": None, "cnpj_emitente": "12.345.678/0001-90",
        "nome_emitente": "ACME LIMPEZA LTDA", "data_emissao": "15/01/2099",
        "numero_documento": "A-1", "descricao_servico": "Limpeza",
    }

    # B representative (highest amount = B1): NF gross 1000.
    b_rep = "d_B1" if "d_B1" in rep_by_doc else "d_B2"
    (b_p1,) = pages_of(b_rep)
    extractions[b_p1] = {
        "papel_artefato": "invoice", "tipo_documento": "NF-e", "valor_total": 1000.0,
        "valor_liquido": None, "valor_pago": None, "cnpj_emitente": "12.345.678/0001-90",
        "nome_emitente": "ACME LIMPEZA LTDA", "data_emissao": "15/01/2099",
        "numero_documento": "B-1", "descricao_servico": "Servico B",
    }

    # C representative: NF gross 1000 (siblings sum 1700 -> over-claim).
    c_rep = "d_C1" if "d_C1" in rep_by_doc else "d_C2"
    (c_p1,) = pages_of(c_rep)
    extractions[c_p1] = {
        "papel_artefato": "invoice", "tipo_documento": "NF-e", "valor_total": 1000.0,
        "valor_liquido": None, "valor_pago": None, "cnpj_emitente": "12.345.678/0001-90",
        "nome_emitente": "ACME LIMPEZA LTDA", "data_emissao": "15/01/2099",
        "numero_documento": "C-1", "descricao_servico": "Servico C",
    }

    # D: heterogeneous, paid value should win the roll-up (900).
    d_p1, d_p2, d_p3 = pages_of("d_D")
    extractions[d_p1] = {
        "papel_artefato": "invoice", "tipo_documento": "NF-e", "valor_total": 1000.0,
        "valor_liquido": 900.0, "valor_pago": None, "cnpj_emitente": "12.345.678/0001-90",
        "nome_emitente": "ACME LIMPEZA LTDA", "data_emissao": "15/01/2099",
        "numero_documento": "D-1", "descricao_servico": "Servico D",
    }
    extractions[d_p2] = {
        "papel_artefato": "boleto", "tipo_documento": "boleto", "valor_total": 950.0,
        "valor_liquido": None, "valor_pago": None, "cnpj_emitente": None,
        "nome_emitente": None, "data_emissao": None, "numero_documento": None,
        "descricao_servico": None,
    }
    extractions[d_p3] = {
        "papel_artefato": "payment_proof", "tipo_documento": "comprovante", "valor_total": None,
        "valor_liquido": None, "valor_pago": 900.0, "cnpj_emitente": None,
        "nome_emitente": None, "data_emissao": None, "numero_documento": None,
        "descricao_servico": None,
    }

    # E: unreadable page -> per-page error -> document error.
    (e_p1,) = pages_of("d_E")
    extractions[e_p1] = {"error": "page illegible"}

    extractions_path(str(data_dir), PERIOD).write_text(
        json.dumps(extractions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def verify(data_dir: Path) -> None:
    period_json = json.loads((data_dir / f"{PERIOD}.json").read_text(encoding="utf-8"))
    analyses = {a["document_id"]: a for a in period_json["document_analyses"]}

    failures: list[str] = []

    def check(name: str, cond: bool) -> None:
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    # Every selected, non-error document got an analysis row.
    for doc_id in ("d_A", "d_B1", "d_B2", "d_C1", "d_C2", "d_D", "d_E"):
        check(f"{doc_id} has an analysis row", doc_id in analyses)

    a = analyses["d_A"]
    check("A amount_match True", a["amount_match"] == 1)
    check("A extracted_amount 500", a["extracted_amount"] == 500.0)
    check("A vendor_match True", a["vendor_match"] == 1)
    check("A date_match True", a["date_match"] == 1)

    check("B1 amount_match True (reconciled split)", analyses["d_B1"]["amount_match"] == 1)
    check("B2 amount_match True (fanned out)", analyses["d_B2"]["amount_match"] == 1)
    check("B1 extracted gross 1000", analyses["d_B1"]["extracted_amount"] == 1000.0)
    check("B2 reused NF number B-1", analyses["d_B2"]["document_number"] == "B-1")

    check("C1 amount_match False (over-claim)", analyses["d_C1"]["amount_match"] == 0)
    check("C2 amount_match False (over-claim)", analyses["d_C2"]["amount_match"] == 0)

    d = analyses["d_D"]
    check("D roll-up picks paid 900", d["extracted_amount"] == 900.0)
    check("D amount_match True", d["amount_match"] == 1)
    check("D has 3 page records", len(d["analysis_records"]) == 3)

    e = analyses["d_E"]
    check("E document-level error", bool(e["error"]))

    # Shared-NF B was extracted once (manifest lists only the representative's pages).
    manifest = json.loads((data_dir / f"{PERIOD}.extract-todo.json").read_text(encoding="utf-8"))
    b_group = next(g for g in manifest["groups"] if g["group_size"] == 2 and g["sibling_sum"] == 1000.0)
    check("B group has 2 members, 1 representative page set", len(b_group["members"]) == 2 and len(b_group["pages"]) == 1)

    # Duplicate-billing: exactly one critical alert, for the over-claim group C.
    periods, _refs = load_all_periods(str(data_dir), [PERIOD])
    alerts = check_duplicate_billing(periods[PERIOD])
    check("exactly one duplicate_billing alert", len(alerts) == 1)
    if alerts:
        meta = alerts[0].metadata
        check("alert is for the over-claim group C (sum 1700 vs total 1000)",
              meta.get("sum_entries") == 1700.0 and meta.get("nf_total") == 1000.0)
        check("alert severity critical", alerts[0].severity == "critical")

    print()
    if failures:
        print(f"VERIFICATION FAILED: {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("VERIFICATION PASSED: all assertions hold.")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        print(f"Building synthetic fixture in {data_dir} ...")
        build_fixture(data_dir)
        print("Running docs-plan (plan_extractions) ...")
        plan_extractions(str(data_dir), [PERIOD], reanalyze=True)
        print("Authoring synthetic extractions ...")
        author_extractions(data_dir)
        print("Running apply-extractions ...")
        apply_extractions(str(data_dir), [PERIOD])
        print("\nVerifying outcomes:")
        verify(data_dir)


if __name__ == "__main__":
    main()
