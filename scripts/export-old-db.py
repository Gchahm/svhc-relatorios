#!/usr/bin/env python3
"""
Export data from the old PostgreSQL database (fiscal-old) to a JSON file.

Reads all tables, maps column names to the new schema, and converts types
(datetime → epoch ms, date → ISO string, bool → 0/1, severity pt→en).

Usage:
    cd fiscal-old
    docker compose up -d  # ensure postgres is running
    cd ../fiscal
    python scripts/export-old-db.py [--output data/export.json]

Requires: psycopg2-binary (pip install psycopg2-binary)
"""

import argparse
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get(
    "OLD_DATABASE_URL",
    "postgresql://fiscal:fiscal_dev@localhost:5432/fiscal",
)

SEVERITY_MAP = {"critico": "critical", "atencao": "warning", "info": "info"}

# Each entry: (old_table, new_table, column_map: {old_col: new_col}, type_converters)
TABLE_MAPPINGS = [
    (
        "coleta",
        "scrape_runs",
        {
            "id": "id",
            "data_execucao": "executed_at",
            "status": "status",
            "erros": "errors",
            "duracao_seg": "duration_seconds",
        },
    ),
    (
        "categoria_ref",
        "categories",
        {
            "id": "id",
            "nome": "name",
            "tipo_movimento": "movement_type",
        },
    ),
    (
        "fornecedor",
        "vendors",
        {
            "id": "id",
            "nome": "name",
        },
    ),
    (
        "unidade",
        "units",
        {
            "id": "id",
            "bloco": "block",
            "numero": "number",
            "codigo": "code",
        },
    ),
    (
        "subcategoria_ref",
        "subcategories",
        {
            "id": "id",
            "categoria_id": "category_id",
            "nome": "name",
        },
    ),
    (
        "prestacao_contas",
        "accountability_reports",
        {
            "id": "id",
            "coleta_id": "scrape_run_id",
            "periodo": "period",
            "accountability_book_id": "external_book_id",
            "total_receitas": "total_revenue",
            "total_despesas": "total_expenses",
            "saldo_inicial": "opening_balance",
            "saldo_mes": "month_balance",
            "saldo_acumulado": "accumulated_balance",
            "url_origem": "source_url",
            "created_at": "created_at",
            "updated_at": "updated_at",
        },
    ),
    (
        "lancamento",
        "entries",
        {
            "id": "id",
            "prestacao_id": "report_id",
            "data": "date",
            "descricao": "description",
            "valor": "amount",
            "tipo_movimento": "movement_type",
            "subcategoria_ref_id": "subcategory_id",
            "unidade_id": "unit_id",
            "fornecedor_id": "vendor_id",
            "documento_id": "external_document_id",
            "url_origem": "source_url",
            "created_at": "created_at",
            "updated_at": "updated_at",
        },
    ),
    (
        "subtotal_categoria",
        "category_subtotals",
        {
            "id": "id",
            "prestacao_id": "report_id",
            "subcategoria_ref_id": "subcategory_id",
            "valor": "amount",
            "tipo_movimento": "movement_type",
            "created_at": "created_at",
            "updated_at": "updated_at",
        },
    ),
    (
        "aprovador",
        "approvers",
        {
            "id": "id",
            "prestacao_id": "report_id",
            "nome": "name",
            "status": "status",
        },
    ),
    (
        "documento",
        "documents",
        {
            "id": "id",
            "lancamento_id": "entry_id",
            "brcondos_document_id": "external_document_id",
            "caminho_arquivo": "file_path",
        },
    ),
    (
        "analise_documento",
        "document_analyses",
        {
            "id": "id",
            "documento_id": "document_id",
            "data_analise": "analyzed_at",
            "tipo_documento": "document_type",
            "valor_extraido": "extracted_amount",
            "valor_match": "amount_match",
            "cnpj_extraido": "extracted_cnpj",
            "nome_emitente": "issuer_name",
            "fornecedor_match": "vendor_match",
            "data_extraida": "extracted_date",
            "data_match": "date_match",
            "numero_documento": "document_number",
            "descricao_servico": "service_description",
            "raw_response": "raw_response",
            "error": "error",
        },
    ),
    (
        "alerta",
        "alerts",
        {
            "id": "id",
            "data_geracao": "created_at",
            "tipo": "type",
            "severidade": "severity",
            "titulo": "title",
            "descricao": "description",
            "periodo_ref": "reference_period",
            "resolvido": "resolved",
            "data_resolucao": "resolved_at",
            "notas": "notes",
            "dados_json": "metadata",
        },
    ),
]


def convert_value(value, new_col: str, new_table: str):
    """Convert a single value to the new schema's expected type."""
    if value is None:
        return None

    # datetime → epoch milliseconds
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)

    # date → ISO string
    if isinstance(value, date):
        return value.isoformat()

    # Decimal → float
    if isinstance(value, Decimal):
        return float(value)

    # bool → 0/1 integer
    if isinstance(value, bool):
        return 1 if value else 0

    # severity mapping (pt-BR → en)
    if new_table == "alerts" and new_col == "severity":
        return SEVERITY_MAP.get(value, value)

    # JSON/dict → JSON string
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return value


def export_table(cursor, old_table: str, new_table: str, col_map: dict) -> list[dict]:
    """Export a single table, mapping columns and converting types."""
    old_cols = list(col_map.keys())
    cursor.execute(f'SELECT {", ".join(old_cols)} FROM {old_table} ORDER BY id')
    rows = cursor.fetchall()

    result = []
    for row in rows:
        new_row = {}
        for old_col, val in zip(old_cols, row):
            new_col = col_map[old_col]
            new_row[new_col] = convert_value(val, new_col, new_table)
        result.append(new_row)

    return result


def main():
    parser = argparse.ArgumentParser(description="Export old PostgreSQL data to JSON")
    parser.add_argument(
        "--output",
        "-o",
        default="data/export.json",
        help="Output JSON file path (default: data/export.json)",
    )
    parser.add_argument(
        "--database-url",
        default=DATABASE_URL,
        help="PostgreSQL connection URL",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(args.database_url)
    try:
        cursor = conn.cursor()
        data = {}

        for old_table, new_table, col_map in TABLE_MAPPINGS:
            rows = export_table(cursor, old_table, new_table, col_map)
            data[new_table] = rows
            print(f"  {old_table} → {new_table}: {len(rows)} rows")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        total = sum(len(rows) for rows in data.values())
        print(f"\nExported {total} total rows to {output_path}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
