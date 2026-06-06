# Research: NF multi-entry reconciliation

**Feature**: 005-nf-multi-entry-reconciliation | **Date**: 2026-06-06

This document resolves the open design questions for grouping sibling documents that share one Nota Fiscal, reconciling their amounts as a group, deduplicating the vision pass, and emitting an over-claim alert.

---

## Decision 1 — Grouping key for "same NF"

**Decision**: Group documents by a **content hash (md5) over the document's page image files**. A document's `file_path` is a `;`-separated list of page paths; the group key is the joined md5 of those page files (order-preserving). Documents whose page bytes are identical form one NF group.

**Rationale**: Confirmed empirically. In `data/scrape/2025-12.json` the sibling copies of NF 1057 (and the TPA internet pair) are byte-identical even though each is stored under a different per-entry filename and carries a different `external_document_id`. Grouping on content is exact and robust:

- `file_path` differs per sibling (named by `entry_id`), so it cannot be the key.
- `external_document_id` differs per sibling (each entry has its own), so it cannot be the key.
- NF number extraction is noisy (partial values, `/A1` suffixes), so it is only a secondary corroboration.

Verified grouping output over `2025-12.json`:

- 4 docs → md5 group `c7006cdb…` (administration / assembly / books / tax-obligations), sibling sum **7160.32**.
- 2 docs → md5 group `938f504f…` (internet R$ 288,59 + JUROS/MULTAS R$ 5,96), sibling sum **294.55**.

**Alternatives considered**:

- _NF number + issuer CNPJ from extracted records_: rejected as primary key — extraction is unreliable and only available post-VLM. Kept as a secondary signal that may corroborate a content group.
- _Perceptual / fuzzy image hashing_: rejected — overkill and risks merging visually-similar-but-distinct documents; the spec requires exact content identity.

**Hashing note**: hash file bytes (not decoded pixels) so it works regardless of `.jpg`/`.png` and needs no image library. Reuse the path-resolution that `documentos.py` already performs on `file_path`.

---

## Decision 2 — What total to reconcile against, and the comparison

**Decision**: Reconcile `sum(sibling entry amounts)` against the shared NF's **gross total** (`valor_total` from the invoice page), using the existing tolerance. Reuse a single tolerance constant consistent with the codebase: relative `< 0.05` (the `documentos.py` amount-match tolerance) OR absolute R$ 0.05 (the consistency-check `TOLERANCE`) — match within **either** to be safe on both small and large totals.

**Rationale**: In the confirmed `1057` example the four entries sum to exactly the NF gross total (7160.32). Entries are allocations of the gross invoice, so the gross `valor_total` is the correct reconciliation target. The roll-up `extracted_amount` uses a payment-precedence (paid → boleto → net → gross) intended for single-entry payment validation; for split reconciliation the **gross invoice total** is the right basis. Fall back to the roll-up `extracted_amount` only when gross `valor_total` is unavailable.

**Outcomes** (group size > 1):

- `|sum − total| within tolerance` → **reconciled**: every sibling `amount_match = True`.
- `sum − total > tolerance` (over-claim) → **mismatch**: siblings `amount_match = False` **and** emit `duplicate_billing` alert.
- `total − sum > tolerance` (under-claim / incomplete split) → **mismatch**: siblings `amount_match = False`, **no** over-claim alert.

**Alternatives considered**:

- _Reconcile against net (`valor_liquido`)_: rejected — would break the confirmed gross-summing example. Net is relevant only when entries themselves are recorded net of retentions, which is not the observed shape.

---

## Decision 3 — Where reconciliation and the alert live

**Decision**: Split the work across the two existing pipeline stages, sharing one grouping helper:

- **`documentos.py` (run_document_analysis)** does grouping, dedup, and group-level `amount_match` (Stories 1 & 3).
- **A new check `check_duplicate_billing`** in the checks pipeline emits the over-claim alert (Story 2).

**Rationale**: The two stages write the period JSON independently. `analise/__init__.py` does `raw["alerts"] = [...]` — a full overwrite — so any alert appended by `documentos.py` would be clobbered by a subsequent `run_analysis`. The checks pipeline is the rightful owner of `alerts`. Both stages need the same "same NF" definition, so the grouping lives in a shared `nf_groups.py` imported by both. The check reads the NF gross total from `document_analyses` (already in the JSON after analysis) and re-derives groups by hashing the same page files — no schema change and no cross-stage state.

**Alternatives considered**:

- _Emit the alert from `documentos.py` by appending to `raw["alerts"]`_: rejected — clobbered by `run_analysis`; also mixes two concerns the codebase keeps separate.
- _Persist the group key / over-claim flag into `document_analyses` for the check to read_: rejected — would require a D1 column (schema change, Principle I) for marginal benefit; re-hashing a handful of small files in the check is cheap.

---

## Decision 4 — Dedup of the vision pass and fan-out

**Decision**: Within a period, group the candidate documents by content hash. Run the VLM **once per group** (on the first document's pages), then **fan the extracted page records / roll-up out** to a `DocAnalysisResult` for each sibling document (each keeps its own `document_id` so every document still gets an analysis row and the importer is unchanged). Reconciliation uses the full sibling set.

**Rationale**: Satisfies SC-005 (one pass for the `1057` quad instead of four) and FR-007 while preserving one `document_analyses` row per document (the UI lists per-document analyses). Group membership for reconciliation is computed over **all** period documents+entries — not the filtered/limited work list — so a sibling excluded by `min_amount`/`limit`/already-analyzed still contributes its amount to the group sum (FR-002 correctness).

**Alternatives considered**:

- _Write a single analysis row shared by all siblings_: rejected — changes the per-document UI/import contract and the `document_id`→analysis mapping.
- _Keep N independent VLM passes but only fix reconciliation_: rejected — fails Story 3 / SC-005 and leaves the compute waste and possible cross-copy disagreement.

---

## Decision 5 — Alert shape and severity

**Decision**: New alert `type = "duplicate_billing"`, `severity = "critical"`, period-scoped, built with the existing `_alert(...)` / `Alert` pattern and `det_id("alert", period, "duplicate_billing", <group discriminator>)`. Title in Portuguese (consistent with sibling alerts), e.g. _"Nota fiscal cobrada acima do valor em {period}"_. `metadata` carries: `nf_total`, `sum_entries`, `over_claim` (difference), `entry_ids`, `document_ids`, and the corroborating `numero_documento`/`cnpj_emitente` when available.

**Rationale**: `critical` matches the gravity of a genuine over-claim and the severity of other integrity-breaking alerts (balance mismatches). The deterministic `id` keeps re-runs idempotent (same group → same alert id), consistent with every other check. No new alert columns are needed (`type`, `severity`, `metadata` already exist).

**Alternatives considered**: `warning` severity — rejected; an invoice claimed above face value is a stronger signal than a subtotal divergence and should sort to the top.

---

## Decision 6 — No UI / no schema change

**Decision**: Make no changes to `src/` or the Drizzle schema or `import-to-d1.mjs`.

**Rationale**: `AlertsClient.tsx` fetches `/api/alerts` and renders `title`/`severity`/`description` generically (no hardcoded type allowlist), so a new `duplicate_billing` type appears automatically. The document-analyses view renders `amountMatch` generically, so corrected values surface without change. `import-to-d1.mjs` already flattens `document_analyses`/`analysis_records` and imports `alerts`. Confirmed by grep over `src/app/dashboard/alerts` and `src/app/dashboard/document-analyses`.

---

## Open risks / notes

- **Ordering dependency**: the `duplicate_billing` check needs `document_analyses` to be populated (to read the NF gross total). If a group has not been analyzed, the check skips it gracefully (FR-009). Document this in the operational notes (run `analyze-docs` before `analyze`).
- **NF total source within a group**: pick the gross `valor_total` from the analyzed (first) document's invoice page record; if absent, fall back to the roll-up `extracted_amount`; if still absent, the group is non-reconcilable (no false reconcile, no alert).
