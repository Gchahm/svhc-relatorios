# Feature Specification: Reconcile a single Nota Fiscal shared across multiple entries

**Feature Branch**: `005-nf-multi-entry-reconciliation`  
**Created**: 2026-06-06  
**Status**: Draft  
**Input**: GitHub issue #8 — "Single Nota Fiscal attached to multiple entries causes false amount-mismatch alerts (and masks duplicate-billing)"

## Overview

The source accounting system frequently attaches **one Nota Fiscal (NF) to several distinct accountability entries**. This happens in two recurring shapes:

- **(a) Line-item split** — one invoice is allocated across several subcategories (e.g. one NF totaling R$ 7.160,32 split into administration, assembly, books, and tax-obligation entries).
- **(b) Principal vs. penalty split** — the invoice principal is one entry and `JUROS/MULTAS` (interest/fines) is a second entry sharing the same NF.

Because the same NF is downloaded once per entry and validated in isolation, the document-amount check today compares the **full NF total** against a **single fractional entry amount**, flagging every sibling as a mismatch even when the books reconcile perfectly. The same reconciliation gap that produces these false positives also means genuine **duplicate-billing fraud** (the same NF claimed multiple times at full value) is never detected.

This feature changes amount validation to reconcile **against the group of entries that share an NF**, removing the false positives and converting the split into a stronger integrity signal that can distinguish a legitimate split from an over-claim.

## Clarifications

### Session 2026-06-06

Resolved by informed default during one-shot clarify (no blocking ambiguities; the issue provided confirmed evidence and a bounded scope):

- Q: What severity should the duplicate-billing / over-claim alert carry? → A: `critical` — an NF claimed for more than its face value is a genuine over-claim and aligns with the severity of other balance/fraud-class alerts.
- Q: How is a sibling entry's amount-match outcome recorded once the group reconciles? → A: Each sibling's per-document amount-match is set to "matched" (the group reconciles); the comparison basis changes from per-entry to group-sum, but the existing per-document match field is still populated so the UI/import need no schema change.
- Q: What is the canonical grouping key? → A: A content hash (e.g. md5) over the document's page image files; entries whose documents are byte-identical form one NF group. NF number + issuer CNPJ are secondary corroboration only.
- Q: Should an under-claim (siblings sum to less than the NF total) reconcile? → A: No — it remains an unreconciled amount mismatch (not a duplicate-billing over-claim), so genuine missing-allocation cases still surface.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Legitimate split no longer raises false mismatch alerts (Priority: P1)

An auditor reviews a period in which one NF was split across several entries (line-item or principal/penalty). Today every sibling entry shows an amount mismatch even though the entries sum exactly to the NF total. The auditor must manually recognize each as a false positive, eroding trust in the mismatch signal.

After this change, when the sibling entries that share an NF sum to the NF total (within the existing rounding tolerance), the group is marked **reconciled** and no amount-mismatch is raised for any sibling.

**Why this priority**: This is the core defect — it produces recurring false positives that undermine the auditing tool's credibility and bury real signal. It must work for the feature to deliver value.

**Independent Test**: Re-run the document analysis over `data/scrape/2025-12.json`. Confirm the NF-e `1057` quad (administration / assembly / books / tax-obligations, summing to R$ 7.160,32) and the TPA Telecom internet pair (internet + `JUROS/MULTAS`, summing to R$ 294,55) no longer report an amount mismatch.

**Acceptance Scenarios**:

1. **Given** four entries sharing one NF whose amounts sum to the NF total, **When** amount validation runs, **Then** the shared NF is treated as reconciled and none of the four entries is flagged as an amount mismatch.
2. **Given** a principal entry plus a `JUROS/MULTAS` entry sharing one NF whose two amounts sum to the NF total, **When** amount validation runs, **Then** neither entry is flagged as an amount mismatch.
3. **Given** a single entry whose own amount matches its (unshared) NF total, **When** amount validation runs, **Then** the existing single-entry match behavior is preserved (no regression).

---

### User Story 2 - Duplicate-billing over-claim is flagged (Priority: P2)

An auditor needs to catch the genuine-fraud counterpart of a legitimate split: the same NF attached to multiple entries whose amounts sum to **more** than the NF face value — i.e. the invoice is being claimed for more money than it is worth.

When a shared NF's sibling entries sum to more than the NF total (beyond the rounding tolerance), the system raises an explicit duplicate-billing / over-claim alert, distinct from the legitimate-split case.

**Why this priority**: This converts the corrected reconciliation into a new fraud-detection capability that directly serves the project's forgery/corruption-detection goal. It depends on the grouping introduced by Story 1.

**Independent Test**: Construct a fixture where two entries share one NF (total R$ 100) but their amounts sum to R$ 150. Run analysis and confirm a duplicate-billing alert is emitted referencing both entries and the over-claim amount, while no such alert is emitted for a correctly-summing split.

**Acceptance Scenarios**:

1. **Given** multiple entries sharing one NF whose amounts sum to more than the NF total (beyond tolerance), **When** analysis runs, **Then** a duplicate-billing alert is emitted identifying the shared NF, the participating entries, the NF total, the sibling sum, and the over-claim difference.
2. **Given** multiple entries sharing one NF whose amounts sum to the NF total within tolerance, **When** analysis runs, **Then** no duplicate-billing alert is emitted.
3. **Given** sibling amounts that sum to **less** than the NF total (an under-claim / possibly incomplete split), **When** analysis runs, **Then** the group is treated as an unreconciled mismatch rather than a duplicate-billing over-claim (the two cases are distinguishable).

---

### User Story 3 - Each unique NF is analyzed once (Priority: P3)

The system currently downloads and vision-analyzes the same NF once per sibling entry (e.g. four identical analysis passes for the `1057` quad), wasting compute and producing redundant analysis rows that can disagree across copies.

When several entries share a byte-identical NF, the system performs the vision analysis **once** for that unique NF and reuses the shared result/roll-up across all sibling entries.

**Why this priority**: Efficiency and consistency improvement. Valuable but not required for the correctness fixes in Stories 1–2; it builds on the same grouping.

**Independent Test**: Run analysis over the `1057` quad and confirm the vision model is invoked once for the shared NF (not four times) and that all four sibling entries reference a consistent extracted NF total.

**Acceptance Scenarios**:

1. **Given** N entries sharing one byte-identical NF, **When** analysis runs, **Then** the vision model is invoked once for that NF and the extracted result is fanned out to all N sibling entries.
2. **Given** the shared analysis is reused, **When** results are persisted, **Then** each sibling entry's analysis reports the same extracted NF total and identity fields.

---

### Edge Cases

- **Noisy / missing NF number**: NF-number extraction is unreliable (partial values, `/A1` suffixes). Grouping MUST NOT rely on the NF number alone; byte-identical document content is the authoritative grouping key, with NF number + issuer identity as a secondary corroborating signal only.
- **Single-entry documents (the common case)**: A document attached to exactly one entry MUST behave exactly as today — its NF total is compared against that one entry's amount.
- **Unparseable / missing NF total**: If the shared NF's total cannot be extracted, the group cannot be reconciled; behavior MUST degrade gracefully (no false reconciliation, no spurious duplicate-billing alert) and the situation should be observable.
- **Mixed-content groups**: If the shared artifact is a payment proof/boleto rather than a clean NF, the amount used for reconciliation MUST follow the existing roll-up precedence conventions.
- **A sibling entry whose amount is zero or negative**: The group sum MUST handle these without crashing; the reconciliation comparison is on the summed total.
- **Documents that are visually similar but not byte-identical**: These MUST NOT be grouped (grouping is on exact content identity, not resemblance).

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The system MUST group accountability entries that share the same Nota Fiscal before validating document amounts, using byte-identical document page content as the authoritative grouping key.
- **FR-002**: For a group of entries sharing one NF, the system MUST reconcile the **sum of the sibling entry amounts** against the extracted NF total, using the existing rounding tolerance, instead of comparing the full NF total against each individual entry.
- **FR-003**: When the sibling sum reconciles to the NF total within tolerance, the system MUST mark all sibling entries as amount-matched (no false mismatch).
- **FR-004**: The system MUST preserve current single-entry behavior unchanged for any document attached to exactly one entry.
- **FR-005**: When a shared NF's sibling amounts sum to **more** than the NF total beyond tolerance, the system MUST emit a duplicate-billing / over-claim alert that is distinct from a legitimate split and from an under-claim.
- **FR-006**: The duplicate-billing alert MUST identify the shared NF, the participating entries, the NF total, the summed sibling amount, and the over-claim difference, and MUST follow the existing alert structure (type, severity, title, description, period, metadata).
- **FR-007**: The system MUST perform the vision analysis once per unique shared NF and reuse the resulting extracted values/roll-up across all sibling entries rather than analyzing each copy independently.
- **FR-008**: Grouping MUST treat the NF number and issuer identity as secondary corroborating signals only; it MUST remain correct when NF-number extraction is partial, suffixed, or missing.
- **FR-009**: The system MUST degrade gracefully when the shared NF total cannot be extracted — neither falsely reconciling the group nor emitting a spurious duplicate-billing alert.
- **FR-010**: Reconciliation thresholds and amount-selection MUST reuse the existing roll-up and tolerance conventions already used for document analysis (the 5% / rounding tolerance), with no new ad-hoc thresholds.
- **FR-011**: The new grouping and reconciliation behavior, and the meaning of the duplicate-billing alert, MUST be documented alongside the existing document-analysis conventions.

### Key Entities _(include if feature involves data)_

- **Nota Fiscal (NF) group**: A set of entries that share the same fiscal document, identified by byte-identical document content. Carries the extracted NF total and the participating entries' amounts.
- **Accountability entry**: An individual line in a period's books, with an amount and a description; one entry may share its NF with sibling entries.
- **Document analysis result**: The extracted/validated values for a document, including the amount used for reconciliation and the amount-match outcome; for shared NFs this is derived once and applied to all siblings.
- **Duplicate-billing alert**: A period-scoped alert raised when a shared NF's sibling amounts exceed its face value, referencing the NF, entries, and over-claim amount.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: After re-analysis of `data/scrape/2025-12.json`, the NF-e `1057` quad and the TPA Telecom internet pair produce **zero** false amount-mismatch results (down from 5 false mismatches today).
- **SC-002**: 100% of documents attached to a single entry retain their pre-change amount-match outcome (no regression on the common case).
- **SC-003**: For any shared-NF group whose sibling amounts sum to the NF total within tolerance, the group is reported as reconciled in 100% of cases.
- **SC-004**: An over-claim group (siblings summing to more than the NF total) raises exactly one duplicate-billing alert, and a correctly-summing split raises none — the two are 100% distinguishable in the output.
- **SC-005**: Each unique shared NF triggers exactly one vision-analysis pass regardless of how many entries reference it (e.g. one pass instead of four for the `1057` quad).

## Assumptions

- Byte-identical page content (a content hash of the document's page image files) is a reliable proxy for "the same NF", consistent with the issue's confirmed evidence that sibling copies are byte-identical.
- The existing 5% / R$ 0.05 rounding tolerance used in document analysis and consistency checks is the correct tolerance for group reconciliation; no new tolerance is introduced.
- The duplicate-billing alert is surfaced through the existing alert pipeline and persisted/imported like other alerts.
- Out of scope (per the issue): changing the scraper to stop re-downloading duplicate NFs, visual forgery detection (#2), and CNPJ validation (#3).
