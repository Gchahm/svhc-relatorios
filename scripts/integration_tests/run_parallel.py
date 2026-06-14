"""Parallel runner for the real-D1 integration suite (feature 063 / issue #109 / DX-002).

The integration modules under ``scripts/integration_tests/`` each drive the UNSTUBBED pipeline
against local Miniflare D1/R2 through ``scripts/common/d1.py`` (every op is a ``wrangler``
subprocess), so the serial ``unittest discover`` run scales linearly with the module count.

This runner shards the suite **one module per task** across ``min(module_count, cpu_count)``
worker SUBPROCESSES, each pinned to its **own** isolated persist dir
(``SVHC_WRANGLER_PERSIST=.wrangler/state-test-w<i>`` — the feature-061 / issue #107 selector), so
concurrent modules never race on a shared local database. Each worker seeds its DB **once** then
runs the module(s) it was assigned, reusing the seeded DB across them.

Two modes (one re-entrant file):

* **parent** (default): discover modules → partition across workers → spawn worker subprocesses →
  aggregate per-module pass/fail into one exit code → clean up the per-worker dirs.
* **worker** (``--worker <persist-dir> <module...>``): seed once, run the assigned modules in
  process, emit one ``##RESULT## {json}`` line per module.

Run via ``pnpm test:py:integration`` (from ``scripts/``: ``uv run python -m
integration_tests.run_parallel``). The serial fallback is ``pnpm test:py:integration:serial``.

This is test infrastructure: stdlib only, LOCAL only (no ``--remote`` path), no D1 schema change.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _THIS_DIR.parent
_REPO_ROOT = _SCRIPTS_DIR.parent

_RESULT_PREFIX = "##RESULT## "
_DEFAULT_PERSIST_PREFIX = ".wrangler/state-test-w"


# --------------------------------------------------------------------------- discovery


def discover_modules() -> list[str]:
    """Sorted distinct dotted names of the integration test modules (``test_*.py``).

    Uses ``unittest`` discovery (the same mechanism the serial command uses) so the parallel run
    covers exactly the same modules.
    """
    loader = unittest.TestLoader()
    suite = loader.discover(str(_THIS_DIR), pattern="test_*.py", top_level_dir=str(_SCRIPTS_DIR))
    modules: set[str] = set()

    def _walk(s) -> None:
        for x in s:
            if isinstance(x, unittest.TestSuite):
                _walk(x)
            else:
                modules.add(type(x).__module__)

    _walk(suite)
    return sorted(modules)


def partition(modules: list[str], n_workers: int) -> list[list[str]]:
    """Round-robin partition (cost-aware proxy) of ``modules`` into ``n_workers`` buckets.

    A plain round-robin over the *sorted* module list spreads modules evenly; since the dominant
    cost is a few slow modules, round-robin keeps at most ~one slow module per worker in practice
    and avoids the worst case of stacking the slowest two onto one worker. Empty buckets are
    dropped (so fewer modules than requested workers ⇒ fewer real workers).
    """
    buckets: list[list[str]] = [[] for _ in range(max(n_workers, 1))]
    for i, m in enumerate(modules):
        buckets[i % len(buckets)].append(m)
    return [b for b in buckets if b]


# --------------------------------------------------------------------------- worker mode


def run_worker(persist_dir: str, modules: list[str]) -> int:
    """Worker entrypoint: seed the isolated DB once, then run each assigned module in process.

    ``SVHC_WRANGLER_PERSIST`` must already be set in this process's env to ``persist_dir`` (the
    parent sets it); we assert that so a stray manual invocation can't silently hit the shared DB.
    Returns 0 iff every assigned module passed.
    """
    env_dir = os.environ.get("SVHC_WRANGLER_PERSIST")
    if env_dir != persist_dir:
        print(
            f"ERROR: worker SVHC_WRANGLER_PERSIST={env_dir!r} != --worker {persist_dir!r}",
            file=sys.stderr,
        )
        return 2

    # Import lazily so the parent's discovery doesn't pay the seed-module import cost.
    from common import d1
    from e2e import seed as seed_module

    # Apply migrations ONCE for this worker's DB (the schema is stable); rows are reset to the
    # clean seed baseline BEFORE EACH module so modules sharing this worker's DB cannot
    # contaminate each other. A whole-DB re-seed (not the scoped _harness.restore, which only
    # touches the synthetic period's analysis-owned rows) is required because a module may
    # mutate rows the scoped restore does not cover — e.g. add an attachment_state row for a
    # seed-pending attachment (INSERT OR REPLACE can't delete an ADDED row), prune documents, or
    # hard-delete mirror rows (reconcile cascade). Re-seeding from scratch heals all of those.
    loader = unittest.TestLoader()
    overall_ok = True
    migrated = False
    for module in modules:
        # Reset to baseline. First module: full seed incl. migrations. Subsequent: drop the
        # synthetic period clean + re-seed rows/docs/alerts/images (migrations already applied).
        if not migrated:
            seed_module.seed(apply_migrations=True)
            migrated = True
        else:
            _reset_db(d1, seed_module)

        suite = loader.loadTestsFromName(module)
        start = time.monotonic()
        runner = unittest.TextTestRunner(verbosity=2, stream=sys.stderr)
        result = runner.run(suite)
        duration = time.monotonic() - start
        passed = result.wasSuccessful()
        overall_ok = overall_ok and passed
        print(
            _RESULT_PREFIX
            + json.dumps(
                {
                    "module": module,
                    "passed": passed,
                    "tests_run": result.testsRun,
                    "duration_s": round(duration, 2),
                }
            ),
            flush=True,
        )
    return 0 if overall_ok else 1


def _reset_db(d1, seed_module) -> None:
    """Reset this worker's DB to the clean seed baseline WITHOUT re-migrating.

    Deletes every row from every table the seed touches (schema-only DB), then re-seeds the
    synthetic period incl. documents + alerts + R2 images. This is a true clean slate — it heals
    rows a prior module ADDED (which an INSERT OR REPLACE re-seed cannot remove), DELETED (mirror
    hard-deletes), or pruned (documents). R2 objects are deterministic by key, so the re-seed's
    INSERT-or-overwrite restores them; stray objects a module created are harmless (tests assert
    presence of known keys, never absence). Migrations are NOT reapplied (schema is stable),
    keeping the reset cheap relative to a full dir wipe.
    """
    # DELETE child→parent. attachment_state is not in TABLE_ORDER (raw-SQL owned), so include it.
    delete_order = [
        "data_corrections",
        "alerts",
        "document_entries",
        "documents",
        "attachment_analysis_records",
        "attachment_analyses",
        "page_classifications",
        "attachment_state",
        "approvers",
        "category_subtotals",
        "attachments",
        "entries",
        "accountability_reports",
        "subcategories",
        "units",
        "vendors",
        "categories",
        "scrape_runs",
    ]
    stmts = "PRAGMA defer_foreign_keys = ON;\n" + "".join(
        f"DELETE FROM {t};\n" for t in delete_order
    )
    d1.execute_sql(stmts, target="local")
    # Re-seed the full synthetic baseline (no migrations; rows + documents + alerts + images).
    seed_module.seed(apply_migrations=False)


# --------------------------------------------------------------------------- parent mode


def _spawn_worker(index: int, persist_prefix: str, modules: list[str]) -> dict:
    """Run one worker subprocess; capture its output + parse the per-module result lines."""
    persist_dir = f"{persist_prefix}{index}"
    env = dict(os.environ)
    env["SVHC_WRANGLER_PERSIST"] = persist_dir
    cmd = [
        sys.executable,
        "-m",
        "integration_tests.run_parallel",
        "--worker",
        persist_dir,
        *modules,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(_SCRIPTS_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    results = []
    for line in proc.stdout.splitlines():
        if line.startswith(_RESULT_PREFIX):
            try:
                results.append(json.loads(line[len(_RESULT_PREFIX) :]))
            except json.JSONDecodeError:
                pass
    # A module that never emitted a result line (worker crashed mid-module) is a failure.
    emitted = {r["module"] for r in results}
    for m in modules:
        if m not in emitted:
            results.append({"module": m, "passed": False, "tests_run": 0, "duration_s": 0.0})
    return {
        "index": index,
        "persist_dir": persist_dir,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "results": results,
    }


def _cleanup(persist_prefix: str, indices: list[int]) -> None:
    """Remove each per-worker persist dir (relative paths resolve against the repo root)."""
    for i in indices:
        raw = Path(f"{persist_prefix}{i}")
        path = raw if raw.is_absolute() else _REPO_ROOT / raw
        shutil.rmtree(path, ignore_errors=True)


def run_parent(workers_cap: int | None, persist_prefix: str) -> int:
    modules = discover_modules()
    if not modules:
        print("no integration modules found — nothing to run.")
        return 0

    cpu = os.cpu_count() or 1
    n_workers = min(len(modules), cpu)
    if workers_cap is not None:
        n_workers = max(1, min(n_workers, workers_cap))

    buckets = partition(modules, n_workers)
    n_workers = len(buckets)  # may shrink if fewer modules than workers
    indices = list(range(n_workers))

    print(
        f"Parallel integration run: {len(modules)} modules across {n_workers} workers "
        f"(cpu={cpu}); persist dirs '{persist_prefix}0..{n_workers - 1}'."
    )

    start = time.monotonic()
    worker_outputs: list[dict] = []
    try:
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = [
                pool.submit(_spawn_worker, i, persist_prefix, buckets[i]) for i in indices
            ]
            for fut in futures:
                worker_outputs.append(fut.result())
    finally:
        _cleanup(persist_prefix, indices)

    wall = time.monotonic() - start

    # Aggregate.
    all_results = [r for w in worker_outputs for r in w["results"]]
    failed_workers = [w for w in worker_outputs if w["returncode"] != 0]
    overall_ok = all(r["passed"] for r in all_results) and not failed_workers

    # Per-module timing table (sorted slowest-first so the wall-clock driver is obvious).
    print("\n=== Per-module results (slowest first) ===")
    for r in sorted(all_results, key=lambda r: r["duration_s"], reverse=True):
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['module']:<48} {r['tests_run']:>3} tests  {r['duration_s']:>7.2f}s")
    total_tests = sum(r["tests_run"] for r in all_results)
    print(
        f"\n{len(all_results)} modules, {total_tests} tests, "
        f"{n_workers} workers, wall-clock {wall:.2f}s — "
        f"{'PASS' if overall_ok else 'FAIL'}"
    )

    # On failure, replay the failing workers' captured output for diagnosis.
    if not overall_ok:
        for w in worker_outputs:
            failed_mods = [r["module"] for r in w["results"] if not r["passed"]]
            if w["returncode"] != 0 or failed_mods:
                print(
                    f"\n----- worker {w['index']} output ({w['persist_dir']}, "
                    f"rc={w['returncode']}, failed: {failed_mods or 'crash'}) -----",
                    file=sys.stderr,
                )
                sys.stderr.write(w["stderr"])
                sys.stderr.write(w["stdout"])

    return 0 if overall_ok else 1


# --------------------------------------------------------------------------- CLI


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the real-D1 integration suite in parallel.")
    parser.add_argument(
        "--worker",
        metavar="PERSIST_DIR",
        help="WORKER MODE: seed PERSIST_DIR once then run the given modules in process.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Cap on worker count (default min(module_count, cpu_count)).",
    )
    parser.add_argument(
        "--persist-prefix",
        default=_DEFAULT_PERSIST_PREFIX,
        help=f"Base for per-worker persist dirs (default '{_DEFAULT_PERSIST_PREFIX}').",
    )
    parser.add_argument("modules", nargs="*", help="WORKER MODE: modules to run.")
    args = parser.parse_args(argv)

    if args.worker:
        return run_worker(args.worker, args.modules)
    return run_parent(args.workers, args.persist_prefix)


if __name__ == "__main__":
    raise SystemExit(main())
