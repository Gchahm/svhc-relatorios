# CLI Contract: `python -m analysis reclassify`

Composite "reclassify one attachment" helper (design §4.5). Records corrected per-page staging then
propagates in the pinned order. The **un-gated** sibling of `apply-correction` (no audit/verify net —
that is `apply-correction`'s job); ergonomics only (staging-driven `apply` already makes a mid-sequence
crash non-destructive).

## Synopsis

```
python -m analysis reclassify --attachment-id <id> [--pages <json> | -] [--cache-dir <dir>] [--remote]
```

## Arguments

| Flag | Required | Default | Meaning |
|------|----------|---------|---------|
| `--attachment-id` | yes | — | Attachment (plan representative id) to reclassify. |
| `--pages` | no (stdin if omitted) | stdin | Corrected per-page extraction(s) as JSON: `{"<page_label>": <fields-object>}`. `-` or omitted ⇒ read stdin. |
| `--cache-dir` | no | `../.cache/analysis` | Ephemeral local scratch dir (matches the other analysis commands). |
| `--remote` | no | off (LOCAL) | Write/read REMOTE (production) D1 instead of local. **Never implicit.** |

## Behavior

1. Read `--pages` (string or stdin); parse JSON. Non-JSON or non-object ⇒ `error:` to stderr, exit 1.
2. Resolve the attachment's `period` (read-only, via the existing `_attachment_context`). Unknown
   attachment ⇒ `error: unknown attachment <id>` to stderr, exit 1.
3. Validate EACH page payload with `validate_page_fields` (the `record-classification` contract gate,
   typed/flat per feature 055). Any failure ⇒ `error: page <label> rejected: <reason>` to stderr, exit 1,
   **write nothing** (validate all before recording any).
4. Empty `--pages` object ⇒ `no-op` result (nothing recorded, nothing propagated), exit 0.
5. Record each page via `record_classification(attachment_id, page_label, fields, target)`.
6. Propagate (the existing `_propagate` ordering, scoped to the attachment's period):
   `clear_classified_stamp` → staging-driven `apply_extractions` → `run_analysis` (which runs
   `build_documents` then writes alerts). The propagation's human-readable banners are routed to **stderr**
   so stdout stays parseable JSON.
7. Print the terse JSON result to stdout; exit 0.

## Result (stdout)

```jsonc
{ "result": "reclassified", "attachment_id": "<id>", "period": "2025-12", "pages": ["p1"], "remote": false }
```

`result` ∈ `reclassified` (staging recorded + propagated) | `no-op` (empty pages). Errors go to stderr +
non-zero exit (never a JSON `error` result on stdout, matching the validate-then-exit idiom).

## Invariants

- LOCAL by default; REMOTE only with `--remote` (FR-015).
- Reads the mirror tables only to resolve period/scope; never writes them.
- Non-destructive by construction: staging-driven `apply` only rolls up groups whose representative has
  staging rows, so an un-recorded attachment is never touched (FR-017).
- Reuses the established stdout-JSON / stderr-banner idiom of `apply-correction` (FR-016).
