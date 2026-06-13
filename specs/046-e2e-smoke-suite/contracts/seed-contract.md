# Contract: Synthetic Seed (`scripts/e2e/seed.py`)

## CLI

```
uv run python -m e2e.seed [--remote]    # default local; --remote refused (synthetic-only, local guard)
```

`--remote` MUST be rejected with a non-zero exit and a clear message (the seed never writes production).

## Behavior (the observable contract)

1. **Apply migrations**: runs `wrangler d1 migrations apply DATABASE --local` (idempotent) before inserting.
2. **Write D1**: upserts the synthetic dataset (data-model.md) via `d1.upsert_tables({...}, target="local")` in one batched, FK-ordered call.
3. **Build documents**: invokes `build_documents("local")` so `documents` + `document_entries` exist for the UI.
4. **Write alerts**: upserts the seeded alerts (incl. deep-link metadata).
5. **Upload R2**: for each seeded attachment, `d1.put_object(key, fake_png, "image/png", target="local")` at the `objectKeyFromFilePath`-equivalent key (`2099-01/<entry_id>_p1.png`).

## Post-conditions (assertable via `d1.query`)

- `SELECT count(*) FROM accountability_reports WHERE period='2099-01'` = 1.
- `SELECT count(*) FROM entries WHERE report_id = det_id("report","2099-01")` = 6.
- `SELECT count(*) FROM attachments` for the period's entries = 5.
- `attachment_state`: 4 rows with non-NULL `classified_at` (E1,E2,E3,E5); E4 absent or NULL (pending).
- `attachment_analyses` = 3; `attachment_analysis_records` = 3.
- `documents` ≥ 2 (NF-1001 over, NF-1002 within); `document_entries` ≥ 3.
- `alerts` for `2099-01` includes one `attachment_amount_mismatch` and one `document_overpayment` with `metadata.entry_ids`.
- R2: each `2099-01/<entry_id>_p1.png` key exists (verified via `d1.get_object` round-trip into a temp file).

## Idempotency

Running the seed twice leaves the row **count and ids identical** (deterministic `det_id`; `INSERT OR REPLACE`). The integration test asserts the count is stable across two seed runs.

## Synthetic guarantee

No `data/scrape` read; all names contain `EXEMPLO`/`example.svhc.local`; CNPJs are fixed fakes. The module imports only `scripts/common` + stdlib + `synthetic.py`.
