# Quickstart: Deterministic per-type mappers

## What changed

`scripts/analysis/type_mappers.py` (new) turns a typed transcription JSON into the flat
reconciliation fields the analysis roll-up consumes, replacing the model's guesswork and the
"first-record-of-role-wins" selection. `_rollup_attachment_fields` and `nf_total_for_reconciliation`
in `scripts/analysis/attachments.py` now read each page record through the mapper.

## Verify (no DB, no vision — pure)

```bash
# Full Python unit suite (includes the new mapper tests + roll-up regression tests)
pnpm test:py

# Just the mapper tests
cd scripts && uv run python -m unittest tests.test_type_mappers -v

# The tools suite (schemas) still passes — no dependency added
uv run python -m unittest discover -s ../tools/doc_transcribe/tests -t ../tools
```

## Spot-check the 757dedb0 fix

```bash
cd scripts && uv run python -c "
from analysis.type_mappers import to_reconciliation_fields
nfse = {'doc_type':'nfse','numero':'0000123','data_emissao':'05/12/2025',
        'prestador':{'nome':'MANUT SV LTDA','cnpj':'11.222.333/0001-44'},
        'valores':{'valor_servico':320.0,'valor_liquido':320.0}}
print(to_reconciliation_fields(nfse))
# -> valor_total == 320.0 (NOT 800), cnpj_emitente == prestador cnpj
"
```

## Legacy flat pass-through

A pre-typed record (no `doc_type`) is returned unchanged over the reconciliation keys — a re-run over
an un-reclassified period produces the same roll-up as before.

## End-to-end (optional, against local data)

```bash
# Re-run analysis over a local period that has attachment_analyses; the documented
# amount_match false positives no longer appear in the mismatch summary.
cd scripts && uv run python -m analysis mismatches --periodo <YYYY-MM>
```
