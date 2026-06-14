# Quickstart: Data-correction audit trail + reversibility

**Feature**: 054-correction-audit-trail

## What this gives you

A safety net for autonomous fiscal-data corrections: every correction is logged with from→to +
evidence to a durable, queryable `data_corrections` table, gated by a verify-after check, and
reversible by a human.

## Migrate (one-time, local)

```bash
pnpm db:generate         # generates drizzle/0014_*.sql for the new data_corrections table
pnpm db:migrate:dev      # applies it to local D1
```

## Apply a correction (the triage agent's primitive)

```bash
# Correct attachment X's page p1 valor_total 800 -> 320, targeting its amount-mismatch finding.
cd scripts && uv run python -m analysis apply-correction \
    --attachment-id <ATT_ID> \
    --target-finding '2099-01|amount|<ATT_ID>|<ENTRY_ID>' \
    --pages '{"p1": {"papel_artefato":"nfse","tipo_documento":"NFS-e","valor_total":320,"valor_liquido":320,"valor_pago":320,"cnpj_emitente":"...","nome_emitente":"...","data_emissao":"2099-01-10","numero_documento":"123","descricao_servico":"..."}}' \
    --evidence /abs/path/to/2099-01/<ENTRY_ID>_p1.png \
    --agent triage-agent
```

- PASS → prints `{"result":"applied", ...}`; the finding is gone and a `data_corrections` row exists.
- Target finding doesn't clear OR a new finding appears → prints `{"result":"rolled-back", ...}` and
  the data is restored to its pre-correction state (nothing silently changed).
- Target finding not present to begin with → `{"result":"unverifiable", ...}`, no data change.
- Corrected values already match → `{"result":"no-op", ...}`, no row written.

## Review what the agent changed

```bash
cd scripts && uv run python -m analysis list-corrections --periodo 2099-01
cd scripts && uv run python -m analysis list-corrections --attachment-id <ATT_ID> --status applied
```

## Undo a correction (human)

```bash
cd scripts && uv run python -m analysis undo-correction --id <CORRECTION_OR_BATCH_ID> --actor gustavo
```

Restores the recorded `from` state, re-derives findings (the original finding reappears), and stamps
the record `reverted`. Only `applied` corrections can be undone.

## Verify locally (the feature's own acceptance)

```bash
# Unit (pure seams): SQL builders, field diff, verify-after rule, status guards, no-op/fail-closed.
pnpm test:py                 # includes scripts/tests/test_corrections.py

# Integration (real local Miniflare D1): apply(pass)→list→undo, apply(fail)→rollback,
#   cache-wipe survives, undo guards.
pnpm e2e:seed                # seed synthetic period 2099-01 (if not already)
pnpm test:py:integration     # includes scripts/integration_tests/test_corrections_d1.py
```

## Notes

- `--remote` writes production; it is never implicit. Omit it to stay on local Miniflare D1.
- The store is analysis-owned and durable — it survives clearing the `.cache/analysis/` scratch.
- This feature does NOT build the triage agent (TRIAGE-004) or its orchestrator (TRIAGE-005); it
  provides the store + record/verify/undo/list primitives they will call.
