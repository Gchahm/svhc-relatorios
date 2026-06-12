"""Scrape-time consistency validation (IMP-002 / issue #39).

The scraper extracts three independent views of the same money for each period — individual
entries (``lancamentos``), the portal's consolidated per-subcategory subtotals
(``category_subtotals``), and the demonstrativo headline totals (``total_receitas`` /
``total_despesas``) — and writes all three to D1 with no cross-check. If an HTML-parsing
regression drops, double-counts, or mis-attributes a row, nothing notices at scrape time; the
inconsistency surfaces much later as confusing analysis output, by which point it is hard to tell
a scraper bug from genuine (or manipulated) portal data.

This module is the sanity net: after a period's rows are persisted on the scrape-success path, it
cross-checks (a) per-``(subcategory, movement_type)`` entry sums against the recorded subtotals and
(b) the subtotal sums grouped by movement type against the demonstrativo revenue/expense totals.
Any disagreement beyond the reused reconciliation tolerance becomes one idempotent, period-scoped
``scrape_inconsistency`` ``warning`` alert (a ledger that doesn't add up is itself a finding — it
can be a scraper bug OR tampered portal HTML), plus a prominent run-log warning and a note on the
scrape run's ``errors`` field.

This module is PURE (mirrors ``reconcile.py`` / ``preserve.py``): it builds the discrepancy list +
the alert dict + the ONE batched SQL string from already-fetched, in-memory data and performs no
I/O. The impure D1 prior-resolution read and the single batched ``execute_sql`` live in
``runner.py``. Kept stdlib-only and free of the scraper's ``playwright`` import AND of the
``scripts.analysis`` package (the two subsystems share only ``scripts/common``), so it is directly
unit-testable (see ``scripts/tests/test_scrape_consistency.py``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from common import det_id as _det_id, now_ms as _now_ms

# Reconciliation tolerance: a value matches a reference within EITHER an absolute floor (cent-level
# portal rounding) OR a relative band. Mirrors ``scripts/analysis/nf_groups.py:within_tolerance``
# (AMOUNT_ABS_TOL / AMOUNT_REL_TOL = 0.05) — kept as a local copy rather than imported, because the
# scraper must not depend on the analysis package. Same values ⇒ one meaning of "consistent" across
# the system.
AMOUNT_REL_TOL = 0.05
AMOUNT_ABS_TOL = 0.05

ALERT_TYPE = "scrape_inconsistency"
ALERT_SEVERITY = "warning"

__all__ = [
    "AMOUNT_REL_TOL",
    "AMOUNT_ABS_TOL",
    "ALERT_TYPE",
    "ALERT_SEVERITY",
    "within_tolerance",
    "detect_inconsistencies",
    "build_consistency_writeback",
    "Discrepancy",
    "ConsistencyResult",
]


# ─── Data shapes ─────────────────────────────────────────────────────────────


@dataclass
class Discrepancy:
    """One failing comparison."""

    level: str                       # "subcategory" or "demonstrativo"
    movement_type: str               # "C" or "D"
    computed_sum: float              # sum from the more-granular side
    reported_total: float            # the side it is checked against
    difference: float                # round(computed_sum - reported_total, 2)
    subcategory_id: str | None = None  # set for level == "subcategory"

    def to_metadata(self) -> dict:
        d = {
            "level": self.level,
            "movement_type": self.movement_type,
            "computed_sum": self.computed_sum,
            "reported_total": self.reported_total,
            "difference": self.difference,
        }
        if self.subcategory_id is not None:
            d["subcategory_id"] = self.subcategory_id
        return d


@dataclass
class ConsistencyResult:
    sql: str                                   # ONE batch ("" never — always carries the clear DELETE)
    discrepancies: list[Discrepancy] = field(default_factory=list)
    affected_entry_ids: list[str] = field(default_factory=list)
    alert: dict | None = None                  # the alerts row dict rendered into the INSERT, or None
    summary: str | None = None                 # one-line human summary (None when consistent)


# ─── SQL helpers ───────────────────────────────────────────────────────────────


def _sql_str(value) -> str:
    """Escape a value as a SQL literal (single quotes doubled). Mirrors reconcile._sql_str."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'"
    return "'" + str(value).replace("'", "''") + "'"


# ─── Tolerance ───────────────────────────────────────────────────────────────


def within_tolerance(value: float, reference: float) -> bool:
    """True when ``value`` matches ``reference`` within the rounding/relative band."""
    diff = abs(value - reference)
    if diff <= AMOUNT_ABS_TOL:
        return True
    return reference > 0 and diff / reference < AMOUNT_REL_TOL


# ─── Detection ───────────────────────────────────────────────────────────────


def detect_inconsistencies(
    entries: list[dict],
    category_subtotals: list[dict],
    total_receitas: float,
    total_despesas: float,
) -> tuple[list[Discrepancy], list[str]]:
    """Cross-check a period's three views of the money. Pure; no I/O.

    Returns ``(discrepancies, affected_entry_ids)``:
      - subcategory-level: per ``(subcategory_id, movement_type)`` key, the entry-amount sum vs the
        recorded subtotal amount. A key present on only one side is compared against ``0.0`` (catches
        a dropped entry row or a phantom subtotal). C and D within the same subcategory are distinct
        keys, so they never net against each other.
      - demonstrativo-level: the sum of C-typed subtotals vs ``total_receitas`` and the sum of
        D-typed subtotals vs ``total_despesas``.

    ``affected_entry_ids`` is the sorted union of entry ids belonging to any
    ``(subcategory_id, movement_type)`` key that failed the subcategory-level check (empty when only
    the demonstrativo-level check failed) — the feature-018 deep-link key for the alerts dashboard.
    """
    # ── Subcategory-level ──
    entry_sums: dict[tuple[str, str], float] = {}
    entry_ids_by_key: dict[tuple[str, str], list[str]] = {}
    for e in entries:
        key = (e["subcategory_id"], e["movement_type"])
        entry_sums[key] = entry_sums.get(key, 0.0) + (e["amount"] or 0.0)
        entry_ids_by_key.setdefault(key, []).append(e["id"])

    subtotal_amounts: dict[tuple[str, str], float] = {}
    for s in category_subtotals:
        key = (s["subcategory_id"], s["movement_type"])
        # The source already consolidates one subtotal row per key (runner._consolidate_subtotais);
        # sum defensively in case a duplicate slips through.
        subtotal_amounts[key] = subtotal_amounts.get(key, 0.0) + (s["amount"] or 0.0)

    discrepancies: list[Discrepancy] = []
    affected_entry_ids: set[str] = set()
    for key in sorted(set(entry_sums) | set(subtotal_amounts)):
        subcategory_id, movement_type = key
        computed = round(entry_sums.get(key, 0.0), 2)
        reported = round(subtotal_amounts.get(key, 0.0), 2)
        if not within_tolerance(computed, reported):
            discrepancies.append(
                Discrepancy(
                    level="subcategory",
                    movement_type=movement_type,
                    subcategory_id=subcategory_id,
                    computed_sum=computed,
                    reported_total=reported,
                    difference=round(computed - reported, 2),
                )
            )
            affected_entry_ids.update(entry_ids_by_key.get(key, []))

    # ── Demonstrativo-level ──
    c_sum = round(sum(s["amount"] or 0.0 for s in category_subtotals if s["movement_type"] == "C"), 2)
    d_sum = round(sum(s["amount"] or 0.0 for s in category_subtotals if s["movement_type"] == "D"), 2)
    for movement_type, computed, reported in (
        ("C", c_sum, round(total_receitas, 2)),
        ("D", d_sum, round(total_despesas, 2)),
    ):
        if not within_tolerance(computed, reported):
            discrepancies.append(
                Discrepancy(
                    level="demonstrativo",
                    movement_type=movement_type,
                    computed_sum=computed,
                    reported_total=reported,
                    difference=round(computed - reported, 2),
                )
            )

    return discrepancies, sorted(affected_entry_ids)


# ─── Alert construction ──────────────────────────────────────────────────────


def _build_alert(period: str, discrepancies: list[Discrepancy], affected_entry_ids: list[str]) -> dict:
    """Build the ``scrape_inconsistency`` alerts row dict (matches the Alert.to_dict shape)."""
    counts = {
        "subcategory": sum(1 for d in discrepancies if d.level == "subcategory"),
        "demonstrativo": sum(1 for d in discrepancies if d.level == "demonstrativo"),
    }
    metadata = {
        # feature-018 deep-link convention (the alerts UI reads metadata.entry_ids).
        "entry_ids": affected_entry_ids,
        # auditable evidence: every failing comparison with both numbers.
        "checks": [d.to_metadata() for d in discrepancies],
        "counts": counts,
    }
    worst = max(discrepancies, key=lambda d: abs(d.difference))
    n = len(discrepancies)
    return {
        # Stable per-period id → idempotent across re-scrapes.
        "id": _det_id("alert", period, ALERT_TYPE),
        "created_at": _now_ms(),
        "type": ALERT_TYPE,
        "severity": ALERT_SEVERITY,
        "title": f"Ledger does not reconcile — {period} ({n} discrepancy/ies)",
        "description": (
            f"A scrape of {period} found {n} internal consistency mismatch(es): "
            f"{counts['subcategory']} subcategory-level (entries vs subtotals) and "
            f"{counts['demonstrativo']} demonstrativo-level (subtotals vs reported totals). "
            f"Largest disagreement: {worst.level}/{worst.movement_type} "
            f"computed={worst.computed_sum} vs reported={worst.reported_total} "
            f"(diff={worst.difference}). This indicates either a scraper bug or manipulated portal data."
        ),
        "reference_period": period,
        "resolved": 0,
        "resolved_at": None,
        "notes": None,
        "metadata": json.dumps(metadata, ensure_ascii=False),
    }


def _graft_resolution(alert: dict, prior_resolution: dict | None) -> None:
    """Carry the user's prior disposition onto the re-emitted alert (mirrors reconcile._graft_resolution).

    The alert uses a stable deterministic id and re-fires on every re-scrape while the period stays
    inconsistent, so a re-scrape must not silently wipe a resolution/notes the user set. Applied only
    when the prior row actually carries a disposition (``resolved`` truthy OR ``notes`` set); a
    first-time alert keeps the unresolved default. ``resolved`` is coerced to int defensively (wrangler
    ``--json`` returns it as an int, but a string ``"0"`` would be truthy).
    """
    if not prior_resolution:
        return
    resolved = int(prior_resolution.get("resolved") or 0)
    notes = prior_resolution.get("notes")
    if resolved or (notes not in (None, "")):
        alert["resolved"] = resolved
        alert["resolved_at"] = prior_resolution.get("resolved_at")
        alert["notes"] = notes


def _summary(period: str, discrepancies: list[Discrepancy]) -> str:
    worst = max(discrepancies, key=lambda d: abs(d.difference))
    return (
        f"{len(discrepancies)} discrepancy/ies; worst {worst.level}/{worst.movement_type} "
        f"computed={worst.computed_sum} vs reported={worst.reported_total} (diff={worst.difference})"
    )


def build_consistency_writeback(
    period: str,
    entries: list[dict],
    category_subtotals: list[dict],
    total_receitas: float,
    total_despesas: float,
    prior_resolution: dict | None = None,
) -> ConsistencyResult:
    """Detect inconsistencies + build the one-batch SQL + alert dict + summary. Pure; no I/O.

    The returned ``sql`` ALWAYS begins with ``DELETE FROM "alerts" WHERE "id" = <id>;`` (clears any
    prior per-period alert, so a now-consistent re-scrape clears the stale finding — FR-005). When the
    period is inconsistent it appends the ``INSERT OR REPLACE INTO "alerts" (...) VALUES (...);`` row
    (with the user's prior disposition grafted on). Submitting the whole string in one ``execute_sql``
    makes the clear + insert one atomic D1 batch (FR-009).
    """
    discrepancies, affected_entry_ids = detect_inconsistencies(
        entries, category_subtotals, total_receitas, total_despesas
    )

    alert_id = _det_id("alert", period, ALERT_TYPE)
    stmts: list[str] = [f'DELETE FROM "alerts" WHERE "id" = {_sql_str(alert_id)};']

    alert: dict | None = None
    summary: str | None = None
    if discrepancies:
        alert = _build_alert(period, discrepancies, affected_entry_ids)
        _graft_resolution(alert, prior_resolution)
        cols = list(alert.keys())
        col_list = ", ".join(f'"{c}"' for c in cols)
        values = ", ".join(_sql_str(alert[c]) for c in cols)
        stmts.append(f'INSERT OR REPLACE INTO "alerts" ({col_list}) VALUES ({values});')
        summary = _summary(period, discrepancies)

    return ConsistencyResult(
        sql="\n".join(stmts),
        discrepancies=discrepancies,
        affected_entry_ids=affected_entry_ids,
        alert=alert,
        summary=summary,
    )
