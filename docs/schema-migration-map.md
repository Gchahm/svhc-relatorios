# Schema Migration Map: fiscal-old (PostgreSQL/SQLAlchemy) → fiscal (D1/Drizzle)

This document maps every table and column from the old Python/SQLAlchemy schema
(`fiscal-old/src/fiscal/db/models.py`) to the new Drizzle schema
(`src/db/fiscal.schema.ts`).

## Table Mapping

| Old Table (PostgreSQL)   | New Table (D1/SQLite)      | Drizzle Export             |
| ------------------------ | -------------------------- | -------------------------- |
| `coleta`                 | `scrape_runs`              | `scrapeRuns`               |
| `prestacao_contas`       | `accountability_reports`   | `accountabilityReports`    |
| `categoria_ref`          | `categories`               | `categories`               |
| `subcategoria_ref`       | `subcategories`            | `subcategories`            |
| `fornecedor`             | `vendors`                  | `vendors`                  |
| `unidade`                | `units`                    | `units`                    |
| `lancamento`             | `entries`                  | `entries`                  |
| `subtotal_categoria`     | `category_subtotals`       | `categorySubtotals`        |
| `aprovador`              | `approvers`                | `approvers`                |
| `documento`              | `documents`                | `documents`                |
| `analise_documento`      | `document_analyses`        | `documentAnalyses`         |
| `alerta`                 | `alerts`                   | `alerts`                   |

## Column Mapping by Table

### coleta → scrape_runs

| Old Column       | New Column         | Type Change                    | Notes                    |
| ---------------- | ------------------ | ------------------------------ | ------------------------ |
| `id`             | `id`               | INTEGER → integer (autoInc)    |                          |
| `data_execucao`  | `executed_at`      | DateTime → timestamp_ms        | Renamed to English       |
| `status`         | `status`           | String(20) → text              |                          |
| `erros`          | `errors`           | Text → text                    | Renamed to English       |
| `duracao_seg`    | `duration_seconds` | Numeric(10,2) → real           | Renamed to English       |

### prestacao_contas → accountability_reports

| Old Column               | New Column            | Type Change               | Notes                              |
| ------------------------ | --------------------- | ------------------------- | ---------------------------------- |
| `id`                     | `id`                  | INTEGER → integer         |                                    |
| `coleta_id`              | `scrape_run_id`       | FK → FK                   | Follows parent table rename        |
| `periodo`                | `period`              | String(7) → text          | Renamed to English                 |
| `accountability_book_id` | `external_book_id`    | Integer → integer         | Renamed for clarity                |
| `total_receitas`         | `total_revenue`       | Numeric(14,2) → real      | Renamed to English                 |
| `total_despesas`         | `total_expenses`      | Numeric(14,2) → real      | Renamed to English                 |
| `saldo_inicial`          | `opening_balance`     | Numeric(14,2) → real      | Renamed to English                 |
| `saldo_mes`              | `month_balance`       | Numeric(14,2) → real      | Renamed to English                 |
| `saldo_acumulado`        | `accumulated_balance` | Numeric(14,2) → real      | Renamed to English                 |
| `url_origem`             | `source_url`          | Text → text               | Renamed to English                 |
| `created_at`             | `created_at`          | DateTime → timestamp_ms   |                                    |
| `updated_at`             | `updated_at`          | DateTime → timestamp_ms   |                                    |

### categoria_ref → categories

| Old Column       | New Column      | Type Change          | Notes              |
| ---------------- | --------------- | -------------------- | ------------------ |
| `id`             | `id`            | INTEGER → integer    |                    |
| `nome`           | `name`          | String(100) → text   | Renamed to English |
| `tipo_movimento` | `movement_type` | String(1) → text     | Renamed to English |

### subcategoria_ref → subcategories

| Old Column      | New Column    | Type Change          | Notes                         |
| --------------- | ------------- | -------------------- | ----------------------------- |
| `id`            | `id`          | INTEGER → integer    |                               |
| `categoria_id`  | `category_id` | FK → FK              | Follows parent table rename   |
| `nome`          | `name`        | String(100) → text   | Renamed to English            |

Old unique constraint `uq_subcategoria_ref_cat_nome` → new unique index `subcategories_category_id_name_idx`

### fornecedor → vendors

| Old Column | New Column | Type Change          | Notes              |
| ---------- | ---------- | -------------------- | ------------------ |
| `id`       | `id`       | INTEGER → integer    |                    |
| `nome`     | `name`     | String(200) → text   | Renamed to English |

### unidade → units

| Old Column | New Column | Type Change          | Notes              |
| ---------- | ---------- | -------------------- | ------------------ |
| `id`       | `id`       | INTEGER → integer    |                    |
| `bloco`    | `block`    | String(1) → text     | Renamed to English |
| `numero`   | `number`   | Integer → integer    | Renamed to English |
| `codigo`   | `code`     | String(10) → text    | Renamed to English |

### lancamento → entries

| Old Column           | New Column              | Type Change             | Notes                              |
| -------------------- | ----------------------- | ----------------------- | ---------------------------------- |
| `id`                 | `id`                    | INTEGER → integer       |                                    |
| `prestacao_id`       | `report_id`             | FK → FK                 | Follows parent table rename        |
| `data`               | `date`                  | Date → text (ISO)       | Stored as YYYY-MM-DD string        |
| `descricao`          | `description`           | Text → text             | Renamed to English                 |
| `valor`              | `amount`                | Numeric(14,2) → real    | Renamed to English                 |
| `tipo_movimento`     | `movement_type`         | String(1) → text        | Renamed to English                 |
| `subcategoria_ref_id`| `subcategory_id`        | FK → FK                 | Simplified name                    |
| `unidade_id`         | `unit_id`               | FK → FK                 | Follows parent table rename        |
| `fornecedor_id`      | `vendor_id`             | FK → FK                 | Follows parent table rename        |
| `documento_id`       | `external_document_id`  | Integer → integer       | Renamed for clarity (not a FK)     |
| `url_origem`         | `source_url`            | Text → text             | Renamed to English                 |
| `created_at`         | `created_at`            | DateTime → timestamp_ms |                                    |
| `updated_at`         | `updated_at`            | DateTime → timestamp_ms |                                    |

### subtotal_categoria → category_subtotals

| Old Column           | New Column       | Type Change             | Notes                         |
| -------------------- | ---------------- | ----------------------- | ----------------------------- |
| `id`                 | `id`             | INTEGER → integer       |                               |
| `prestacao_id`       | `report_id`      | FK → FK                 | Follows parent table rename   |
| `subcategoria_ref_id`| `subcategory_id` | FK → FK                 | Simplified name               |
| `valor`              | `amount`         | Numeric(14,2) → real    | Renamed to English            |
| `tipo_movimento`     | `movement_type`  | String(1) → text        | Renamed to English            |
| `created_at`         | `created_at`     | DateTime → timestamp_ms |                               |
| `updated_at`         | `updated_at`     | DateTime → timestamp_ms |                               |

Old unique constraint `uq_subtotal_categoria_prestacao_subref` → new unique index `category_subtotals_report_subcategory_idx`

### aprovador → approvers

| Old Column     | New Column  | Type Change          | Notes                       |
| -------------- | ----------- | -------------------- | --------------------------- |
| `id`           | `id`        | INTEGER → integer    |                             |
| `prestacao_id` | `report_id` | FK → FK              | Follows parent table rename |
| `nome`         | `name`      | String(200) → text   | Renamed to English          |
| `status`       | `status`    | String(50) → text    |                             |

### documento → documents

| Old Column              | New Column              | Type Change          | Notes                         |
| ----------------------- | ----------------------- | -------------------- | ----------------------------- |
| `id`                    | `id`                    | INTEGER → integer    |                               |
| `lancamento_id`         | `entry_id`              | FK (unique) → FK     | Follows parent table rename   |
| `brcondos_document_id`  | `external_document_id`  | Integer → integer    | Generalized name              |
| `caminho_arquivo`       | `file_path`             | Text → text          | Renamed to English            |

### analise_documento → document_analyses

| Old Column          | New Column            | Type Change              | Notes                       |
| ------------------- | --------------------- | ------------------------ | --------------------------- |
| `id`                | `id`                  | INTEGER → integer        |                             |
| `documento_id`      | `document_id`         | FK (unique) → FK         |                             |
| `data_analise`      | `analyzed_at`         | DateTime → timestamp_ms  | Renamed to English          |
| `tipo_documento`    | `document_type`       | String(50) → text        | Renamed to English          |
| `valor_extraido`    | `extracted_amount`    | Numeric(14,2) → real     | Renamed to English          |
| `valor_match`       | `amount_match`        | Boolean → boolean (int)  | Renamed to English          |
| `cnpj_extraido`     | `extracted_cnpj`      | String(20) → text        | Renamed to English          |
| `nome_emitente`     | `issuer_name`         | String(200) → text       | Renamed to English          |
| `fornecedor_match`  | `vendor_match`        | Boolean → boolean (int)  | Renamed to English          |
| `data_extraida`     | `extracted_date`      | String(10) → text        | Renamed to English          |
| `data_match`        | `date_match`          | Boolean → boolean (int)  | Renamed to English          |
| `numero_documento`  | `document_number`     | String(100) → text       | Renamed to English          |
| `descricao_servico` | `service_description` | Text → text              | Renamed to English          |
| `raw_response`      | `raw_response`        | Text → text              |                             |
| `error`             | `error`               | Text → text              |                             |

### alerta → alerts

| Old Column       | New Column         | Type Change              | Notes                                  |
| ---------------- | ------------------ | ------------------------ | -------------------------------------- |
| `id`             | `id`               | INTEGER → integer        |                                        |
| `data_geracao`   | `created_at`       | DateTime → timestamp_ms  | Renamed, uses standard timestamp col   |
| `tipo`           | `type`             | String(50) → text        | Renamed to English                     |
| `severidade`     | `severity`         | String(20) → text        | Renamed; values: critical/warning/info |
| `titulo`         | `title`            | String(200) → text       | Renamed to English                     |
| `descricao`      | `description`      | Text → text              | Renamed to English                     |
| `periodo_ref`    | `reference_period` | String(7) → text         | Renamed to English                     |
| `resolvido`      | `resolved`         | Boolean → boolean (int)  | Renamed to English                     |
| `data_resolucao` | `resolved_at`      | DateTime → timestamp_ms  | Renamed to English                     |
| `notas`          | `notes`            | Text → text              | Renamed to English                     |
| `dados_json`     | `metadata`         | JSONB → text             | Stored as JSON string in SQLite        |

## Severity Value Mapping

| Old (pt-BR) | New (en)   |
| ----------- | ---------- |
| `critico`   | `critical` |
| `atencao`   | `warning`  |
| `info`      | `info`     |

## Type Changes Summary

| PostgreSQL Type  | D1/SQLite Type              | Notes                                   |
| ---------------- | --------------------------- | --------------------------------------- |
| `Numeric(14,2)`  | `real`                      | D1 has no decimal type; use real        |
| `Date`           | `text` (ISO YYYY-MM-DD)     | Stored as string for SQLite compat      |
| `DateTime`       | `integer` (timestamp_ms)    | Unix ms epoch, matches auth schema      |
| `Boolean`        | `integer` (mode: boolean)   | SQLite stores as 0/1                    |
| `JSONB`          | `text`                      | Store as JSON string, parse in app      |
| `String(N)`      | `text`                      | SQLite text has no length enforcement   |
