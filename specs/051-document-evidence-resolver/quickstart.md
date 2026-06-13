# Quickstart: `document-evidence` resolver

## Run

From `scripts/`:

```bash
# Local D1 (default)
uv run python -m analysis document-evidence --id <document_id>

# Production D1
uv run python -m analysis document-evidence --id <document_id> --remote
```

Prints a JSON object: `{document_id, attachment_ids, findings}` where each finding carries
`page_refs[].read_path` (a local image file the triage agent can open with the Read tool).

## Typical triage-agent flow

1. Agent is handed a document id (from a `document_overpayment` alert or the documents dashboard).
2. `document-evidence --id <id>` → findings + page read paths, no SQL.
3. Agent opens the `read_path` images, judges each finding (real vs. misread).
4. (Downstream / other issues) correct via re-classification of the resolved `attachment_ids`.

## Verify

```bash
# Unknown id → non-zero exit, clear message
uv run python -m analysis document-evidence --id does-not-exist ; echo "exit=$?"

# A seeded over-claim document (e.g. the e2e synthetic period) → findings with page_refs
uv run python -m analysis document-evidence --id <seeded-doc-id> | python -m json.tool
```

## Test

From `scripts/`:

```bash
python -m unittest discover -s tests -t .        # or: pnpm test:py
```

The unit test (`scripts/tests/test_document_evidence.py`) drives the pure resolver seam with an
injected `query` callable and a stubbed `summarize_mismatches` — no D1/R2/network.
