# Contract: extraction-provider seam (D1-backed)

The single seam decoupling the deterministic merge from where per-page extractions come from. Lives
in `scripts/analysis/attachments.py` (`build_attachment_analysis(..., provider)`); the
implementation moves from file-backed to D1-backed.

## Signature (changed)

```python
# Before (file-backed):
#   provider(path: str) -> tuple[dict | None, str | None]
# After (D1-backed):
provider(attachment_id: str, page_label: str) -> tuple[dict | None, str | None]
```

Rationale for the key change: page-image filenames are named by **entry**, not attachment, so a
path does not identify the attachment. `build_attachment_analysis` already has `attachment_id` and
derives `page_label` per page (`_page_label_from_path(path, idx)`), so it calls the provider with the
identity pair instead of the path.

## Return contract (unchanged semantics)

- `(fields, None)` — the parsed fields object for the page.
- `(None, reason)` — the page is a recorded error result (`reason` = the stored error).
- `(None, "no classification for page (run classify-doc-page)")` — no row exists for this
  (attachment_id, page_label).

`build_attachment_analysis` keeps its existing handling: a `None` fields → a per-page `parse_error`
record (does not abort the attachment); at least one parseable page → roll-up; zero parseable pages
→ the attachment-level `"no page produced a parseable response"` error.

## D1-backed implementation: `D1ExtractionProvider`

Constructed from the period's batch-loaded staging rows (one query per period via the loader), so
lookups are in-memory:

```python
class D1ExtractionProvider:
    def __init__(self, rows: list[dict]):
        # key: (attachment_id, page_label) -> row; response already decoded to dict by the loader
        self._by_key = {(r["attachment_id"], r["page_label"]): r for r in rows}

    def __call__(self, attachment_id: str, page_label: str) -> tuple[dict | None, str | None]:
        row = self._by_key.get((attachment_id, page_label))
        if row is None:
            return None, "no classification for page (run classify-doc-page)"
        if row.get("error"):
            return None, str(row["error"])
        resp = row.get("response")
        if not isinstance(resp, dict):
            return None, "invalid classification (no fields recorded)"
        return resp, None
```

## Loader contribution

`loader._load_period_raw` adds `raw["page_classifications"]`: the rows for the period's attachments
(joined attachments→entries→report), with `response` JSON-decoded back to an object (mirroring the
existing `attachment_analysis_records.response` decode). `apply_extractions` builds the provider from
`raw["page_classifications"]` for each period in scope.

## Removed

`FileExtractionProvider`, `classify_path_for`, and `CLASSIFY_SUFFIX` are deleted from
`extractions.py` (FR-006). No code reads or writes `*.classify.json`.
