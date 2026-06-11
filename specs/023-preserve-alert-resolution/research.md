# Research: Preserve user-set alert resolution state across analysis re-runs

No NEEDS CLARIFICATION markers remained from the spec. The research below records the design
decisions for the writeback fix.

## Decision 1: Where to carry resolution state — read-then-graft by id (chosen)

**Decision**: Before each delete in `run_analysis`, `SELECT id, resolved, resolved_at, notes`
for the rows about to be deleted, build a `{id: state}` map of rows that carry user disposition
(`resolved` truthy OR `notes` non-empty), then graft that state onto the freshly-built insert
rows whose id matches. Insert as before.

**Rationale**:
- Alert ids are deterministic (`det_id("alert", period, type, discriminator)` — feature 018 made
  discriminators stable precisely so re-runs are idempotent). The same finding re-emitted has the
  same id as the row the user resolved, so id-matching is reliable (FR-006).
- Re-emitted findings keep disposition (FR-001/FR-002); findings that no longer fire are simply
  not in the new insert set, so they vanish with the delete (FR-003).
- Minimal: reuses the existing delete-then-insert flow; one extra `SELECT` per writeback.

**Alternatives considered**:
- **`INSERT ... ON CONFLICT(id) DO UPDATE` on analysis-owned columns only + explicit delete of
  ids not re-emitted**: also correct and avoids re-reading, but `upsert_tables` currently emits
  `INSERT OR REPLACE` (full-row replace) and would need a new SQL path; it also still needs an
  explicit "delete ids no longer emitted" step. More moving parts than read-then-graft for no
  behavioral gain. Rejected on simplicity (constitution V).
- **Stop deleting; only upsert**: would leave obsolete findings in place forever, violating
  FR-003. Rejected.

## Decision 2: Only carry state for rows that actually have disposition

**Decision**: Build the preservation map only from rows where `resolved` is truthy OR `notes` is
non-empty/non-null. Rows with default state (unresolved, no notes) contribute nothing.

**Rationale**: Default state is exactly what a fresh insert already produces, so grafting it is a
no-op; filtering keeps the map small and the intent explicit. A brand-new alert (no prior row)
correctly stays at the default (FR-005).

## Decision 3: Remove the hardcoded reset in `Alert.to_dict()`

**Decision**: `Alert.to_dict()` currently hardcodes `"resolved": 0, "resolved_at": None,
"notes": None`. Make the default explicit but allow the writeback merge to override. Cleanest:
keep `to_dict()` emitting the default (a freshly-detected alert IS unresolved), and let
`run_analysis` overwrite the three keys on rows whose id is in the preservation map. This keeps
`Alert` a pure value object and puts the merge where the existing-row data is available.

**Rationale**: `Alert` instances are built by the checks and have no knowledge of prior D1 state;
the merge needs the DB read, which lives in `run_analysis`. Per FR-004 the reset must not be the
final word — the explicit graft after `to_dict()` satisfies that without moving DB access into
the model layer.

**Alternatives considered**:
- Pass existing state into `Alert` before `to_dict()`: would couple the model to the DB read and
  spread the merge across two layers. Rejected.

## Decision 4: Share one helper between both writeback paths

**Decision**: Extract `preserve_resolution_state(rows, existing)` (pure dict-merge) and/or a thin
`read_existing_resolution(where_sql, target)` so the per-period path and the global
`document_overpayment` path use identical logic, mirroring the feature-018 single-source-of-truth
discipline.

**Rationale**: Two delete-then-insert sites (lines ~51 and ~62 of `scripts/analysis/__init__.py`)
must behave identically; a shared helper means they cannot drift (an explicit edge case in the
spec).

## Decision 5: Timestamp / SQL-escaping correctness

**Decision**: Read `resolved_at` and `notes` back as-is from D1 and write them through the existing
`upsert_tables` path (which already handles SQL escaping via `_escape_sql`). `resolved` is stored
as an integer 0/1; preserve the integer value. No new escaping logic.

**Rationale**: `notes` is free user text and may contain quotes/newlines — routing it back through
the existing `upsert_tables` escaping avoids a new injection/escaping surface. `query()` returns
D1 JSON rows with the stored types.
