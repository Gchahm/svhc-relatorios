---
name: summarize-mismatches-empty-scope
description: summarize_mismatches treats a falsy attachment_ids/entry_ids as "no scope" (returns ALL findings) — never pass it [] when you mean "nothing"
metadata:
  type: feedback
---

`summarize_mismatches` (`scripts/analysis/extractions.py`) computes its scope as
`doc_filter = set(attachment_ids) if attachment_ids else None`. An **empty list** `[]` is falsy, so
it collapses to `None` → returns EVERY period's findings (no scope), not zero findings.

**Why:** any caller that resolves a scope set dynamically (e.g. the `document-evidence` resolver in
`scripts/analysis/documents.py`, which maps a document id to its source attachment ids) can legitimately
end up with an empty set ("this document has no source attachments / nothing to triage"). Passing that
`[]` straight through silently returns the whole corpus — a serious over-scope bug.

**How to apply:** when delegating to `summarize_mismatches` with a computed id set, short-circuit and
return `[]` yourself when the set is empty; only call the summary when the set is non-empty. See
`document_evidence()` for the guard. The same falsy-collapse applies to `entry_ids`.
