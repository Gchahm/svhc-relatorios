import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from scripts/ directory (one level up from scripts/scraper/)
_scripts_dir = Path(__file__).resolve().parent.parent
load_dotenv(_scripts_dir / ".env")

BRCONDOS_URL = os.environ.get("BRCONDOS_URL", "https://ssl.brcondos.com.br")
BRCONDOS_USER = os.environ.get("BRCONDOS_USER", "")
BRCONDOS_PASSWORD = os.environ.get("BRCONDOS_PASSWORD", "")
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"

# Routes
LOGIN_PATH = "/"
ACCOUNTABILITY_PATH = "/Accountability/Index"

# CSS selectors
SELECTORS = {
    # Login page
    "login_user": "input#Login",
    "login_password": "input#Password",
    "login_submit": '#form_login button[type="submit"]',
    # Period selector
    "period_select": "select#q",
    "period_options": "select#q option",
    # Overview tab - financial summary
    "tab_overview": "#tab_overview",
    "receitas_valor": ".dem-fin-box-icon.box-icon-green",
    "despesas_valor": ".dem-fin-box-icon.box-icon-red",
    "dem_fin_values": ".dem-fin-box-value",
    "dem_fin_titles": ".dem-fin-box-title",
    # Category tabs
    "tab_links": '.menu-tabs a[data-toggle="tab"]',
    # Lancamentos table
    "table": "table.prescontas-table",
    "title_row": "tr.prescontas-table-title-row",
    "data_row": 'tr[data-group-id]:not(.prescontas-table-title-row)',
    # Aprovadores
    "aprovadores_container": ".prescontas-overview-aprovadores",
    "aprovador_nome": ".font-size-0_86rem.font-weight-500",
    "aprovador_status": ".text-uppercase.font-size-0_86rem",
}

# Tab name to category mapping
TAB_CATEGORIES = {
    "tab_7": "Consumo",
    "tab_12": "Contratos / Prestadores",
    "tab_3": "Despesas Administrativas",
    "tab_2": "Despesas Com Pessoal",
    "tab_4": "Despesas Financeiras",
    "tab_30": "Despesas Reembolsáveis",
    "tab_8": "Encargos e Impostos",
    "tab_9": "Manutenção e Conservação",
    "tab_25": "Materiais",
    "tab_0": "Receitas",
}
