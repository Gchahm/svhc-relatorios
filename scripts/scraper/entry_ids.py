"""Order-independent deterministic entry-id derivation (issue #40 / IMP-003).

An entry's id is ``det_id("entry", period, date, description, str(amount), subcategory_id,
discriminator)``. The first six parts are the entry's *natural key*; the ``discriminator``
disambiguates two ledger lines that share an identical natural key (which happens with split
charges). Historically the discriminator was a 1-based **occurrence index** assigned in the order
the rows appeared in the portal HTML — so if the portal ever reordered two duplicate rows between
scrapes, the entries swapped ids and everything keyed by those ids (attachments, document links,
alert evidence, dashboard deep links) silently re-pointed to the sibling.

This module makes the discriminator prefer an **order-independent portal-native** value derived
from the entry's ``documento_ids`` set (the ``/Dashboard/ViewDocuments/<id>`` ids already extracted
per lancamento). A natural key that occurs exactly once in the period keeps the legacy
discriminator ``"1"`` so its id is byte-identical to before (no churn). A duplicate group whose
members carry distinct doc sets is disambiguated by those sets order-independently; a duplicate
group whose members share/lack a doc set falls back to the occurrence index and records an
enumerable note. On a re-scrape, ``detect_id_drift`` flags any natural key whose id moved.

Kept stdlib-only and free of the scraper's ``playwright`` import so it is directly unit-testable
(see ``scripts/tests/test_entry_ids.py``), mirroring ``scripts/scraper/preserve.py`` /
``reconcile.py`` / ``consistency.py``. This module is PURE: it derives ids/notes from in-memory
data and performs no I/O. The impure D1 read + note threading live in ``runner.py``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from common import det_id as _det_id


# ─── Inputs / outputs ────────────────────────────────────────────────────────


@dataclass
class EntryKeyInput:
    """The minimal per-lancamento input to id assignment (source order preserved)."""

    date_str: str
    description: str
    amount: float
    subcategory_id: str
    documento_ids: list[int] = field(default_factory=list)


@dataclass
class AssignedEntryId:
    """One assigned id, returned in the same order as the corresponding input row."""

    entry_id: str
    discriminator: str
    used_fallback: bool


@dataclass
class AssignResult:
    assigned: list[AssignedEntryId]
    fallback_notes: list[str] = field(default_factory=list)


@dataclass
class ScrapedEntry:
    """A freshly-assigned id paired with its natural key, for drift detection."""

    entry_id: str
    date_str: str
    description: str
    amount: float
    subcategory_id: str


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _natural_key(row: EntryKeyInput) -> tuple[str, str, float, str]:
    return (row.date_str, row.description, row.amount, row.subcategory_id)


def _doc_set_key(documento_ids: list[int]) -> tuple[int, ...]:
    """Order-independent, deduped tuple of the doc ids (the bucket key within a group)."""
    return tuple(sorted(set(documento_ids)))


def entry_discriminator(documento_ids: list[int]) -> str | None:
    """The order-independent portal-native discriminator, or ``None`` when there are no docs.

    Any permutation of the same id set yields the same string; repeats are deduped. Prefixed with
    ``"doc:"`` so its namespace is disjoint from the bare occurrence index (``"1"``, ``"2"``…).
    """
    key = _doc_set_key(documento_ids)
    if not key:
        return None
    return "doc:" + ",".join(str(i) for i in key)


def _entry_id(period: str, row: EntryKeyInput, discriminator: str) -> str:
    return _det_id(
        "entry", period, row.date_str, row.description, str(row.amount), row.subcategory_id, discriminator
    )


# ─── Core: id assignment ───────────────────────────────────────────────────────


def assign_entry_ids(period: str, rows: list[EntryKeyInput]) -> AssignResult:
    """Assign a deterministic, order-independent id to each row.

    Returns one ``AssignedEntryId`` per input row, in input order, plus a list of fallback notes
    (one per duplicate group that had to use the order-dependent occurrence index).

    Rules (see ``specs/034-deterministic-entry-id/data-model.md``):
      * Singleton natural key → discriminator ``"1"`` (byte-identical to the legacy id).
      * Duplicate natural key → bucket the members by their order-independent doc set:
          - a member whose doc set is non-empty AND unique within the group → ``"doc:<ids>"``.
          - members sharing a doc set, or lacking one → ``base + "#<n>"`` (n = 1-based index within
            the bucket), where ``base`` is ``"doc:<ids>"`` for a shared-doc bucket or ``""`` for the
            no-doc bucket. These are the order-dependent fallback cases (one note per group).
    """
    # Partition row indices by natural key, preserving source order within each group.
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        groups[_natural_key(row)].append(i)

    assigned: list[AssignedEntryId | None] = [None] * len(rows)
    fallback_notes: list[str] = []

    for key, indices in groups.items():
        if len(indices) == 1:
            i = indices[0]
            disc = "1"
            assigned[i] = AssignedEntryId(_entry_id(period, rows[i], disc), disc, used_fallback=False)
            continue

        # Duplicate natural key. Bucket by order-independent doc set.
        buckets: dict[tuple[int, ...], list[int]] = defaultdict(list)
        for i in indices:
            buckets[_doc_set_key(rows[i].documento_ids)].append(i)

        group_used_fallback = False
        for doc_set, bucket_indices in buckets.items():
            distinct_bucket = len(bucket_indices) == 1 and bool(doc_set)
            base = entry_discriminator(rows[bucket_indices[0]].documento_ids) if doc_set else ""
            if distinct_bucket:
                # A lone, doc-bearing member: its doc set fully disambiguates it (order-independent).
                i = bucket_indices[0]
                assert base is not None
                assigned[i] = AssignedEntryId(_entry_id(period, rows[i], base), base, used_fallback=False)
            else:
                # Shared doc set, or no docs: the occurrence index is the only separator.
                group_used_fallback = True
                for n, i in enumerate(bucket_indices, start=1):
                    disc = f"{base}#{n}" if base else str(n)
                    assigned[i] = AssignedEntryId(_entry_id(period, rows[i], disc), disc, used_fallback=True)

        if group_used_fallback:
            d, de, a, s = key
            fallback_notes.append(
                f"Entry-id occurrence-index fallback in {period} for duplicate natural key "
                f"(date={d}, amount={a}, subcategory={s}, desc={de[:60]!r}, count={len(indices)}) — "
                f"id stability depends on portal row order for these rows (issue #40 / IMP-003)"
            )

    # All slots filled by construction.
    return AssignResult(assigned=[a for a in assigned if a is not None], fallback_notes=fallback_notes)


# ─── Drift detection (re-scrape) ────────────────────────────────────────────────


def detect_id_drift(period: str, scraped: list[ScrapedEntry], existing: list[dict]) -> list[str]:
    """Flag natural keys whose id MOVED between the prior D1 state and this scrape.

    ``existing`` is the period's current D1 rows (``{id, date, description, amount,
    subcategory_id}``), read BEFORE the upsert. A drift note is emitted for a scraped id that is
    absent from the existing id set AND whose natural key already existed in ``existing`` under a
    different id (i.e. the id moved). An empty ``existing`` (first scrape) yields no notes.
    """
    if not existing:
        return []

    existing_ids: set[str] = {str(r["id"]) for r in existing}
    existing_ids_by_key: dict[tuple, set[str]] = defaultdict(set)
    for r in existing:
        key = (str(r["date"]), str(r["description"]), float(r["amount"]), str(r["subcategory_id"]))
        existing_ids_by_key[key].add(str(r["id"]))

    notes: list[str] = []
    for s in scraped:
        if s.entry_id in existing_ids:
            continue  # id reproduced exactly — no drift
        key = (s.date_str, s.description, float(s.amount), s.subcategory_id)
        prior = existing_ids_by_key.get(key)
        if prior:
            notes.append(
                f"Entry-id drift in {period} for natural key (date={s.date_str}, amount={s.amount}, "
                f"subcategory={s.subcategory_id}, desc={s.description[:60]!r}): natural key existed under "
                f"id(s) {sorted(prior)} but this scrape minted new id {s.entry_id} (issue #40 / IMP-003)"
            )
    return notes
