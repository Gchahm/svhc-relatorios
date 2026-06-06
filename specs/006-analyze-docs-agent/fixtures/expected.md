# Synthetic verification — expected outcomes

`build_and_verify.py` builds a self-contained synthetic period (no real images, no VLM), runs
`plan_extractions` then `apply_extractions` with hand-authored extractions, and asserts the
deterministic pipeline behaves exactly as the old flow would for the same extracted values. It then
runs `check_duplicate_billing` on the result.

## Cases and expectations

| Doc   | Kind                                         |     Entry amount |    Extraction (gross) | Expected `amount_match` | Notes                                                               |
| ----- | -------------------------------------------- | ---------------: | --------------------: | ----------------------- | ------------------------------------------------------------------- |
| A     | single invoice                               |              500 |     `valor_total` 500 | **True**                | per-entry compare within 5%; `vendor_match` True; `date_match` True |
| B1+B2 | shared NF (reconciled split)                 | 600 + 400 = 1000 | NF `valor_total` 1000 | **True** for both       | byte-identical pages → extracted once, fanned out; group reconciles |
| C1+C2 | shared NF (over-claim)                       | 900 + 800 = 1700 | NF `valor_total` 1000 | **False** for both      | sibling sum > NF total → `over_claim`                               |
| D     | heterogeneous (invoice+boleto+payment_proof) |              900 | paid 900 (precedence) | **True**                | roll-up amount precedence picks payment_proof `valor_pago` 900      |
| E     | unreadable                                   |              300 |    `{ "error": ... }` | n/a                     | document-level error `no page produced a parseable response`        |

## Cross-cutting assertions

- B's pages are extracted **once** (only the representative appears in the manifest's pages); B2 is a
  member that is fanned out — verifies SC-005 (no redundant vision passes).
- `check_duplicate_billing` emits exactly **one** `critical` `duplicate_billing` alert, for group C
  (FR-008). Group B (reconciled) emits none.
- Every written `document_analyses` row carries nested `analysis_records` whose `response` matches the
  supplied extraction (shape compatible with `import-to-d1.mjs`, SC-003 — shape level).

Run: `cd scripts && uv run python ../specs/006-analyze-docs-agent/fixtures/build_and_verify.py`
