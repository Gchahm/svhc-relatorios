"""Shared harness for the real-D1 integration tests (feature 046).

These tests run against **local Miniflare D1/R2** through the real ``scripts/common/d1.py``
wrapper (never stubbed) — so they require ``wrangler`` and an applied local migration set, and
must NOT be discovered by the fast unit suite (they live under ``scripts/integration_tests/``,
run via ``pnpm test:py:integration``).

Each test module calls ``seed_once()`` in ``setUpClass`` to (re)provision the synthetic period
deterministically; because every seeded id is ``det_id``-derived, re-seeding is an idempotent
``INSERT OR REPLACE`` (it also heals any mutation a prior test made).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from common import d1
from e2e import seed as seed_module
from e2e import synthetic


_migrated = False


def seed_once() -> dict:
    """Full synthetic seed against local D1+R2 (migrations + documents + images). Idempotent.

    Migrations are applied only on the first call per process (the schema does not change between
    tests); subsequent calls skip the migration step for speed.
    """
    global _migrated
    summary = seed_module.seed(apply_migrations=not _migrated)
    _migrated = True
    return summary


def restore() -> None:
    """Cheap per-test re-seed: reset the synthetic period's mutable analysis-owned rows to the
    seeded baseline, without the migration / global-build_documents / R2 cost. Use in ``setUp``
    for writeback tests that mutate only the synthetic rows and do not assert the documents table.

    Because ``INSERT OR REPLACE`` only overwrites rows present in the seed (it cannot remove a row
    a test *added* — e.g. the E4 stamp/analysis a merge test writes), the synthetic attachments'
    analysis-owned rows are first DELETEd, then the dataset is re-upserted to the baseline.
    """
    i = synthetic.ids()
    att_ids = ",".join(f"'{a}'" for a in i["attachments"].values())
    an_ids = ",".join(f"'{a}'" for a in i["analyses"].values())
    # Also reset the reconcile target (E5 mirror rows) by re-upserting the whole dataset below.
    cleanup = (
        f"DELETE FROM attachment_analysis_records WHERE attachment_analysis_id IN ({an_ids});\n"
        f"DELETE FROM attachment_analyses WHERE attachment_id IN ({att_ids});\n"
        f"DELETE FROM attachment_state WHERE attachment_id IN ({att_ids});\n"
        f"DELETE FROM page_classifications WHERE attachment_id IN ({att_ids});\n"
        f"DELETE FROM alerts WHERE reference_period = '{synthetic.PERIOD}';"
    )
    d1.execute_sql(cleanup, target="local")
    seed_module.seed(apply_migrations=False, build_docs=False, upload_images=False)


def q(sql: str) -> list[dict]:
    """SELECT against local D1, returning result rows."""
    return d1.query(sql, target="local")


def scalar(sql: str):
    """First column of the first row, or None."""
    rows = q(sql)
    if not rows:
        return None
    first = rows[0]
    return next(iter(first.values()), None)


def count(table: str, where: str | None = None) -> int:
    sql = f"SELECT count(*) AS n FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return int(scalar(sql) or 0)


def r2_exists(key: str) -> bool:
    """True if the R2 object exists locally (round-trips it into a temp file)."""
    with tempfile.TemporaryDirectory() as d:
        dest = str(Path(d) / "obj.bin")
        return d1.get_object(key, dest, target="local")


def ids() -> dict:
    """Resolved deterministic ids for the synthetic rows (see e2e.synthetic.ids)."""
    return synthetic.ids()
