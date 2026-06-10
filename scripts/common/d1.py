"""Wrangler-backed access to Cloudflare D1 + R2 for the scraper and analysis CLIs.

Python cannot reach D1/R2 directly (there is no public D1 REST surface and no API
token in the repo), so this module shells out to the ``wrangler`` CLI — the same
sanctioned path the project already uses for ``import-to-d1.mjs`` and migrations.
Every public function takes an explicit ``target`` (``"local"`` default, ``"remote"``
on request), mapping to ``wrangler``'s ``--local``/``--remote`` flag.

This module is the single home of the SQL generation ported from
``scripts/import-to-d1.mjs`` (escaping, ``TABLE_ORDER``, ``INSERT OR REPLACE``,
``analysis_records`` flattening), so the rows written here are byte-identical to
the retired import path.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

Target = Literal["local", "remote"]

# Cloudflare binding / bucket names (see wrangler.toml).
_DB_BINDING = "DATABASE"
_BUCKET = "fiscal-documents"

# The repo root is where wrangler.toml lives: scripts/common/d1.py -> parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Table insertion order (respects foreign-key dependencies). Mirrors import-to-d1.mjs.
TABLE_ORDER = [
    "scrape_runs",
    "categories",
    "vendors",
    "units",
    "subcategories",
    "accountability_reports",
    "entries",
    "category_subtotals",
    "approvers",
    "attachments",
    "attachment_analyses",
    "attachment_analysis_records",
    "alerts",
]


def target_flag(target: Target) -> str:
    """The wrangler flag for a target. ``remote`` writes production; default is local."""
    return "--remote" if target == "remote" else "--local"


def content_type_for(name: str) -> str:
    """MIME type for a page-image filename (mirrors src/lib/r2.ts:contentTypeForExt)."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in ("jpg", "jpeg"):
        return "image/jpeg"
    if ext == "png":
        return "image/png"
    return "application/octet-stream"


# ─── SQL generation (ported from import-to-d1.mjs) ───────────────────────────


def _escape_sql(value) -> str:
    if value is None:
        return "NULL"
    # bool is a subclass of int — test it first so True/False become 1/0, not "True".
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    # Objects/arrays (e.g. a record's structured `response`) are JSON-serialized, not
    # str()-coerced. ensure_ascii=False keeps unicode as-is, matching the JS importer.
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'"
    return "'" + str(value).replace("'", "''") + "'"


def _generate_inserts(table: str, rows: list[dict]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    col_list = ", ".join(f'"{c}"' for c in columns)
    statements = []
    for row in rows:
        values = ", ".join(_escape_sql(row.get(col)) for col in columns)
        statements.append(f'INSERT OR REPLACE INTO "{table}" ({col_list}) VALUES ({values});')
    return "\n".join(statements)


def _merge_dataset(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Dedup rows by id per table and lift nested ``analysis_records`` into their own table."""
    merged: dict[str, list[dict]] = {t: [] for t in TABLE_ORDER}
    seen: dict[str, set] = {t: set() for t in TABLE_ORDER}

    for table in TABLE_ORDER:
        for row in data.get(table) or []:
            rid = row.get("id")
            if rid is not None and rid in seen[table]:
                continue
            if rid is not None:
                seen[table].add(rid)

            if table == "attachment_analyses" and isinstance(row.get("analysis_records"), list):
                for rec in row["analysis_records"]:
                    rec_id = rec.get("id")
                    if rec_id is not None and rec_id in seen["attachment_analysis_records"]:
                        continue
                    if rec_id is not None:
                        seen["attachment_analysis_records"].add(rec_id)
                    merged["attachment_analysis_records"].append(rec)
                row = {k: v for k, v in row.items() if k != "analysis_records"}

            merged[table].append(row)
    return merged


def build_sql(data: dict[str, list[dict]]) -> tuple[str, dict[str, int]]:
    """Build the batched upsert SQL for a dataset and the per-table row counts."""
    merged = _merge_dataset(data)
    sql = "PRAGMA defer_foreign_keys = ON;\n\n"
    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        rows = merged[table]
        if not rows:
            continue
        sql += f"-- {table} ({len(rows)} rows)\n"
        sql += _generate_inserts(table, rows)
        sql += "\n\n"
        counts[table] = len(rows)
    return sql, counts


# ─── D1 writes ───────────────────────────────────────────────────────────────


def execute_sql(sql: str, *, target: Target) -> None:
    """Run arbitrary SQL against D1 via ``wrangler d1 execute --file``.

    Writes ``sql`` to a temp file and executes it in one call. Raises
    ``subprocess.CalledProcessError`` on a non-zero exit so callers report failure
    (FR-007). This is the escape hatch for non-upsert SQL (e.g. the period-/attachment-
    scoped DELETEs the analysis writebacks issue before upserting).
    """
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as fh:
        fh.write(sql)
        sql_path = fh.name
    try:
        subprocess.run(
            ["npx", "wrangler", "d1", "execute", _DB_BINDING, "--file", sql_path, target_flag(target)],
            cwd=_REPO_ROOT,
            check=True,
        )
    finally:
        Path(sql_path).unlink(missing_ok=True)


def upsert_tables(data: dict[str, list[dict]], *, target: Target) -> dict[str, int]:
    """Upsert a dataset's tables (INSERT OR REPLACE) in one batched execution.

    ``data`` maps table name -> list of row dicts (e.g. the period payload, or a single
    attachment's ``{"attachment_analyses": [..]}``). Empty/missing tables are skipped, so
    callers never clobber tables they don't supply. Returns ``{table: rows_written}``.
    """
    sql, counts = build_sql(data)
    if not counts:
        return {}
    execute_sql(sql, target=target)
    return counts


# ─── D1 reads ────────────────────────────────────────────────────────────────


def _parse_d1_json(stdout: str) -> list[dict]:
    """Parse the ``wrangler d1 execute --json`` envelope into result rows."""
    text = stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # Be resilient to a leading banner: parse from the first JSON bracket.
        start = min((i for i in (text.find("["), text.find("{")) if i != -1), default=-1)
        if start == -1:
            return []
        payload = json.loads(text[start:])
    # Envelope is a list of {results, success, meta}; flatten the result sets.
    if isinstance(payload, list):
        rows: list[dict] = []
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("results"), list):
                rows.extend(item["results"])
        return rows
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return payload["results"]
    return []


def query(sql: str, *, target: Target) -> list[dict]:
    """Run a SELECT against D1 and return the result rows as dicts."""
    proc = subprocess.run(
        ["npx", "wrangler", "d1", "execute", _DB_BINDING, "--command", sql, "--json", target_flag(target)],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return _parse_d1_json(proc.stdout)


# ─── R2 objects ──────────────────────────────────────────────────────────────


def put_object(key: str, file_path: str, content_type: str, *, target: Target) -> None:
    """Upload a local file to R2 at ``fiscal-documents/<key>`` (idempotent overwrite)."""
    # Resolve to absolute against the caller's CWD: wrangler runs with cwd=_REPO_ROOT,
    # so a relative --file (e.g. the scraper's ``../.cache/...`` from scripts/) would be
    # mis-resolved against the repo root and not found.
    abs_path = str(Path(file_path).resolve())
    subprocess.run(
        [
            "npx", "wrangler", "r2", "object", "put", f"{_BUCKET}/{key}",
            "--file", abs_path, "--content-type", content_type, target_flag(target),
        ],
        cwd=_REPO_ROOT,
        check=True,
    )


def get_object(key: str, dest_path: str, *, target: Target) -> bool:
    """Download an R2 object to ``dest_path``. Returns False if the key does not exist."""
    # Resolve to absolute (see put_object): wrangler's cwd=_REPO_ROOT must not re-anchor
    # a relative dest_path, or the bytes land somewhere the caller never looks.
    abs_dest = str(Path(dest_path).resolve())
    Path(abs_dest).parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["npx", "wrangler", "r2", "object", "get", f"{_BUCKET}/{key}", "--file", abs_dest, target_flag(target)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False
    return Path(abs_dest).exists()
