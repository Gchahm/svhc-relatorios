# Phase 1 Data Model: test fixtures + module contracts under test

This feature adds no production data model. The "entities" here are the **in-memory fixture shapes**
the tests construct and the **pure contracts** each tested function exposes.

## Fixture shapes (built by hand in tests, no D1)

### PeriodData (`analysis/models.py`)
Constructed directly: `PeriodData(period, raw, report, entries, category_subtotals, attachments)`.
- `report`: dict with `total_revenue`, `total_expenses`, `month_balance`, `opening_balance`,
  `accumulated_balance` (consistency checks); only `total_expenses`/`total_revenue` for advanced/
  trends.
- `raw`: dict; tests set `raw["attachment_analyses"]`, `raw["alerts"]`, `raw["page_classifications"]`.
- `entries`: list of `{id, movement_type ("C"|"D"), amount, vendor_id?, unit_id?, subcategory_id?}`.
- `category_subtotals`: list of `{subcategory_id, movement_type, amount}`.
- `attachments`: list of `{id, entry_id, file_path?, content_hash?, classified_at?,
  external_document_id?}`.

### RefIndex (`analysis/models.py`)
Built via `RefIndex()` + `merge_period({vendors,subcategories,categories,units}, period)`, or fields
set directly. Provides `vendor_name`, `subcategory_name`, `category_name`.

### attachment_analyses row (input to `detect_attachment_mismatches`)
`{attachment_id, amount_match (0|1|None), vendor_match, date_match, error?, extracted_amount,
issuer_name, extracted_date}`.

### PageAnalysisRecord-style extraction (input to `build_attachment_analysis` via provider)
The injected `provider(attachment_id, page_label)` returns `(parsed_dict | None, error | None)`
where `parsed_dict` has VLM keys: `tipo_documento`, `papel_artefato`, `valor_total`, `valor_pago`,
`valor_liquido`, `cnpj_emitente`, `nome_emitente`, `data_emissao`, `numero_documento`,
`descricao_servico`.

### Verdicts file (`analysis/verdicts.py`)
JSON `{period, verdicts: [{mismatch_key, verdict, iteration, root_cause?, fix?}], loop_state}`,
written/read under a `tempfile` cache dir.

## Contracts under test (pure functions / seams)

| Module | Functions covered | Seam / how D1 is avoided |
|--------|-------------------|--------------------------|
| `mismatches.py` | `detect_attachment_mismatches` | takes `PeriodData`+`RefIndex`; reads `raw` only |
| `checks/attachments.py` | `check_attachment_mismatches`, `check_attachment_not_downloaded` | pure over `PeriodData` |
| `checks/advanced.py` | `check_vendor_concentration`, `check_category_growth`, `check_seasonality`, `check_delinquency`, `run_advanced` | pure over `PeriodData`/`all_periods`/`RefIndex` |
| `checks/trends.py` | `check_subcategory_above_average`, `check_month_over_month`, `check_missing_recurring_subcategory`, `run_trends` | pure |
| `checks/consistency.py` | `check_balance_month`, `check_balance_accumulated`, the entry-sum checks, `run_consistency` | pure |
| `nf_groups.py` | `within_tolerance`, `reconcile_group`, `group_attachments` | pure (hash from `content_hash` field) |
| `attachments.py` | `build_attachment_analysis`, `_fanout_result`, `_apply_group_amount_match`, `nf_total_for_reconciliation`, `_rollup_attachment_fields`, `_map_artifact_role`, `_pick_*`, `_parse_brl_value`, `_page_label_from_path`, `_check_date_in_period`, `select_work`, `summarize_results` | `provider` injection; `select_work` over in-memory periods |
| `vendor_match.py` | `normalize_tokens`, `normalize_company_name`, `is_payer_name`, `names_match`, `reconcile_vendor` | pure |
| `verdicts.py` | `mismatch_key`, `validate_verdict`, `validate_fix`, `upsert_verdict`, `_latest_verdicts`, `_verdict_history_by_key`, `_upsert_history`, `record_verdict`, `load/save_verdicts_file`, `_attachment_ids_of`, `loop_state` | tmp cache dir; `loop_state` stubs `summarize_mismatches` via `unittest.mock.patch` (stdlib) |
| `documents.py` | `normalize_number`, `normalize_cnpj`, `document_key`, `_sql_id_list`, `_prune_sql`, `_analysis_total` | pure string/SQL builders |
| `extractions.py` | `build_plan`, `_page_refs_for_doc`, `mark_pending` (no-id no-op path) | in-memory periods/refs |
| `images.py` | `attachments_needing_hash_backfill`, `_split_tokens` | pure read of in-memory periods |
| `loader.py` | `_sql_str`, `_in_clause` | pure |

## Validation rules exercised

- Tolerance band: `within_tolerance`/`reconcile_group` at exact boundaries (R$0.05 abs, 5% rel),
  `nf_total <= 0` → `None`, sum>total → over_claim, sum<total → under_claim.
- Mismatch emission: one per failing flag; page-error short-circuits; `amount_match==0` (int) only.
- Verdict validation: `false` requires valid `root_cause.area` + non-empty hypothesis; `root_cause`
  forbidden otherwise; invalid `verdict`/`confidence` rejected; fix status never `merged`.
- `loop_state` termination precedence: converged > no-progress (flip or stagnant window) >
  max-iterations.
- `_map_artifact_role`: payment-proof override when `valor_pago` present or tipo comprovante/recibo.
- Amount precedence in roll-up: payment paid → boleto → multi-invoice sum → invoice net → gross.
