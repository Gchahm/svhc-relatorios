# Phase 1 Data Model: Deterministic Entry IDs for Duplicate Natural Keys

No persisted-schema change. This documents the in-memory structures the pure module uses and the
unchanged `entries` mirror columns it reads/derives.

## Persisted entities (unchanged)

### `entries` (mirror table — scraper-owned)

Columns relevant here (all existing; no migration):

| Column | Type | Role in this feature |
|--------|------|----------------------|
| `id` | text (UUID) | The deterministic id whose derivation changes for duplicate natural keys only. |
| `date` | text (`YYYY-MM-DD`) | Part of the natural key. |
| `description` | text | Part of the natural key (normalized, as today). |
| `amount` | real | Part of the natural key (`str(amount)` in the id, as today). |
| `subcategory_id` | text (UUID) | Part of the natural key. |
| `external_document_id` | int (nullable) | First portal doc id (unchanged); the *full* `documento_ids` set drives the discriminator at build time. |

The mirror invariant holds: only the scraper writes `entries`; this feature changes how the
scraper computes `id`, not who writes it, and adds no column.

## In-memory structures (new, in `scripts/scraper/entry_ids.py`)

### `EntryKeyInput`

The minimal per-lancamento input to id assignment, derived from the already-extracted/normalized
lancamento and ref resolution:

| Field | Type | Notes |
|-------|------|-------|
| `date_str` | str | `YYYY-MM-DD` |
| `description` | str | normalized description (fornecedor-prefix stripped, as today) |
| `amount` | float | parsed `valor` |
| `subcategory_id` | str | resolved subcategory id |
| `documento_ids` | list[int] | the entry's portal document id set (may be empty) |

### `AssignedEntryId`

The output per input row, in input order (so the runner zips it back onto its lancamento):

| Field | Type | Notes |
|-------|------|-------|
| `entry_id` | str | the deterministic id (`det_id("entry", period, date, desc, str(amount), subcat, discriminator)`) |
| `discriminator` | str | `"1"` for a singleton; `"doc:<sorted ids>"` (optionally `+ "#<n>"`) or `"<n>"` for duplicates |
| `used_fallback` | bool | True when the occurrence index was needed (no/ambiguous portal discriminator) |

### `AssignResult`

| Field | Type | Notes |
|-------|------|-------|
| `assigned` | list[AssignedEntryId] | same length/order as the input list |
| `fallback_notes` | list[str] | one note per duplicate group that used the index fallback (period, natural key, count) |

### Drift detection structures

- Input `existing`: `list[dict]` of the period's current D1 rows
  `{id, date, description, amount, subcategory_id}` (read pre-upsert, same shape as the
  reconciliation read).
- Input `scraped`: the `AssignResult.assigned` ids paired with their natural keys.
- Output: `list[str]` of drift notes — one per natural key whose id moved (a fresh id absent from
  the existing id set whose natural key already existed under a different id), naming the period,
  the natural key, and the old/new ids.

## Derivation rules (the contract)

1. **Natural key** = `(date_str, description, amount, subcategory_id)`, byte-equal comparison
   (matches today's duplicate detection).
2. **Group**: partition the input rows by natural key.
3. **Singleton group** (size 1): `discriminator = "1"`, `used_fallback = False`. → id byte-identical
   to today's (FR-004).
4. **Duplicate group** (size > 1): partition further by the **doc set key** =
   `tuple(sorted(set(documento_ids)))`.
   - If a row's doc set is non-empty AND unique within the group → `discriminator =
     "doc:" + ",".join(map(str, sorted(set(ids))))`, `used_fallback = False`.
   - If two+ rows share the same doc set, OR a row has an empty doc set → those rows get
     `discriminator = base + "#" + str(n)` where `base` is `"doc:<ids>"` for the shared-doc bucket
     or the empty string for the no-doc bucket, and `n` is the 1-based index within that bucket;
     `used_fallback = True`. One `fallback_note` is recorded for the group.
5. **Uniqueness** (FR-007): within a group the `(doc-set, index)` pairs are distinct by
   construction, and across groups the natural key differs, so all ids are unique within the
   period.
6. **Determinism / order-independence** (FR-002, FR-007): grouping is by value, the doc set is
   sorted+deduped, and the fallback index is assigned in a **stable, value-sorted order within the
   bucket** (not source order) so even the fallback ids are reproducible across a reorder *as long
   as the bucket members are themselves distinguishable*; when bucket members are genuinely
   indistinguishable (identical natural key AND identical doc set) the index is the only separator
   and is assigned by stable source order — this residual case is exactly what the fallback note +
   drift check exist to surface.
