# Phase 0 Research: Atomic delete-then-insert writebacks

## Decision 1 — Atomicity mechanism: single submitted `wrangler d1 execute --file`

**Decision**: Fold each writeback's `DELETE`/`UPDATE` and `INSERT OR REPLACE` statements into one
SQL string and submit it through a single `d1.execute_sql(sql, target=...)` call.

**Rationale**: `d1.execute_sql` writes the SQL to a temp file and runs `wrangler d1 execute
--file`. D1 executes the statements of one submitted file as a single implicit transaction
(SQLite semantics; `wrangler` wraps a `--file` batch in one transaction), so either all statements
commit or none do. This removes the inter-call window entirely with no new dependency and no schema
change — exactly the "batch atomically" suggestion in issue #37. `execute_sql` already raises
`subprocess.CalledProcessError` on a non-zero exit, so failures stay loud (FR-004).

**Alternatives considered**:
- *Explicit `BEGIN; ... COMMIT;` wrapper*: Rejected — `wrangler d1 execute --file` already runs the
  file's statements transactionally; an explicit `BEGIN` inside it is redundant and risks
  "cannot start a transaction within a transaction" errors against the wrapper's own framing. Keep
  it as a plain multi-statement file (the existing `attachment_analyses` delete already chains 3
  statements in one `execute_sql`, proving the pattern works).
- *Try/except + loud log only (no atomicity)*: Rejected — issue #37 lists this only as a fallback
  "at minimum". A genuinely atomic batch is strictly better and just as simple here.
- *Two-phase: insert to a temp/shadow table then swap*: Rejected — heavy, needs schema, violates
  Simplicity (Principle V) for no benefit over the single-batch approach.

## Decision 2 — Expose INSERT-SQL generation without executing it (`upsert_sql`)

**Decision**: Add `d1.upsert_sql(data: dict[str, list[dict]]) -> str` returning the same batched
`INSERT OR REPLACE` SQL that `upsert_tables` builds (via the existing `build_sql`), **without**
executing it. Refactor `upsert_tables` to call it. Callers that must combine a clear + insert
prepend their `DELETE`/`UPDATE` SQL to `upsert_sql(...)` and submit one `execute_sql`.

**Rationale**: `build_sql` already returns `(sql, counts)`; the INSERT generation is fully reusable.
A thin string-returning helper keeps all SQL generation in `common/d1.py` (Principle II) and lets
the writebacks compose one batch without duplicating escaping/`TABLE_ORDER`/`PRAGMA` logic. The
emitted INSERT rows stay byte-identical to today (FR-006).

**Alternatives considered**:
- *Have callers re-implement INSERT generation*: Rejected — duplicates escaping and ordering,
  risks drift, violates the "single home of SQL generation" invariant in `d1.py`'s docstring.
- *Add an optional `extra_sql=` prefix param to `upsert_tables`*: Rejected as slightly more
  surprising than a clearly named string-builder; `upsert_sql` reads better at the call sites and is
  trivially unit-testable.

## Decision 3 — Attachment writeback: `classified_at` stamp moves into the insert batch

**Decision**: In `attachments._merge_and_write`, build one batch =
`DELETE records; DELETE analysis;` + `upsert_sql({"attachment_analyses": [result.to_dict()]})` +
`UPDATE attachments SET classified_at = <ms> WHERE id = ...;`, submitted in a single `execute_sql`.

**Rationale**: Today the stamp is in the **delete** batch and the insert is a separate call — the
exact self-hiding bug (FR-002): a failed insert leaves the attachment stamped-but-empty. Putting the
stamp in the same batch as the insert means a failed insert rolls back the stamp too, so the
attachment stays pending and the next run heals it (US-2). Statement order within the batch:
deletes → insert → stamp (the stamp last is harmless given atomicity, and reads naturally).

**Alternatives considered**:
- *Two calls, stamp after a verified-successful insert*: Rejected — still two calls; a failure
  between insert and stamp would leave an analysis written but the attachment still pending, causing
  a redundant (idempotent) re-analysis. The single batch avoids even that benign drift and is
  simpler.

## Decision 4 — Alert writebacks: combine DELETE + INSERT per scope

**Decision**: For each per-period writeback and the global overpayment writeback in
`run_analysis`, build one batch = `DELETE FROM alerts WHERE <scope>;` + (when rows exist)
`upsert_sql({"alerts": rows})`, submitted in a single `execute_sql`. When `rows` is empty, submit
just the `DELETE` (still one call) so the scope correctly clears to empty (FR-005, US-1 scenario 2).
The resolution-preservation read (`_read_existing_resolution`) and `_graft_resolution` happen
**before** building the batch, unchanged (FR-007).

**Rationale**: Removes the delete-then-insert window for alerts (US-1) — the worst failure mode for
an auditing tool. Reusing `upsert_sql` keeps the inserted rows identical (FR-006) and the grafting
logic untouched (FR-007). The overpayment write stays a single global delete-by-type + insert.

**Alternatives considered**:
- *One mega-batch for all periods + overpayment*: Rejected — periods are computed independently and
  the per-period log line ("N alerts written") is useful operationally; per-scope batches keep the
  failure blast radius to one scope and preserve the existing logging. Each scope is individually
  atomic, which is what US-1 requires.

## Decision 5 — Testing approach: stdlib `unittest`, monkeypatched D1 seam

**Decision**: Add `scripts/tests/` with stdlib `unittest` modules that monkeypatch
`common.d1.execute_sql` / `common.d1.upsert_tables` (and `query`) to capture submitted SQL instead
of shelling out to `wrangler`. Assertions: (1) exactly one `execute_sql` per writeback scope; (2)
the captured batch contains the `DELETE` and the `INSERT` (and, for attachments, the
`classified_at UPDATE`) together; (3) a simulated `execute_sql` failure raises and no separate
committed delete occurred; (4) `upsert_sql` output equals the INSERT portion of `build_sql`.

**Rationale**: The real write goes through an external CLI/network, which cannot be failure-injected
deterministically in CI; intercepting the in-process seam tests the exact guarantees the FRs state.
`unittest` is stdlib (no new dependency, runnable here), satisfying the constitution's stance on
tests being added only when runnable.

**Alternatives considered**:
- *pytest*: Rejected — would add a dependency the repo doesn't configure; `unittest` covers these
  seam tests fully.
- *Real local Miniflare D1 integration test*: Rejected for the atomicity assertions (can't inject a
  mid-batch failure), though a happy-path parity check could run there; kept out of scope to avoid
  flakiness and `wrangler` dependence in the test suite.
