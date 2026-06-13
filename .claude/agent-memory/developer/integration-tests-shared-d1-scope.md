---
name: integration-tests-shared-d1-scope
description: Real-D1 integration tests run against shared local Miniflare D1 with non-synthetic data — scope every count/assert to the synthetic period's ids, never the whole table
metadata:
  type: feedback
---

In `scripts/integration_tests/` (feature-046 harness, `pnpm test:py:integration`), tests run against the **shared local Miniflare D1**, which holds real scraped data alongside the synthetic `2099-01` seed. So a whole-table assertion like `h.count("page_classifications", "1=1") == 0` will FAIL even after clearing the synthetic period's staging (a real run had ~362 unrelated rows).

**Why:** the harness `restore()` only resets the synthetic period's analysis-owned rows; it does not wipe other periods. `apply_extractions("local", ["2099-01"])` is period-scoped, so it only ever selects from `2099-01`'s loaded rows — other periods are irrelevant to behaviour but DO inflate global counts.

**How to apply:** always scope integration-test `count`/`scalar` assertions to the synthetic attachment/entry ids (e.g. `f"attachment_id = '{self.e4_att}'"`), resolved via `h.ids()` / `e2e.synthetic.ids()`. The seeded fixtures: E1+E2 share an NF (classified, over-claim alert), E3 classified with analysis NF-1002, E4 pending WITH a staging row, E5 reconcile target, E6 revenue/no-attachment.
