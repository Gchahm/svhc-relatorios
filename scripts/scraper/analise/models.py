"""Data models for the analysis module."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Alert:
    id: str
    type: str
    severity: str  # "critical", "warning", "info"
    title: str
    description: str
    reference_period: str
    metadata: dict = field(default_factory=dict)
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "reference_period": self.reference_period,
            "metadata": json.dumps(self.metadata, ensure_ascii=False) if self.metadata else None,
            "resolved": 0,
            "resolved_at": None,
            "notes": None,
        }


@dataclass
class PeriodData:
    period: str
    raw: dict
    report: dict
    entries: list[dict]
    category_subtotals: list[dict]
    documents: list[dict]

    @property
    def debit_entries(self) -> list[dict]:
        return [e for e in self.entries if e["movement_type"] == "D"]

    @property
    def credit_entries(self) -> list[dict]:
        return [e for e in self.entries if e["movement_type"] == "C"]

    @property
    def total_debits(self) -> float:
        return sum(e["amount"] for e in self.debit_entries)

    @property
    def total_credits(self) -> float:
        return sum(e["amount"] for e in self.credit_entries)

    @property
    def entry_ids_with_documents(self) -> set[str]:
        return {d["entry_id"] for d in self.documents}


class RefIndex:
    """Merged reference data across all periods."""

    def __init__(self):
        self.categories: dict[str, dict] = {}
        self.subcategories: dict[str, dict] = {}
        self.vendors: dict[str, dict] = {}
        self.units: dict[str, dict] = {}
        # vendor_id -> earliest period seen
        self.vendor_first_seen: dict[str, str] = {}

    def merge_period(self, data: dict, period: str):
        for cat in data.get("categories", []):
            self.categories[cat["id"]] = cat
        for sub in data.get("subcategories", []):
            self.subcategories[sub["id"]] = sub
        for v in data.get("vendors", []):
            self.vendors[v["id"]] = v
            if v["id"] not in self.vendor_first_seen or period < self.vendor_first_seen[v["id"]]:
                self.vendor_first_seen[v["id"]] = period
        for u in data.get("units", []):
            self.units[u["id"]] = u

    def subcategory_name(self, sub_id: str) -> str:
        sub = self.subcategories.get(sub_id, {})
        return sub.get("name", sub_id[:8])

    def category_name(self, sub_id: str) -> str:
        sub = self.subcategories.get(sub_id, {})
        cat_id = sub.get("category_id", "")
        cat = self.categories.get(cat_id, {})
        return cat.get("name", cat_id[:8])

    def vendor_name(self, vendor_id: str) -> str:
        v = self.vendors.get(vendor_id, {})
        return v.get("name", vendor_id[:8])
