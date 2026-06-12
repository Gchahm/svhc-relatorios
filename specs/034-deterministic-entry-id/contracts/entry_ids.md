# Contract: `scripts/scraper/entry_ids.py` (pure, stdlib-only)

This feature has no HTTP API surface. The "contracts" are the pure functions in the new module
and the runner glue. All functions are deterministic and perform no I/O (the impure D1 read +
note threading stay in `runner.py`), mirroring `reconcile.py`/`consistency.py`.

## `entry_discriminator(documento_ids: list[int]) -> str | None`

- **Input**: an entry's portal document id list (may be empty, may contain duplicates / any order).
- **Output**: `"doc:" + ",".join(map(str, sorted(set(documento_ids))))` when non-empty; `None`
  when empty.
- **Guarantees**: order-independent (FR-002) — any permutation of the same set yields the same
  string; dedups repeats.

## `assign_entry_ids(period: str, rows: list[EntryKeyInput]) -> AssignResult`

- **Input**: the period and the ordered list of entry-build inputs (date, description, amount,
  subcategory_id, documento_ids), in source order.
- **Output**: `AssignResult(assigned: list[AssignedEntryId], fallback_notes: list[str])` where
  `assigned` is the SAME length and order as `rows`.
- **Guarantees**:
  - Each `assigned[i].entry_id == det_id("entry", period, date, description, str(amount),
    subcategory_id, discriminator)`.
  - Singleton natural key → `discriminator == "1"` (byte-identical to the legacy id — FR-004).
  - Duplicate natural key with distinct portal doc sets → discriminator is the order-independent
    `"doc:<sorted ids>"`; `used_fallback == False`; no fallback note (FR-001, FR-005).
  - Duplicate natural key with shared/empty doc sets → discriminator carries a `#<n>` index suffix;
    `used_fallback == True`; exactly one fallback note per such group naming period + natural key +
    count (FR-003, FR-005).
  - All `entry_id`s unique within the period (FR-007).
  - Pure & deterministic: same `rows` (in any duplicate-group permutation that preserves
    distinguishability) → same ids (FR-007, SC-005).

## `detect_id_drift(period: str, scraped: list[ScrapedEntry], existing: list[dict]) -> list[str]`

- **Input**: the period; the freshly-assigned `(entry_id, natural_key)` pairs; the period's
  existing D1 rows `{id, date, description, amount, subcategory_id}` (read pre-upsert).
- **Output**: a list of one-line drift notes — one per natural key whose id moved (a scraped id
  absent from the existing id set whose natural key already existed in `existing` under a
  different id), naming period, natural key, and old→new ids.
- **Guarantees**:
  - Empty `existing` (first scrape) → `[]` (FR-006, no false positive).
  - A scrape that reproduces every existing id for its natural key → `[]` (FR-006).
  - A natural key whose id changed → exactly one note (FR-006, SC-004).
  - Pure — no I/O.

## Runner glue (impure, in `runner.py`)

- In `_scrape_periodo`'s entry build: assemble `EntryKeyInput`s, call `assign_entry_ids`, zip the
  resulting ids back onto the entry rows (replacing the old `entry_key_counts`/`_entry_id` inline
  logic). Collect `fallback_notes` into the period's `_parse_notes`-style note channel (so the
  runner surfaces them through `consistency_notes`, never into D1).
- In `run_scrape`'s success path, BEFORE `upsert_tables`: read the period's existing entries via
  `d1.query`, call `detect_id_drift`, and append any returned notes to `consistency_notes` (with a
  `logger.warning`). The read is read-only; no mirror write.
