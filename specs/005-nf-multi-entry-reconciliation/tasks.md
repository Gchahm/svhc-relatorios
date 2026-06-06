---
description: "Task list for 005-nf-multi-entry-reconciliation"
---

# Tasks: Reconcile a single Nota Fiscal shared across multiple entries

**Input**: Design documents from `/specs/005-nf-multi-entry-reconciliation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/nf-grouping.md

**Tests**: No automated test framework is configured (constitution Principle III — tests OPTIONAL, not requested). Verification is fixture-based via the quickstart and a throwaway script.

**Organization**: Tasks grouped by user story. US1 (reconciliation) is the MVP.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No project initialization needed — the Python pipeline already exists. Confirm baseline only.

- [x] T001 Capture the current (buggy) baseline: run the document analysis over `data/scrape/2025-12.json` (or read its existing `document_analyses`) and record which sibling documents in the NF `1057` quad and the TPA internet pair currently have `amount_match = 0`, so the fix can be verified against it.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared "same NF" grouping helper that US1, US2, and US3 all build on.

**⚠️ CRITICAL**: No user story work can begin until this is complete.

- [x] T002 Create `scripts/scraper/analise/nf_groups.py` with `content_hash(file_path: str) -> str | None` (joined md5 of the `;`-separated page files, resolving paths the same way `documentos.py` does) and `group_documents(documents: list[dict]) -> dict[str, list[dict]]` (maps content hash → sibling document dicts; unreadable/unhashable documents fall into their own singleton group keyed by document id — never merged on failure). Per `contracts/nf-grouping.md`.

**Checkpoint**: Grouping helper exists and is import-safe; running it over `2025-12.json` reproduces the two known multi-entry groups (quad sum 7160.32, pair sum 294.55).

---

## Phase 3: User Story 1 - Legitimate split no longer raises false mismatch alerts (Priority: P1) 🎯 MVP

**Goal**: Reconcile `sum(sibling amounts)` against the NF total so split invoices stop being flagged as mismatches; single-entry behavior unchanged.

**Independent Test**: Re-run analysis over `data/scrape/2025-12.json`; the NF `1057` quad and the TPA internet pair no longer report `amount_match = 0`; an unrelated single-entry document keeps its prior outcome.

### Implementation for User Story 1

- [x] T003 [US1] In `scripts/scraper/analise/documentos.py`, add a group-reconciliation helper that, given a group's sibling entry amounts and the shared NF total, returns the outcome per `data-model.md` (reconciled within tolerance / over-claim / under-claim / non-reconcilable). Reuse the existing tolerance — relative `< 0.05` OR absolute `<= 0.05` (do not introduce a new threshold). Add it as a module-level function so the check in US2 can reuse it.
- [x] T004 [US1] In `run_document_analysis` (`documentos.py`), build NF groups over **all** period documents+entries (not the filtered/limited work list) using `nf_groups.group_documents`, and resolve each group's sibling entry amounts via the period entry map. Make the per-group sibling sum available when validating a document.
- [x] T005 [US1] In `analyze_single_document` / its caller, when a document belongs to a multi-entry NF group, set `amount_match` from the **group** reconciliation (reconciled → True; over/under-claim → False) using the NF gross total (`valor_total` of the analyzed invoice page, else roll-up `extracted_amount`, else leave `amount_match`/`extracted_amount` as today and treat as non-reconcilable). Preserve the existing per-entry comparison exactly for singleton groups (FR-004).
- [x] T006 [US1] Update the run summary/log lines in `run_document_analysis` so a reconciled split reports OK (and, where useful, notes "reconciled as NF group of N") rather than printing N spurious mismatches.

**Checkpoint**: US1 done — the two known splits reconcile; SC-001/SC-002/SC-003 hold for the document-analysis stage.

---

## Phase 4: User Story 2 - Duplicate-billing over-claim is flagged (Priority: P2)

**Goal**: Emit a distinct `duplicate_billing` critical alert when a shared NF's siblings sum to more than its total.

**Independent Test**: A synthetic fixture with two entries sharing one NF (total 100) summing to 150 yields exactly one `duplicate_billing` alert (`over_claim = 50`); a correctly-summing split yields none; an under-claim yields none.

### Implementation for User Story 2

- [x] T007 [P] [US2] Add `check_duplicate_billing(p: PeriodData, refs: RefIndex) -> list[Alert]` (in `scripts/scraper/analise/checks/advanced.py`, or a new `checks/duplicate_billing.py` imported there): group `p.documents` via `nf_groups.group_documents`; for each multi-entry group, read the NF gross total from `p.raw["document_analyses"]` (match by `document_id`), sum the sibling entry amounts, and when `sum - nf_total > tolerance` build a `critical` Alert (`type="duplicate_billing"`) via the existing `_alert(...)` pattern with `det_id("alert", period, "duplicate_billing", <group discriminator>)`. Skip groups with no extractable NF total (FR-009). Populate `metadata` with `nf_total`, `sum_entries`, `over_claim`, `entry_ids`, `document_ids`, and `numero_documento`/`cnpj_emitente` when available. Reuse the US1 group-reconciliation helper so the over-claim boundary is defined once.
- [x] T008 [US2] Register `check_duplicate_billing` in `scripts/scraper/analise/checks/__init__.py` (`run_all_checks`) so `run_analysis` persists its alerts into `raw["alerts"]`. Confirm the check needs `document_analyses` present and degrades to no-op when absent.

**Checkpoint**: US2 done — over-claim → one alert; legitimate split / under-claim → none (SC-004). Alert flows through the existing alerts view and importer unchanged.

---

## Phase 5: User Story 3 - Each unique NF is analyzed once (Priority: P3)

**Goal**: Run the VLM once per unique shared NF and fan the result out to all siblings.

**Independent Test**: Analyzing the `1057` quad invokes the VLM once (not four times); all four siblings report the same extracted NF total and identity fields.

### Implementation for User Story 3

- [x] T009 [US3] In `run_document_analysis` (`documentos.py`), deduplicate the VLM work: for each NF group, analyze the representative (first) document once, then construct a `DocAnalysisResult` per sibling document that reuses the representative's page records and roll-up (each keeps its own `document_id`/`entry_id`); apply the US1 group `amount_match` to each. Ensure siblings excluded by `min_amount`/`limit`/already-analyzed still contribute to the group sum but only the in-scope siblings get persisted results.
- [x] T010 [US3] Adjust the progress logging so a deduped group logs one "analyzing NF group of N" pass instead of N independent passes, keeping multi-page per-page logs intact.

**Checkpoint**: US3 done — one VLM pass per shared NF (SC-005); siblings carry consistent extracted values.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T011 [P] Document the grouping/reconciliation behavior and the `duplicate_billing` alert (key, gross-total basis, tolerance reuse, over- vs under-claim) in `CLAUDE.md` under the document-analysis notes (FR-011).
- [x] T012 Run `pnpm format` (and `pnpm lint` if any TS touched — none expected) to satisfy the commit quality gate; ensure no unrelated files are reformatted.
- [x] T013 Run the quickstart verification end-to-end (`quickstart.md`): re-analyze `2025-12.json`, confirm zero false mismatches on the quad + pair and one VLM pass per group; exercise the synthetic over-claim/under-claim fixtures for the alert; then discard any throwaway fixtures/scripts.

---

## Dependencies & Execution Order

- **Setup (T001)**: baseline capture — do first for verifiability.
- **Foundational (T002)**: BLOCKS all stories.
- **US1 (T003–T006)**: after T002. MVP. T003 before T004/T005.
- **US2 (T007–T008)**: after T002; reuses the US1 reconciliation helper (T003), so land T003 first. Otherwise independent of US1's `documentos.py` edits (different files), so T007 is [P] vs US1.
- **US3 (T009–T010)**: after US1 (extends the same `run_document_analysis` grouping introduced in T004).
- **Polish (T011–T013)**: after the desired stories.

### Parallel Opportunities

- T007 (US2, in `checks/`) can proceed in parallel with US1's `documentos.py` work once the shared helper (T002) and the reconciliation helper (T003) exist.
- T011 (docs) is [P] with code once behavior is settled.

---

## Implementation Strategy

### MVP First (User Story 1)

1. T001 baseline → T002 grouping helper → T003–T006 reconciliation.
2. **STOP and VALIDATE**: the two known splits reconcile, single-entry unchanged.

### Incremental Delivery

- US1 (false positives fixed) → US2 (over-claim alert) → US3 (dedup). Each is independently testable and shippable; none regresses the previous.

## Notes

- No D1 schema change, no `import-to-d1.mjs` change, no `src/` change — alerts and amount-match render generically.
- Define the over-claim boundary once (US1 helper) and reuse it in US2 to keep the split/over-claim line consistent.
- Commit after each story; keep the diff confined to `scripts/scraper/analise/` plus `CLAUDE.md`.
