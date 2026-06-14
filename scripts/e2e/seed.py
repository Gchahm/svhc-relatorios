"""Deterministic synthetic seed for the local Miniflare D1 + R2 (feature 046).

LOCAL ONLY. This stands in for the scraper in a local-only test context: it applies the
committed D1 migrations, writes one fully synthetic period (``synthetic.build_dataset``) via the
real ``scripts/common/d1.py`` wrapper, derives the ``documents`` entity from the seeded analyses
(the real ``build_documents``), writes the deep-link alerts, and uploads matching fake page images
to R2. It refuses ``--remote`` — production is never seeded with synthetic data.

Idempotent: every row id is ``det_id``-derived, so a second run is an ``INSERT OR REPLACE`` over
the same ids (no duplicates). Run via ``python -m e2e.seed`` (``pnpm e2e:seed``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from analysis.documents import build_documents
from common import d1

from . import synthetic

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _apply_migrations() -> None:
    """Apply the committed D1 migrations to the local Miniflare state (idempotent).

    This is a wrangler local call OUTSIDE ``d1.py``'s read/write helpers, so it must honor the
    ``SVHC_WRANGLER_PERSIST`` selector itself (feature 061 / issue #107) — otherwise the seed would
    migrate the default ``.wrangler/state`` (staging) while the subsequent upserts (which go through
    ``d1.py``) land in ``.wrangler/state-test``, leaving the test DB schema-less ("no such table").
    ``d1._persist_args("local")`` returns ``[]`` when the var is unset, so the staging default is
    unchanged.
    """
    subprocess.run(
        ["npx", "wrangler", "d1", "migrations", "apply", "DATABASE", "--local"]
        + d1._persist_args("local"),
        cwd=_REPO_ROOT,
        check=True,
    )


def _upload_images() -> int:
    """Write each synthetic page image to R2 at its file_path-derived key. Returns the count."""
    n = 0
    for key, data in synthetic.image_plan():
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as fh:
            fh.write(data)
            tmp = fh.name
        try:
            d1.put_object(key, tmp, "image/png", target="local")
            n += 1
        finally:
            Path(tmp).unlink(missing_ok=True)
    return n


def seed(*, apply_migrations: bool = True, build_docs: bool = True, upload_images: bool = True) -> dict:
    """Seed local D1 + R2 with the synthetic period. Returns a terse summary dict.

    The flags let the integration harness avoid redundant work between tests that re-seed
    only to restore mutated rows: ``apply_migrations`` (the schema is already applied after the
    first run), ``build_docs`` (the global ``build_documents`` pass — only needed by the
    documents surface), and ``upload_images`` (R2 objects persist across re-seeds). The default
    (all True) is the full first-time provision used by ``pnpm e2e:seed``.
    """
    if apply_migrations:
        _apply_migrations()

    dataset = synthetic.build_dataset()
    # attachment_state is NOT in d1.TABLE_ORDER (the pipeline writes it via raw SQL in
    # _merge_and_write), so upsert_tables would silently drop it — write it explicitly.
    state_rows = dataset.pop("attachment_state", [])
    counts = d1.upsert_tables(dataset, target="local")
    if state_rows:
        values = ",\n".join(
            f"('{r['attachment_id']}', {int(r['classified_at'])})" for r in state_rows
        )
        d1.execute_sql(
            "INSERT OR REPLACE INTO attachment_state (attachment_id, classified_at) "
            f"VALUES {values};",
            target="local",
        )
    counts["attachment_state"] = len(state_rows)

    # Derive documents from the seeded analyses (real pipeline path), so the documents
    # surface + the document_overpayment alert have backing rows.
    docs_upserted, links_upserted = build_documents("local") if build_docs else (0, 0)

    # The deep-link alerts (feature 018) — written after documents so the overpayment
    # alert's document_id resolves to a real row.
    d1.upsert_tables({"alerts": synthetic.build_alerts()}, target="local")

    images = _upload_images() if upload_images else 0

    summary = {
        "period": synthetic.PERIOD,
        "tables": counts,
        "documents_upserted": docs_upserted,
        "document_links_upserted": links_upserted,
        "alerts": len(synthetic.build_alerts()),
        "images": images,
    }
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Seed local Miniflare D1+R2 with synthetic E2E data.")
    parser.add_argument(
        "--remote",
        action="store_true",
        help="REFUSED — the synthetic seed is local-only and never writes production.",
    )
    args = parser.parse_args(argv)
    if args.remote:
        print("ERROR: the synthetic E2E seed is local-only; --remote is refused.", file=sys.stderr)
        return 2

    summary = seed()
    print(f"Seeded synthetic period {summary['period']}:")
    for table, n in summary["tables"].items():
        print(f"  {table}: {n}")
    print(f"  documents: {summary['documents_upserted']} (links {summary['document_links_upserted']})")
    print(f"  alerts: {summary['alerts']}")
    print(f"  R2 images: {summary['images']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
