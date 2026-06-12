# Phase 0 Research: Deterministic Entry IDs for Duplicate Natural Keys

## R1 — What portal-native identifier is available per entry?

**Decision**: Use the entry's `documento_ids` set (the `/Dashboard/ViewDocuments/<id>` ids already
extracted by `extractors/lancamentos.py` and carried on each lancamento) as the portal-native
discriminator.

**Rationale**: Inspecting the live extractor, the only per-row portal identifier is the document
link id (`re.search(r"/ViewDocuments/(\d+)", href)`). The `<tr>` rows carry only a
`data-group-id` (the subcategory, already part of the natural key) and CSS classes — no per-row
element id. Real data confirms the value: the three identical `ENERGIA ELÉTRICA` charges
(2026-01) each carry a distinct doc id (18990374/375/376), so the doc set fully disambiguates them
order-independently. (Issue suggestion #1.)

**Alternatives considered**:
- A per-row HTML element id — none exists in the portal markup.
- The HTTP request order / DOM index — that *is* the order-dependent thing we are removing.
- A content hash of the row — would change whenever any cell changes and is not "portal-native".

## R2 — How to keep unique-entry ids unchanged (no churn, FR-004)?

**Decision**: A natural key that occurs exactly once in the period keeps the existing final
`det_id` part `"1"`. Only entries in a duplicate group (size > 1) get a non-`"1"` discriminator.

**Rationale**: The current formula is
`det_id("entry", period, date, desc, str(amount), subcat, str(index))` with `index == 1` for the
first (and, for unique keys, only) occurrence. By emitting the literal `"1"` for singletons, the
id is byte-identical to today's for the overwhelmingly common case, bounding churn to the rare
duplicate groups. Verified: `det_id('entry','2026-01','2026-01-20','ENERGIA…','101.76',<subcat>,'1')`
reproduces the current id for a singleton.

**Alternatives considered**:
- Always derive the discriminator from docs (even for singletons) — would change every doc-bearing
  entry's id on the next re-scrape (116 entries today), an unnecessary mass churn rejected by
  FR-004.
- A schema migration to rewrite ids — rejected (Assumptions): the authoritative re-scrape
  reconciliation already self-heals the bounded duplicate-doc set; no migration needed.

## R3 — Discriminator format for a duplicate group with portal docs

**Decision**: For a duplicate natural-key group, the discriminator for an entry is
`"doc:" + ",".join(sorted_unique_str(documento_ids))` when the entry has document ids and the doc
set is unique within the group; this is order-independent (the set is sorted) and distinct from
the bare occurrence index. When two entries in the group share the identical doc set (or both have
none), they additionally get a `#<n>` occurrence suffix within that doc-set bucket and a fallback
note is recorded.

**Rationale**: Sorting+dedup makes FR-002 hold (same set → same value regardless of source order).
Prefixing with `doc:` keeps the discriminator namespace disjoint from the bare index used for
singletons (`"1"`) and for the no-doc fallback, so no accidental id collision across the two
schemes. Keeping the occurrence suffix only inside an identical-doc-set bucket preserves
uniqueness (FR-007) while maximizing determinism.

**Alternatives considered**:
- Use the doc set as the *whole* key (drop the index entirely) — breaks uniqueness when two rows
  genuinely share one invoice (a real split); rejected.
- Hash the doc set — unnecessary; the joined sorted id string is already short, stable, and
  human-readable in logs.

## R4 — How to detect and surface id drift on re-scrape (FR-006)?

**Decision**: Before the upsert, read the period's existing `(id, date, description, amount,
subcategory_id)` rows from D1. After computing the fresh ids, a pure helper flags any fresh id
that is new (not in the existing id set) while its natural key already existed in D1 under a
different id. The runner appends a one-line drift note to the existing `consistency_notes`
accumulator (which lands in `scrape_runs.errors`/notes) and logs a `warning`. No new table, no
alert, no scrape failure.

**Rationale**: The IMP-002 `consistency_notes` channel is the established "queryable run note that
does not flip status to error" mechanism for scrape-time findings; reusing it satisfies the
Assumptions decision (no new schema/dashboard) and matches the project philosophy that row
movements are evidence to review. The read is the same shape and cost as the reconciliation read.
On a first scrape (no prior rows) the helper finds nothing — no false positive.

**Alternatives considered**:
- A `portal_row_vanished`-style `alerts` row — heavier; drift is informational/monitoring and the
  spec (Assumptions) chose the notes channel. Deferred to a follow-up if drift proves frequent.
- Computing drift inside the existing `_reconcile_period` — that read happens *after* upsert (ids
  already overwritten), so a separate *pre-upsert* read is required; kept in its own helper for
  clarity and testability.

## R5 — Where does drift read happen relative to upsert/reconcile?

**Decision**: The drift read is a **pre-upsert** read of the period's existing entries, performed
in the runner right before `upsert_tables`. Drift is computed against the freshly-assigned ids,
the note is collected, and only then does the upsert (which overwrites the ids) run.

**Rationale**: After upsert the old ids are gone (INSERT OR REPLACE by id), so drift must be
measured against the pre-upsert snapshot. This is a read-only `SELECT`, no mirror write (mirror
invariant preserved).

## R6 — Testing approach (SC-005)

**Decision**: Add `scripts/tests/test_entry_ids.py` (stdlib `unittest`) covering: (a)
order-independence — assign ids for the same rows in two orders, assert per-ledger-line id
equality; (b) no-churn — a singleton's id equals the legacy `det_id(...,'1')`; (c) fallback note —
a no-doc duplicate group records a note, a distinct-doc group does not; (d) within-group
uniqueness for same-doc-set duplicates; (e) drift detection — moved id flagged, reproduced ids
not. Run via `python -m unittest discover -s scripts/tests -t scripts`.

**Rationale**: Mirrors the existing pure-module test suites; the spec explicitly requests the
determinism test (SC-005), satisfying Constitution Principle III's "tests when the spec requests
them" clause.
