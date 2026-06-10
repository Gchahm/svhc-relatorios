# Research: Real Documents Entity

Phase 0 — decisions resolving the spec's clarified points and the integration unknowns.

## D1. Where does the build step run, and at what scope?

- **Decision**: A standalone `python -m analysis build-documents [--remote]` CLI command, ALSO invoked at the start of `run_analysis` (before the per-period checks). It reads D1 **globally** (all periods) regardless of any `--periodo` filter.
- **Rationale**: Documents are global (FR-001). The existing loader (`load_all_periods`) and checks are period-scoped, so a per-period build would mis-dedup an NF that recurs across months and mis-sum overpayment. Reading `attachment_analyses` straight from D1 (joined to attachments→entries→reports) is global by construction. Folding it into `analyze` means the `analyze-docs` agent (apply-extractions → analyze → mismatches) produces documents with no extra step (clarified placement: "after apply-extractions, before checks"); exposing it standalone supports backfill.
- **Alternatives rejected**: (a) build inside the per-period `run_advanced` — wrong scope, would duplicate work and miss cross-period links; (b) a TypeScript/Drizzle build in an API route — splits the pipeline across two languages and runtimes; the analysis CLI already owns derivation from analyses.

## D2. Document identity, normalization, and the confidence gate

- **Decision**: identity = `(normalize_number(document_number), normalize_cnpj(extracted_cnpj))`.
  - `normalize_number`: `str.strip()`, strip non-alphanumeric separators (spaces, `.`, `/`, `-`), uppercase. Empty ⇒ not confident.
  - `normalize_cnpj`: keep digits only; confident **iff** exactly 14 digits remain.
  - A document is created only when BOTH are confident (FR-004).
- **Rationale**: The issue names (NF number + issuer CNPJ) as the dedup key and calls out noisy extraction; requiring a structurally-valid 14-digit CNPJ plus a non-empty normalized number is the minimal gate that prevents spurious rows while resolving re-scans of the same invoice (FR-005). Source fields are `attachment_analyses.document_number` and `attachment_analyses.extracted_cnpj` (already populated by the roll-up).
- **Deterministic id**: `det_id("document", normalized_number, normalized_cnpj)` so the id IS a pure function of the key — `INSERT OR REPLACE` + `uniqueIndex(document_number, issuer_cnpj)` make re-runs idempotent (FR-006). Stored `document_number`/`issuer_cnpj` are the **normalized** values (the key); `issuer_name`/`document_type` are display fields from the analysis.
- **Alternatives rejected**: keying on `attachments.content_hash` (per-scan bytes; misses re-scans — the main reuse vector); keying on raw unnormalized number (formatting splits one NF into many).

## D3. Total-value drift across siblings (FR-009)

- **Decision**: per-analysis total = `nf_total_for_reconciliation(record_responses, fallback=extracted_amount)` (invoice gross `valor_total`, else roll-up). The document's `total_value` = the **maximum** confident per-analysis total across ALL analyses sharing the key, recomputed each global run.
- **Rationale**: Order-independent and deterministic (no read-modify-write, so idempotent). Conservative for the critical alert: a higher total can only *reduce* the computed over-amount, so it never manufactures a false `document_overpayment`. Recomputing globally each run means the value can't drift on re-run.
- **Alternatives rejected**: "first confident" (order-dependent, non-deterministic across query orderings); "latest by analyzed_at" (read-modify-write, and a later worse extraction could wrongly trip the alert).

## D4. document_entries payload — live vs. snapshot

- **Decision**: the link stores provenance only: `document_id`, `entry_id`, `source_attachment_id`. The claimed amount is read **live** from `entries.amount` at reconciliation and listing time.
- **Rationale**: Issue's recommended option; a later correction to an entry amount is reflected without rebuilding links, and there's a single source of truth for the amount (the ledger). `source_attachment_id` preserves which attachment evidenced the link.
- **Alternatives rejected**: snapshotting the amount on the link (drifts from the ledger; needs invalidation).

## D5. Overpayment detection + alert writeback

- **Decision**: `check_document_overpayment(target)` queries `documents`, `document_entries`, and `entries.amount` + the entry's `accountability_reports.period` globally. For each document: `status = reconcile_group(sum(live entry amounts), total_value)`. When `status == "over_claim"`, emit a `document_overpayment` (critical) alert with `reference_period = max(linked entry periods)` and metadata `{document_id, document_number, issuer_cnpj, total_value, sum_entries, over_amount, entry_ids}`.
- **Writeback**: in `run_analysis`, after the existing per-period alert loop, do `DELETE FROM alerts WHERE type = 'document_overpayment'` then `upsert_tables({"alerts": [...]})`. Unconditional delete-by-type makes it idempotent and independent of which periods were filtered (the per-period `DELETE … WHERE reference_period` loop cannot reliably clear a cross-period alert).
- **Single-entry document**: included; flagged only if that lone entry's amount alone exceeds the total beyond tolerance (`reconcile_group` already yields `over_claim` then).
- **Rationale**: Reuses the exact tolerance/classification (`reconcile_group`: 5% rel OR R$0.05 abs). The deep-link metadata shape matches feature 018's `entry_ids` so `AlertsClient` renders per-entry links with no UI change.
- **Alternatives rejected**: emitting per-period overpayment via `run_advanced` (double-counts a cross-period document once per period; can't see all links).

## D6. Retiring duplicate_billing (FR-012)

- **Decision**: remove the `check_duplicate_billing` call from `run_advanced` and delete the function. Its over-claim signal is fully replaced by `document_overpayment` (entity-backed, cross-period, deep-linked). Keep `nf_groups.group_attachments`/`reconcile_group` (still used by `apply-extractions` for `amount_match` and now by overpayment).
- **Rationale**: Issue's recommended full replacement; avoids double-reporting the same case. The split `amount_match` reconciliation in `apply-extractions` is a separate concern and is retained.
- **Migration note**: existing persisted `duplicate_billing` alerts are cleared naturally — `analyze` re-runs delete per-period alerts and no longer re-emit the type; the global overpayment writeback replaces the signal.

## D7. d1.py TABLE_ORDER

- **Decision**: insert `"documents"` then `"document_entries"` into `TABLE_ORDER` (after the attachment tables, before `alerts`) so batched upserts respect FK order (`document_entries` → `documents`, `entries`). No change to escaping/merge logic.

## D8. UI patterns (confirmed from Explore)

- **List**: mirror `vendors/page.tsx` (server component; auth at layout) + `VendorsClient.tsx` (client fetch + filter + virtualized table). Add a **type** `Select` filter and a **search** `Input` (number/issuer). Status badge mirrors `AlertsClient` badge variants: over = `destructive`, within = green outline, under = yellow outline, unknown total = `secondary`.
- **API auth**: copy the `ALLOWED_ROLES` session guard from `/api/vendors/route.ts` verbatim.
- **Detail + deep link**: clicking a document opens a `Dialog` listing its linked entries; each row links via `entryHref(period, entryId)` = `/dashboard/entries?period=<>&entry=<>` (feature 018), which `EntriesClient` already handles (selects period, scrolls, highlights, auto-opens analysis). Full list in the dialog ⇒ no Popover needed.
- **Nav**: add a `NavLink` (lucide `FileText`) in `dashboard/layout.tsx` near the entity links.
