# Quickstart: All-CLI typed document transcription

## The new all-CLI pipeline (per period)

```bash
cd scripts

# 1. scrape a period (mirror + page images) — unchanged
python -m scraper scrape --periodo 2025-12 --download-docs

# 2. classify (NEW) — headless typed transcription of pending pages
python -m analysis classify --periodo 2025-12            # cli backend (default)
#   python -m analysis classify --periodo 2025-12 --backend api --model <m>   # optional

# 3. apply — roll up the recorded staging into attachment_analyses — unchanged
python -m analysis apply-extractions --periodo 2025-12

# 4. analyze — checks + alerts — unchanged
python -m analysis analyze --periodo 2025-12

# (optional) review
python -m analysis mismatches --periodo 2025-12
```

`classify` replaces the former `classify-period` / `classify-doc-page` skill fan-out and the
`analyze-docs` agent. Each step still runs standalone per period.

## Re-classify a subset

```bash
python -m analysis mark-pending --attachment-id <id> [<id> …]   # clears classified_at + staging
python -m analysis classify --periodo 2025-12                   # re-reads the now-pending pages
python -m analysis apply-extractions --periodo 2025-12
```

## Verify the typed-only gate

```bash
cd scripts
# Rejected (legacy flat — no doc_type):
echo '{"papel_artefato":"invoice","tipo_documento":"danfe","valor_total":100,"valor_liquido":null,"valor_pago":null,"cnpj_emitente":null,"nome_emitente":null,"data_emissao":null,"numero_documento":null,"descricao_servico":null}' \
  | python -m analysis record-classification --attachment-id X --page p1 --json -   # exits non-zero

# Accepted (error alternative):
echo '{"error":"page illegible"}' | python -m analysis record-classification --attachment-id X --page p1 --json -
```

## Run the tests

```bash
pnpm test:py                      # full stdlib unit suite (incl. new test_classify.py)
node --test src/app/dashboard/entries/typed-transcription.test.mjs   # UI renderer
```

## Acceptance walk-through (maps to spec SC-001..SC-006)

- SC-001: `classify` records a typed row per pending non-recorded page (fake transcriber in tests;
  real `doc_transcribe` in prod).
- SC-002: a page whose transcription carries `parse_errors` yields one error row; the rest proceed.
- SC-003: `--backend cli` with no `claude` on PATH → `doc_transcribe` exit 2 → `classify` stops with
  the message, no fallback.
- SC-004: flat payload rejected at the gate; typed accepted; `apply-correction`/`reclassify` pass.
- SC-005: `grep -rn 'classify-doc-page\|classify-period\|analyze-docs'` finds no live-path reference.
- SC-006: `pnpm test:py` green; analysis library imports without `tools/` on `sys.path` beyond
  `typed_gate`.
```
