# Quickstart: Staging-driven apply-extractions

## What changed

`apply-extractions` now processes **only** the shared-NF groups whose representative attachment has
recorded `page_classifications` staging rows. A pending attachment with no staging is skipped (left
intact), so re-running apply can no longer overwrite a good analysis with an empty one.

## Targeted single-attachment reclassify (new simple flow)

```bash
# 1. Re-record the corrected page(s) for the one attachment you want to fix:
python -m analysis record-classification --attachment-id <ATT_ID> --page p1   # (the vision skill does this)

# 2. Apply — only that attachment's group is rolled up; everything else is untouched:
python -m analysis apply-extractions --periodo <YYYY-MM>
```

No more manual "isolate the pending set" step (the prior fragile workaround). Recording staging *is* the
selection.

## Run the tests

```bash
# Fast pure unit suite (includes the new staging-presence selection test):
pnpm test:py

# Real-D1 integration suite (includes the bystander + targeted-reclassify cases; needs wrangler + local migrations):
pnpm test:py:integration
```

## Verify the safety guard manually (local Miniflare)

```bash
# Seed the synthetic period (E3 = classified with an analysis; mark it pending WITHOUT recording staging):
pnpm e2e:seed
python -m analysis mark-pending --attachment-id <E3_ATT_ID>   # clears classified_at AND its staging (none for E3)

# Re-run apply: E3 has no staging, so its existing analysis is preserved and it stays pending.
python -m analysis apply-extractions --periodo 2099-01

# Assert E3's analysis row + records are unchanged and E3 is still pending.
```
