# Contract: NF grouping helper & reconciliation

**Feature**: 005-nf-multi-entry-reconciliation

No HTTP API. The contracts here are the Python function signatures the feature introduces/changes and their behavioral guarantees.

## `scripts/scraper/analise/nf_groups.py` (new)

```python
def content_hash(file_path: str) -> str | None:
    """Joined md5 of the document's page image files (the `;`-separated paths in
    `file_path`). Returns None if no page file can be read.
    Resolves paths the same way documentos.py does."""

def group_documents(documents: list[dict]) -> dict[str, list[dict]]:
    """Map content_hash -> list of document dicts that share byte-identical pages.
    Documents whose pages can't be hashed are returned each in their own singleton
    group keyed by document id (never merged on failure)."""
```

**Guarantees**:

- Two documents are grouped **iff** their page bytes are identical (exact, not fuzzy).
- Single-entry documents end up in singleton groups → callers preserve existing behavior.
- Pure / no side effects; safe to call from both the analysis stage and the check.

## `documentos.py` (changed)

`run_document_analysis(...)` behavioral contract (additions):

- Builds NF groups over **all** period documents/entries (not the filtered work list).
- Invokes the VLM **once per group** and fans the page records + roll-up out to a
  `DocAnalysisResult` per sibling document (each retains its own `document_id`).
- Sets `amount_match` from **group reconciliation** when group size > 1 (per the
  data-model table); identical single-entry behavior when group size == 1.
- Never raises on an unreadable page or missing NF total — degrades gracefully.

**Guarantees**:

- SC-002: single-entry documents retain their prior `amount_match`.
- SC-003: a within-tolerance group is reconciled (all siblings `amount_match = True`).
- SC-005: one VLM pass per unique shared NF.

## `checks/` — `check_duplicate_billing(period, refs, analyses_by_doc)` (new)

```python
def check_duplicate_billing(p: PeriodData, refs: RefIndex) -> list[Alert]:
    """Group p.documents by content hash; for each multi-entry group read the NF
    gross total from p.raw['document_analyses']; emit one critical
    'duplicate_billing' Alert when sum(sibling amounts) - nf_total > tolerance."""
```

**Guarantees**:

- SC-004: over-claim group → exactly one alert; correctly-summing split → none;
  under-claim → none (treated as plain mismatch, not over-claim).
- FR-009: a group with no extractable NF total is skipped (no alert).
- Idempotent: same group → same deterministic alert `id` across re-runs.
- Registered in `run_all_checks` so `run_analysis` persists it into `raw["alerts"]`.

## Verification (no automated test framework)

Run over the committed fixtures and assert the issue's confirmed outcomes:

- `2025-12.json`: NF `1057` quad and TPA internet pair → `amount_match` not False; one VLM pass per group.
- Synthetic over-claim (siblings sum > total) → one `duplicate_billing` alert.
- Synthetic correctly-summing split → zero `duplicate_billing` alerts.
