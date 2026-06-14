# Quickstart: verify typed-record persistence + flat coexistence

All commands run from the repo root. Local D1/R2 (Miniflare) only.

## 1. Python unit + integration tests

```bash
# Pure dual-path validation + roll-up over typed/flat records
cd scripts && uv run python -m unittest discover -s tests -t .

# EXTRACT-001 validator still green (reached by the gate)
uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools   # from repo root

# Real local D1: record typed -> apply -> records carry typed JSON; flat still rolls up; invalid rejected
cd scripts && uv run python -m unittest discover -s integration_tests -t .
```

## 2. Manual CLI smoke (local D1)

```bash
# A valid typed NFS-e payload is accepted and stored verbatim.
python -m analysis record-classification --attachment-id <att> --page p1 --json '{
  "doc_type":"nfse","schema_version":"1","raw_text":"...","numero":"0000123",
  "data_emissao":"05/12/2025","prestador":{"nome":"X LTDA","cnpj":"11.222.333/0001-44"},
  "tomador":{"nome":"SVHC","cnpj_cpf":"98.765.432/0001-00"},
  "discriminacao_servico":"servico","valores":{"valor_servico":320.0,"deducoes":0.0,"valor_liquido":320.0}
}'
# -> "Recorded classification for <att> p1."

# A schema-invalid typed payload (missing required block) is rejected, nothing written.
python -m analysis record-classification --attachment-id <att> --page p1 --json '{"doc_type":"nfse"}'
# -> exit 1, "error: classification rejected: ..."

# A legacy flat payload still works.
python -m analysis record-classification --attachment-id <att> --page p1 --json '{
  "papel_artefato":"nfse","tipo_documento":"nfse","valor_total":320,"valor_liquido":320,
  "valor_pago":null,"cnpj_emitente":"11.222.333/0001-44","nome_emitente":"X LTDA",
  "data_emissao":"05/12/2025","numero_documento":"0000123","descricao_servico":"servico"
}'
# -> "Recorded classification for <att> p1."
```

## 3. End-to-end roll-up check

```bash
python -m analysis apply-extractions --periodo <YYYY-MM>
python -m analysis mismatches --periodo <YYYY-MM>
# Confirm: a typed NFS-e reconciles on its valor_liquido (320), not a gross; legacy flat unchanged.

# Inspect the stored record shape (typed JSON survives into the records table):
wrangler d1 execute DATABASE --local --command \
  "SELECT response FROM attachment_analysis_records WHERE attachment_analysis_id LIKE '%' LIMIT 3"
```

## 4. UI verification (running app)

```bash
pnpm preview   # build + local Cloudflare preview (auth-gated)
```

- Sign in (see the `ui-login` skill). Open `/dashboard/entries`, expand an entry whose attachment was
  classified with a **typed** record → the analysis detail dialog shows the reconciliation fields AND
  the rich typed transcription (no crash, no empty panel).
- Open an entry whose attachment is a **legacy flat** record → the dialog renders the flat fields
  exactly as before.

## Success signals

- typed payload stored verbatim with `doc_type` + `schema_version`; roll-up total = mapper-derived.
- legacy flat rows: reconciliation + UI unchanged.
- schema-invalid typed payload rejected at the gate (exit 1, no write).
- detail dialog renders both shapes without error.
