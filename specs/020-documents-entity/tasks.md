# Tasks: Real Documents Entity

**Feature**: 020-documents-entity | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Tests are OPTIONAL and NOT generated — the repo has no test framework (constitution III). Validation is `pnpm lint` + `pnpm format` + `pnpm build` + the manual pipeline run in [quickstart.md](./quickstart.md).

**User stories** (by dependency): US3 (persist global deduped documents, P1) → US1 (overpayment detection, P1, depends on US3) → US2 (browse UI, P2, depends on US3).

---

## Phase 1: Setup (schema + plumbing)

- [x] T001 Add `documents` and `documentEntries` tables + relations to `src/db/fiscal.schema.ts` per [data-model.md](./data-model.md): `documents` (id, documentNumber text(100) notNull, issuerCnpj text(14) notNull, issuerName text(200), documentType text(50), totalValue real, timestamps) with `uniqueIndex documents_number_cnpj_idx` and `index documents_type_idx`; `documentEntries` (id, documentId FK→documents, entryId FK→entries, sourceAttachmentId FK→attachments, createdAt) with `uniqueIndex document_entries_doc_entry_idx` + `index` on documentId and entryId; add `documentsRelations` (many documentEntries) and `documentEntriesRelations` (one document/entry/attachment). Use the existing `uuid()` / `timestamps` helpers.
- [x] T002 Generate + commit the migration: run `node_modules/.bin/drizzle-kit generate` (or `pnpm db:generate`) producing `drizzle/0011_*.sql`; apply locally with `pnpm db:migrate:dev`. Confirm the SQL creates both tables + indexes.
- [x] T003 Add `"documents"` then `"document_entries"` to `TABLE_ORDER` in `scripts/common/d1.py` (after `attachment_analysis_records`, before `alerts`) so batched upserts respect FK order.

**Checkpoint**: schema migrated; Python upserts can target the new tables.

---

## Phase 2: Foundational (shared module — blocks US3/US1)

- [x] T004 Create `scripts/analysis/documents.py` with normalization + keying helpers: `normalize_number(s)` (strip, remove non-alphanumeric separators, uppercase; return `""` when empty), `normalize_cnpj(s)` (digits only; return the 14-digit string or `None` when not exactly 14), and `document_key(analysis)` returning `(number, cnpj)` or `None` when either is not confident (FR-004/FR-005). Import `det_id` from `common` and `nf_total_for_reconciliation` from `.attachments`. Keep stdlib-only.

**Checkpoint**: identity/normalization seam ready.

---

## Phase 3: US3 — Persist one global, deduplicated document per invoice (P1)

**Goal**: build documents + links from analyses, globally, idempotently. **Independent test**: run `build-documents`; one row per unique (normalized number, CNPJ), linked to every referencing entry; attachments missing either field create nothing; re-run leaves counts unchanged.

- [x] T005 [US3] Implement `build_documents(target)` in `scripts/analysis/documents.py`: query all analyses globally from D1 (`attachment_analyses` JOIN `attachments` JOIN `entries`, plus `attachment_analysis_records` for totals — decode `response` JSON like `loader._load_period_raw` does); group by `document_key`; per group emit one `documents` row (`id = det_id("document", number, cnpj)`, normalized number/cnpj, first non-empty issuerName/documentType, `total_value` = max confident `nf_total_for_reconciliation(record_responses, fallback=extracted_amount)` across the group); per analysis emit one `document_entries` row (`id = det_id("document_entry", document_id, entry_id)`, `source_attachment_id = attachment_id`). Upsert via `d1.upsert_tables({"documents": [...], "document_entries": [...]})`. Log counts + skipped (missing number/CNPJ).
- [x] T006 [US3] Wire the `build-documents` subcommand in `scripts/analysis/__main__.py`: add the parser (only `--remote`, no `--periodo` — global), import + call `build_documents(target)`, print a one-line summary. Match the existing subcommand style.
- [x] T007 [US3] Call `build_documents(target)` at the start of `run_analysis` in `scripts/analysis/__init__.py` (after `load_all_periods`, before `run_all_checks`) so `analyze` (and the analyze-docs agent's apply→analyze sequence) produces documents automatically.
- [x] T008 [US3] Verify per [quickstart.md](./quickstart.md) step 2: `build-documents` then count `documents`/`document_entries`; confirm no rows from analyses missing number/CNPJ; re-run and confirm both counts unchanged (SC-001, SC-004).

**Checkpoint**: documents persisted + deduped; US1 and US2 can build on them.

---

## Phase 4: US1 — Detect an invoice claimed above its value (P1, depends on US3)

**Goal**: a `document_overpayment` alert when linked entries sum above the document total; supersede `duplicate_billing`. **Independent test**: a known over-claim yields exactly one critical alert with correct totals + entry deep links, and no `duplicate_billing` for that case.

- [x] T009 [US1] Implement `check_document_overpayment(target) -> list[Alert]` in `scripts/analysis/documents.py`: query `documents` + `document_entries` + `entries.amount` + the entry's `accountability_reports.period` globally; per document compute `sum_entries = sum(live amounts)` and `status = reconcile_group(sum_entries, total_value)`; when `over_claim`, build an `Alert` (type `document_overpayment`, severity `critical`, `id = det_id("alert", reference_period, "document_overpayment", document_id)`, `reference_period = max(linked periods)`, metadata `{document_id, document_number, issuer_cnpj, total_value, sum_entries, over_amount, entry_ids}`). Reuse `reconcile_group` from `.nf_groups` and the `Alert` model.
- [x] T010 [US1] In `run_analysis` (`scripts/analysis/__init__.py`), after the per-period alert writeback loop, run `check_document_overpayment(target)`, then `d1.execute_sql("DELETE FROM alerts WHERE type = 'document_overpayment'", target=target)` and `d1.upsert_tables({"alerts": [a.to_dict() for a in overpayment_alerts]}, target=target)` (skip upsert when empty). Log the count.
- [x] T011 [US1] Retire `check_duplicate_billing` in `scripts/analysis/checks/advanced.py`: remove its call from `run_advanced` and delete the function. Keep the `group_attachments`/`reconcile_group`/`nf_total_for_reconciliation` imports only if still used elsewhere in the file (else drop the now-unused imports to satisfy lint).
- [x] T012 [US1] Verify per [quickstart.md](./quickstart.md) step 3: `analyze` then `SELECT type, count(*) FROM alerts GROUP BY type` shows `document_overpayment` and no `duplicate_billing`; spot-check one alert's metadata has `entry_ids` and correct `over_amount` (SC-003).

**Checkpoint**: overpayment detection live, entity-backed, idempotent.

---

## Phase 5: US2 — Browse documents and their entries (P2, depends on US3)

**Goal**: an auth-gated `/dashboard/documents` listing with filter/search, status badge, and drill-into-entries deep links. **Independent test**: open the page, filter by type, search by number/issuer, open a document, follow an entry deep link to the highlighted row.

- [x] T013 [P] [US2] Create `src/app/api/documents/route.ts` (GET): copy the `ALLOWED_ROLES` session guard from `src/app/api/vendors/route.ts`; `await getDb()`; select documents left-joined to a `document_entries`→`entries` aggregate (group by document) returning `{id, documentNumber, issuerCnpj, issuerName, documentType, totalValue, linkedCount, sumEntries}`; compute `status` (`over`/`within`/`under`/`unknown`) in TS using the 5%-relative-OR-R$0.05-absolute tolerance; order by issuerName/documentNumber. Per [contracts/documents-api.md](./contracts/documents-api.md).
- [x] T014 [P] [US2] Create `src/app/api/documents/[id]/route.ts` (GET): same auth guard; return the document plus `entries[]` (join `document_entries`→`entries`→`accountability_reports` for `period`): `{entryId, period, date, description, amount, sourceAttachmentId}`, plus `status`/`sumEntries`; `404` when missing. Per [contracts/documents-api.md](./contracts/documents-api.md).
- [x] T015 [US2] Create `src/app/dashboard/documents/page.tsx` as a server component rendering `<DocumentsClient />` (mirror `src/app/dashboard/vendors/page.tsx`; auth handled by the dashboard layout).
- [x] T016 [US2] Create `src/app/dashboard/documents/DocumentsClient.tsx`: fetch `/api/documents`; render a table with number, issuer, type, total, linked count, sum, and a status `Badge` (over=`destructive`, within=green outline, under=yellow outline, unknown=`secondary`, mirroring `AlertsClient`); a type `Select` filter + a number/issuer search `Input`; clicking a row opens a `Dialog` that fetches `/api/documents/[id]` and lists linked entries, each a deep link `/dashboard/entries?period=<period>&entry=<entryId>` (reuse the feature-018 `entryHref` shape from `AlertsClient`). Use existing `@/components/ui/*`.
- [x] T017 [US2] Add a "Documents" `NavLink` (lucide `FileText`) to `src/app/dashboard/layout.tsx` near the entity links (e.g. by Vendors/Entries).
- [x] T018 [US2] Verify per [quickstart.md](./quickstart.md) step 4: listing renders with badges; type filter + search work; a document's entry deep link lands on `/dashboard/entries` with the row highlighted + analysis dialog open; an alerts-page `document_overpayment` alert renders per-entry links (SC-005).

**Checkpoint**: full browse + drill-in shipped.

---

## Phase 6: Polish & cross-cutting

- [x] T019 [P] Update docs: the **Attachments vs. Documents** note in `CLAUDE.md` now describes a *built* entity (documents table, N:N `document_entries`, build step, overpayment alt), and `scripts/README.md` + `scripts/pipeline-flow.md` document `build-documents` + its place in `analyze`/the analyze-docs agent, and the `duplicate_billing` → `document_overpayment` replacement (FR-017).
- [x] T020 Run `pnpm lint` and `pnpm format`; fix any findings. Run `pnpm build` and confirm tsc/Next build passes. Confirm `drizzle/0011_*.sql` + regenerated schema are committed.

---

## Dependencies & ordering

- **Phase 1 (Setup)** → **Phase 2 (Foundational)** → **US3** → {**US1**, **US2**} → **Polish**.
- US1 and US2 both depend only on US3 (persisted documents); they are independent of each other and can proceed in parallel once US3 is done.
- T013 and T014 are `[P]` (separate route files). T019 is `[P]` (docs only).

## Parallel example

After US3 (T005–T008) lands, US1 (T009–T012) and US2 (T013–T018) can run concurrently. Within US2, T013 ∥ T014 (different files), then T015/T016 (client depends on both routes), T017 independent.

## MVP

US3 + US1 (Phases 1–4): documents persist globally and overpayment is detected — the core fraud signal. US2 (the browse UI) is the next increment.
