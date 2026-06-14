# Quickstart: Re-derive command

## What it does

After you fix a deterministic mapper (`scripts/analysis/type_mappers.py`), propagate the corrected
interpretation to every already-classified document **without re-reading any page image**:

```bash
# Global — re-derive every classified attachment across all periods (local D1):
python -m analysis re-derive

# Scoped to one period:
python -m analysis re-derive --periodo 2025-12

# Scoped to specific attachments (each re-derives with its full shared-NF group):
python -m analysis re-derive --attachment-id <id1> <id2>

# Against production:
python -m analysis re-derive --periodo 2025-12 --remote
```

It reads the stored transcriptions from `attachment_analysis_records.response`, re-runs the mappers,
rebuilds `attachment_analyses`, then rebuilds `documents` and refreshes `alerts` for the affected
period(s). Zero vision calls, zero image reads.

## Verify locally

1. Seed synthetic data (classified attachments with stored transcriptions):

   ```bash
   pnpm e2e:seed     # populates the 2099-01 synthetic period (local Miniflare D1)
   ```

2. Run re-derive on the synthetic period:

   ```bash
   python -m analysis re-derive --periodo 2099-01
   ```

   Expect a JSON summary like `{"re_derived": N, "skipped_no_transcription": M, "periods": ["2099-01"], "remote": false}`.

3. Run it again — the `attachment_analyses` rows (ignoring `analyzed_at`) are identical (idempotent).

## Run the tests

```bash
pnpm test:py                 # fast unit suite (includes test_re_derive.py pure seams)
pnpm test:py:integration     # real-D1 suite (includes test_re_derive_d1.py)
pnpm lint && pnpm format     # quality gates (Prettier covers specs/markdown too)
```

## Where it lives

- Command + dispatch: `scripts/analysis/__main__.py`
- Orchestration: `re_derive(...)` in `scripts/analysis/extractions.py`
- Staging reconstruction (shared with `corrections`): `scripts/analysis/page_classifications.py`
- Reused propagation: feature-050 staging-driven `apply_extractions` + `run_analysis`
