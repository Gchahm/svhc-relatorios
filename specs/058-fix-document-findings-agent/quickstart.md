# Quickstart: fix-document-findings agent + reclassify CLI

## The composite `reclassify` CLI (§4.5)

Reclassify one attachment's pages and propagate (re-derive analysis + documents + alerts), LOCAL:

```bash
cd scripts
echo '{"p1": {"papel_artefato": "nota_fiscal", "valor_total": 320, "numero_documento": "12345", "cnpj_emitente": "12345678000199"}}' \
  | python -m analysis reclassify --attachment-id <attachment-id> --pages -
# → {"result": "reclassified", "attachment_id": "<id>", "period": "2025-12", "pages": ["p1"], "remote": false}
```

Production (explicit): add `--remote`.

## The `fix-document-findings` agent

Invoked as a context-isolated worker (e.g. by the TRIAGE-005 batch orchestrator, or directly):

> Triage document `<document-id>` for false positives (local).

The agent:
1. `python -m analysis document-evidence --id <document-id>` → findings + page `read_path`s.
2. Opens each page image, judges true / false-misread / systematic-fault / page-error.
3. For a `false-misread`, calls `apply-correction --attachment-id <id> --target-finding <mismatch_key>
   --pages <json> --evidence <read_path>` (audited + verify-after).
4. Returns terse JSON `{document_id, attachment_ids, corrections, left_as_finding, escalated}`.

## Verifying against seeded local data

The e2e seed (`pnpm e2e:seed`) creates synthetic period `2099-01`. To exercise the correction loop:

```bash
# 1. See a document's findings
cd scripts && python -m analysis document-evidence --id <doc-id>

# 2. Reclassify an attachment (composite helper) and confirm re-derivation
echo '{"p1": {...}}' | python -m analysis reclassify --attachment-id <id> --pages -

# 3. Audited correction + verify-after (the agent's path)
echo '{"p1": {...}}' | python -m analysis apply-correction --attachment-id <id> \
    --target-finding '<period>|amount|<id>|<entry>' --pages - --evidence <read_path>

# 4. Inspect the audit trail
python -m analysis list-corrections --attachment-id <id>
```

## Tests

```bash
pnpm test:py                 # unit (incl. scripts/tests/test_reclassify.py)
pnpm test:py:integration     # real-D1 (incl. scripts/integration_tests/test_reclassify_d1.py)
pnpm lint && pnpm format     # quality gates
```
