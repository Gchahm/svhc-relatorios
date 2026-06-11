# Behavioral Contract: Alert writeback preserves user resolution state

This feature changes no HTTP API. The contract here is the **internal writeback behavior** of the
analysis pipeline (`run_analysis` in `scripts/analysis/__init__.py`). It is the testable surface.

## Contract: `run_analysis` alert writeback (both per-period and global `document_overpayment`)

### Preconditions
- D1 reachable via `scripts/common/d1.py` (`query` / `execute_sql` / `upsert_tables`).
- Alert ids are deterministic for a given (period, type, discriminator).

### Guarantees

For each writeback scope S (per-period `reference_period = '<p>'`; global `type =
'document_overpayment'`):

1. **Preserve on re-emit** — For every freshly-built alert row R whose `id` matches an existing
   row E in scope S where E carried user disposition (`E.resolved` truthy OR `E.notes` non-empty):
   the written row has `resolved = E.resolved`, `resolved_at = E.resolved_at`, `notes = E.notes`.
2. **Drop the obsolete** — Any existing row in scope S whose `id` is NOT among the freshly-built
   rows is absent after the writeback (deleted, not preserved).
3. **Default the new** — Any freshly-built row whose `id` had no prior row (or whose prior row
   carried no disposition) is written `resolved = 0/false`, `resolved_at = NULL`, `notes = NULL`.
4. **Idempotent** — Running the writeback twice with the same detected alerts and no user action
   leaves `resolved` / `resolved_at` / `notes` byte-identical between the two runs.
5. **Scope isolation** — A per-period writeback for period P does not read or alter resolution
   state of alerts outside P; the global `document_overpayment` writeback only touches that type.

### Failure modes
- Existing-state `SELECT` returns no rows → preservation map empty → behaves as a clean insert
  (all rows default). Acceptable.
- Free-text `notes` with quotes/newlines → routed back through `upsert_tables` escaping; no SQL
  breakage.

## Verification (manual — no test framework per constitution III)

See `quickstart.md` for the exact CLI + UI steps that exercise guarantees 1–4.

### Acceptance mapping

| Guarantee | Spec requirement | Spec scenario |
|-----------|------------------|---------------|
| 1         | FR-001, FR-002   | US1 #1, #2, #3 |
| 2         | FR-003           | US2 #1        |
| 3         | FR-005           | edge: re-appear after gap |
| 4         | FR-007           | SC-004        |
| 5         | FR-002           | edge: two writeback paths |
