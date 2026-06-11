# Quickstart / Manual Verification: Preserve alert resolution across re-runs

No test framework is configured (constitution III). Verify by exercising the pipeline + D1
directly. Run from repo root; the analysis CLI runs via `uv` under `scripts/`.

## Setup

Use the local D1 (default target). Pick a period that already has alerts, e.g. `2025-12`.

```bash
# List current alerts for the period (note an id you'll resolve)
cd scripts && uv run python -m analysis ... # (whatever the analyze entrypoint is)
```

Or inspect D1 directly via wrangler (the pipeline's own access path):

```bash
npx wrangler d1 execute fiscal-db --local \
  --command "SELECT id, type, resolved, notes FROM alerts WHERE reference_period='2025-12' LIMIT 5"
```

## Test 1 — Per-period alert: resolution survives re-run (FR-001, SC-001)

1. Mark one alert resolved with a note (simulate the PATCH the UI sends):

   ```bash
   npx wrangler d1 execute fiscal-db --local \
     --command "UPDATE alerts SET resolved=1, resolved_at=1700000000000, notes='handled — see invoice' WHERE id='<ALERT_ID>'"
   ```

2. Re-run the analysis for that period:

   ```bash
   cd scripts && uv run python -m analysis analyze --periodo 2025-12
   ```

3. Confirm the alert is **still resolved with its note**:

   ```bash
   npx wrangler d1 execute fiscal-db --local \
     --command "SELECT id, resolved, resolved_at, notes FROM alerts WHERE id='<ALERT_ID>'"
   ```

   Expected: `resolved=1`, `resolved_at=1700000000000`, `notes='handled — see invoice'`.
   (Before the fix: `resolved=0`, `notes=NULL`.)

## Test 2 — Global document_overpayment: resolution survives (FR-002)

Repeat Test 1 against a `document_overpayment` alert (global writeback path). **Re-run a FULL
`analyze` (no `--periodo`), or `--periodo` = that alert's own `reference_period`**, then confirm
preservation.

> ⚠️ Do NOT re-run with `--periodo` set to some *other* period: an overpayment alert carries a
> real `reference_period` (max of its linked periods), and the per-period delete is keyed on
> `reference_period`. Picking an unrelated period means the row is never deleted, so it survives
> regardless of the fix — a false positive that hides the global-path bug (issue #34 review).

## Test 3 — Obsolete finding still clears (FR-003, SC-003)

1. Resolve an alert as in Test 1.
2. Change the underlying data so the finding no longer fires (or pick an alert you know won't
   re-emit), and re-run `analyze`.
3. Confirm the alert id is **absent** from `alerts` (not lingering as a resolved orphan).

## Test 4 — Idempotency (FR-007, SC-004)

Run `analyze` for the period twice in a row with no user action between runs. Confirm
`resolved` / `resolved_at` / `notes` are identical after both runs for every alert.

## UI round-trip (optional, end-to-end)

Use the `ui-login` skill to open the dashboard, resolve an alert + add a note via the alert
detail page, then run `analyze` and reload the alert detail page — the resolution and note must
still be shown.

## Gates before commit

```bash
pnpm lint
pnpm format
```
