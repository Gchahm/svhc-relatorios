# Quickstart: Atomic delete-then-insert writebacks

## What changed

Two analysis writebacks now apply their "clear old rows" + "insert new rows" as a **single D1
batch** (one transaction), instead of two separate `wrangler` calls. A failure can no longer commit
the delete without the insert.

- **Attachment analyses** (`scripts/analysis/attachments.py:_merge_and_write`): the
  `classified_at` stamp now rides in the same batch as the analysis insert — a failed insert leaves
  the attachment **pending**, so a re-run heals it automatically.
- **Alerts** (`scripts/analysis/__init__.py:run_analysis`): each period's alerts and the global
  overpayment alerts are cleared + reinserted in one batch — a failure leaves the prior alerts
  intact, never a falsely empty list.

New helper: `common/d1.py:upsert_sql(data) -> str` returns the INSERT SQL without executing it, so
callers compose `DELETE … + INSERT …` into one `execute_sql`.

## Run it

No interface change. The same commands behave the same on success:

```bash
# from scripts/ (uv-managed)
uv run python -m analysis apply-extractions --periodo 2025-12   # attachment writebacks
uv run python -m analysis analyze --periodo 2025-12             # alert writebacks
```

## Verify the fix

Run the unit tests (stdlib unittest, no new dependency, no network):

```bash
# from repo root
python -m unittest discover -s scripts/tests -t scripts
# or: cd scripts && python -m unittest discover -s tests
```

Tests assert:
- `upsert_sql` returns the same INSERTs as `upsert_tables` would execute (and `""` for empty input).
- The attachment writeback submits ONE batch containing the deletes, the insert, and the
  `classified_at` UPDATE — and a simulated insert failure raises without a standalone committed
  delete (attachment stays pending).
- The per-period and overpayment alert writebacks each submit ONE batch (DELETE-only when the new
  set is empty), and a simulated failure leaves prior state intact.

## Manual smoke (optional, local)

```bash
cd scripts
uv run python -m analysis analyze --periodo <some-period>   # succeeds; dashboard alerts unchanged in shape
```

Confirm via the dashboard that alerts/analyses look identical to before for a clean run (parity).
