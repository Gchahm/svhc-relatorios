# Research: Prune stale documents and links after re-classification

All Technical Context items were resolvable from the existing codebase; no external research needed.
The decisions below resolve the implementation choices the spec left to planning.

## Decision 1 — Authoritative replace vs. surgical diff

**Decision**: Make `build_documents` an authoritative write of the complete desired state. Within one
atomic D1 batch, DELETE the stale rows (those whose id is not in this run's desired sets) and
INSERT-OR-REPLACE the desired rows (the existing upsert).

**Rationale**: `build_documents` already reads ALL `attachment_analyses` globally and computes the
complete `docs`/`links` sets, so the desired state is fully known each run. `documents` and
`document_entries` carry no user-owned state to preserve (only `alerts` carry resolution/notes —
confirmed below), so a delete-then-reinsert is safe and is exactly the idiom already used for the alert
and attachment writebacks (feature 024). This is the smallest change that satisfies FR-001..FR-004.

**Alternatives considered**:
- *Surgical diff (compute add/remove deltas in Python, issue targeted DELETEs)*: more code, same DB
  effect; rejected for complexity with no benefit at this scale.
- *Delete all + reinsert unconditionally every run*: simplest, but the issue's "log pruned Y" and the
  idempotency success criterion (SC-004 "changes 0 rows") read more naturally against a NOT-IN prune
  that touches only stale rows. We keep INSERT-OR-REPLACE for the desired rows (so unchanged rows are
  re-asserted identically) and DELETE only the non-desired ids. (Functionally a full replace, but the
  prune is scoped to stale ids so the log can report a real pruned count.)

## Decision 2 — How to express the prune in SQL

**Decision**: Two `DELETE` statements keyed on the desired-id sets:
`DELETE FROM document_entries WHERE id NOT IN (<desired link ids>);` and
`DELETE FROM documents WHERE id NOT IN (<desired doc ids>);`. When a desired set is empty, the prune
becomes an unconditional `DELETE FROM document_entries;` / `DELETE FROM documents;` (since `NOT IN ()`
is invalid SQL and the empty desired state means "remove everything"). Delete links before documents so
no document is removed while a (about-to-be-removed) link still references it; with
`PRAGMA defer_foreign_keys = ON` (set by `build_sql`) ordering is not strictly required, but
links-before-documents is the natural, FK-safe order.

**Rationale**: `NOT IN (<id list>)` against the exact desired ids is the direct expression of
"remove anything not in the desired set" and reuses the same id-escaping the upsert already does. The
empty-set special case is required because SQLite rejects `NOT IN ()`.

**Alternatives considered**:
- *`DELETE … WHERE id IN (<stale ids>)` after reading existing ids and diffing*: needs the read result
  to build the list anyway; `NOT IN (desired)` avoids depending on a possibly-stale read for
  correctness (the read is used only for the pruned-count log, not to drive the delete).

## Decision 3 — Atomic batching seam

**Decision**: Build the combined SQL as `"<delete links>;\n<delete docs>;\n" + d1.upsert_sql({...})`
and run it with a single `d1.execute_sql(...)`. `upsert_sql` returns the PRAGMA header + INSERTs (or
`""` when there are no desired rows). When BOTH the prune and the upsert are no-ops the combined SQL is
empty and we skip the call.

**Rationale**: This is exactly the pattern `run_analysis` uses for alerts and `_merge_and_write` uses
for attachment analyses — one `execute_sql` = one wrangler invocation = one D1 implicit transaction, so
a partial failure cannot commit the delete without the insert (FR-005). The `upsert_sql` seam exists
precisely so callers can prepend their own DELETEs and submit one batch (feature 024).

**Alternatives considered**:
- *`d1.upsert_tables(...)` (current) then a separate `execute_sql` for the deletes*: two wrangler
  calls = two transactions; a failure between them leaves a half-applied state — the exact class of bug
  feature 024 fixed. Rejected.

## Decision 4 — Reporting pruned counts (FR-008)

**Decision**: Before writing, read the current persisted id sets
(`SELECT id FROM documents` / `SELECT id FROM document_entries`) and compute pruned counts as
`existing_ids - desired_ids`. Log `"%d document(s), %d link(s) upserted; pruned %d document(s), %d
link(s); %d analysis(es) skipped"`. Return value extended is unnecessary for callers (only `run_analysis`
calls it and ignores the return); keep the `(docs, links)` upserted tuple as the return type for
backward compatibility, surface pruned counts via the log only.

**Rationale**: The read is cheap (id-only) and gives a precise pruned count for the log without
changing the function's return contract. SC-005 ("reports the pruned counts") is a log requirement.

**Alternatives considered**:
- *Use wrangler's affected-rows meta from the DELETE*: `execute_sql` does not surface per-statement
  meta (it uses `--file`, not `--json`), so a pre-read is the straightforward way to count.

## Confirmation — no user-owned state on the pruned tables (A-002)

Searched `src/` and `scripts/` for writes to `documents` / `document_entries`: the only writer is
`build_documents` (derived data) and the read-only API/UI under `src/app/api/documents` +
`/dashboard/documents`. User-owned analysis state (resolution/notes) lives only on `alerts`. Therefore
pruning may delete-and-reinsert these two tables freely with no resolution-preservation graft.
