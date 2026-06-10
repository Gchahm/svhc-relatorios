# Quickstart: verify per-page extractions land in D1 (no `.classify.json`)

Manual end-to-end verification (no automated test framework is configured). Run from the repo root
unless noted. Use `--remote` only to verify production; default is local Miniflare.

## 0. Apply the migration locally

```bash
pnpm db:generate        # generates drizzle/0010_*.sql (new table + dropped columns) if not done
pnpm db:migrate:dev     # apply to local D1
```

Confirm in Drizzle Studio (`pnpm db:studio:dev`) that `page_classifications` exists and that
`attachment_analyses.raw_response` / `attachment_analysis_records.raw_text` are gone.

## 1. Plan + classify a period

```bash
cd scripts
uv run python -m analysis docs-plan --periodo 2025-12        # prints plan JSON; each page has `recorded:false`
```

Then run the classify flow (via the skill / analyze-docs agent in Claude Code, or by calling
`record-classification` per page manually). Each `classify-doc-page` invocation now records to D1:

```bash
# (manual single-page example)
uv run python -m analysis record-classification --attachment-id "$AID" --page p1 <<'JSON'
{ "papel_artefato":"invoice","tipo_documento":"DANFE","valor_total":617.25,"valor_liquido":null,
  "valor_pago":null,"cnpj_emitente":null,"nome_emitente":"ACME LTDA","data_emissao":"05/12/2025",
  "numero_documento":"123","descricao_servico":null }
JSON
```

Re-running `docs-plan` should now show `recorded:true` for recorded pages (FR-008).

## 2. Core test — cleared cache (User Story 1 / SC-001)

Remove the ephemeral scratch but keep nothing else needed (the merge must rely on D1 only):

```bash
rm -rf ../.cache/analysis/2025-12      # drop materialized images + any leftover scratch
uv run python -m analysis apply-extractions --periodo 2025-12
```

The merge re-materializes images from R2 (for grouping/hash) and reads per-page extractions **from
D1**. It must produce `attachment_analyses` + records equivalent to a run where scratch was kept.
Confirm no `.classify.json` was needed and none exists:

```bash
find ../.cache/analysis -name '*.classify.json'   # → no output (SC-003)
```

## 3. Equivalence + analysis (User Story 2 / SC-002)

```bash
uv run python -m analysis analyze --periodo 2025-12
uv run python -m analysis mismatches --periodo 2025-12
```

Compare analyses, matches, and alerts against a pre-change baseline for the same period: equivalent
aside from the removed dead columns.

## 4. Idempotency (SC-004)

Re-record one page with a corrected value, then query the staging table:

```bash
uv run python -m analysis record-classification --attachment-id "$AID" --page p1 --json '{"error":"re-read: illegible"}'
npx wrangler d1 execute DATABASE --local --command \
  "SELECT count(*) c FROM page_classifications WHERE attachment_id='$AID' AND page_label='p1';"
# → c = 1 (latest wins; no duplicate)
```

## 5. Contract rejection (SC-006)

```bash
uv run python -m analysis record-classification --attachment-id "$AID" --page p9 --json '{"papel_artefato":"bogus"}'
# → non-zero exit, stderr explains the contract violation; nothing written
```

## 6. App build + codebase checks (SC-003, SC-005)

```bash
cd .. && pnpm lint && pnpm format && npx tsc --noEmit
grep -rn "classify.json\|FileExtractionProvider\|raw_response\|rawText" src scripts/analysis | grep -v node_modules
# → no functional references remain (only the migration drop + this spec's prose)
```
