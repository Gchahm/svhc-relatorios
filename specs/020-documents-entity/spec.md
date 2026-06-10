# Feature Specification: Real Documents Entity (N:N documents↔entries, overpayment detection, listing UI)

**Feature Branch**: `020-documents-entity`  
**Created**: 2026-06-10  
**Status**: Draft  
**Input**: GitHub issue #29 — "Real documents entity: N:N documents↔entries, overpayment detection, and a documents listing"

## Overview

Today the auditing tool downloads a multi-page **attachment** per ledger entry and classifies its pages, but the *real fiscal document* inside those pages (an NF / NFS-e / receipt / boleto) has no persisted identity. The "same invoice attached to several entries" signal — the main reuse/over-claim vector — exists only transiently inside one analysis run.

This feature makes the **document** a first-class, persisted, globally-deduplicated entity that links many-to-many to ledger entries, detects when the entries referencing one document together claim more than the document is worth (**overpayment**), and gives auditors a place to **browse documents and drill into the entries that reference each one**.

## Clarifications

### Session 2026-06-10

Resolved automatically (one-shot pipeline) from the issue's explicit decision points, using the recommended defaults; downstream artifacts follow these:

- Q: Where does the document build step run? → A: A standalone `build-documents` CLI command that the `analyze` flow also invokes after `apply-extractions` and before the checks (so the `analyze-docs` agent produces documents with no extra manual step, and backfill remains possible standalone).
- Q: Keep `duplicate_billing` or replace it? → A: Replace — the over-claim case of `duplicate_billing` is fully superseded by `document_overpayment`; `check_duplicate_billing` is retired. The split-reconciliation that sets `amount_match` during `apply-extractions` is unrelated and is retained.
- Q: What does a document↔entry link store? → A: Provenance only — the source `attachment_id` (for traceability); the entry amount is read live from the ledger at reconciliation/listing time, never frozen on the link.
- Q: Total-value drift rule when siblings disagree? → A: Store the **maximum** confident reconciliation total (`nf_total_for_reconciliation`) seen across the document's analyses. Order-independent/deterministic and conservative — it never inflates the over-amount, avoiding false overpayment alerts. The build step refreshes it (monotonic max) on each run.
- Q: "Confident" threshold for keying a document? → A: A non-empty normalized document number AND an issuer CNPJ that reduces to exactly 14 digits after stripping punctuation. Missing/short CNPJ or empty number ⇒ no document, no link.
- Q: NF-number normalization for the identity key? → A: Trim whitespace and strip non-alphanumeric separators (spaces, dots, slashes, hyphens), uppercase; keep the original for display.
- Q: Single-entry documents in the listing? → A: Listed (for browsing). Flagged overpaid only if that single entry's amount alone exceeds the document total beyond tolerance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Detect an invoice claimed above its value across entries (Priority: P1)

An auditor needs to know when one fiscal document (e.g. NF #4521 from vendor X) is referenced by several ledger entries whose amounts, summed, exceed the document's total value — the same invoice billed beyond its face value, whether across line-item splits or across periods.

**Why this priority**: This is the core fraud/forgery signal the whole tool exists to surface. It is the reason the entity must be persisted and global (an NF re-submitted in a later month as a different scan is still the same NF). It replaces the transient `duplicate_billing` signal with an entity-backed, durable one.

**Independent Test**: Analyze period data containing a known shared-NF over-claim and confirm a single `document_overpayment` alert appears, naming the document, its total, the summed entry amounts, the over-amount, and deep-linking to every referencing entry — and that the old `duplicate_billing` alert no longer also fires for the same case.

**Acceptance Scenarios**:

1. **Given** two entries each referencing the same NF (same NF number + issuer CNPJ) whose amounts sum to more than the NF total beyond tolerance, **When** the analysis pipeline runs, **Then** exactly one `document_overpayment` (critical) alert is raised for that document, carrying the document id/number, total value, sum of linked entry amounts, the over-amount, and the list of affected entry ids.
2. **Given** the same shared-NF over-claim, **When** the alerts are produced, **Then** no `duplicate_billing` alert is raised for it (the new alert supersedes the old one).
3. **Given** two entries referencing the same NF whose amounts sum to the NF total within tolerance (a legitimate split), **When** analysis runs, **Then** no overpayment alert is raised.
4. **Given** an over-claiming document spanning two different periods, **When** both periods have been analyzed, **Then** the document links to entries from both periods and the overpayment is computed against the sum of all of them.

---

### User Story 2 - Browse documents and the entries that reference them (Priority: P2)

An auditor wants to open a documents list, filter and search it, and click into any document to see every ledger entry that references it, then jump straight to a specific entry.

**Why this priority**: Persisting documents is only half the value; auditors need to explore the new entity. It depends on the entity existing (Story 1's schema + build step) but delivers standalone browsing value even before any alert fires.

**Independent Test**: With documents persisted, open the documents page, confirm each row shows the NF number, issuer, type, total value, number of linked entries, and the summed linked-entry amount with an over/within/under-total status badge; filter by document type and search by NF number / issuer; open one document and follow a per-entry deep link into the entries view with that entry highlighted.

**Acceptance Scenarios**:

1. **Given** persisted documents, **When** the auditor opens the documents listing, **Then** each document is shown with NF number, issuer name, type, total value, count of linked entries, sum of linked entry amounts, and a status badge (over / within / under the total).
2. **Given** the listing, **When** the auditor filters by a document type and/or searches by NF number or issuer text, **Then** only matching documents are shown.
3. **Given** a document with linked entries, **When** the auditor opens it, **Then** each linked entry is listed and provides a deep link to the entries view for that entry's period with the entry selected/highlighted.
4. **Given** the documents routes, **When** an unauthenticated visitor requests them, **Then** access is denied like the other dashboard routes.

---

### User Story 3 - Persist one global, deduplicated document per unique invoice (Priority: P1)

The pipeline must turn confidently-extracted invoice identities into exactly one persisted document per unique (NF number + issuer CNPJ), accruing entry links as more attachments/periods are analyzed, and must NOT manufacture documents from attachments lacking a confident identity.

**Why this priority**: This is the data-integrity backbone both other stories rest on. Spurious or duplicated document rows would corrupt the overpayment signal and the listing.

**Independent Test**: Run the build step over analyses where some have a confident NF number + CNPJ and some are missing one or both; confirm one document row exists per unique (number, CNPJ), each linked to every entry whose attachment carried that identity, and that attachments missing either field produced no document and no link.

**Acceptance Scenarios**:

1. **Given** several attachment analyses that confidently carry the same NF number and issuer CNPJ, **When** the build step runs, **Then** exactly one document row exists for that pair, linked to each corresponding entry.
2. **Given** an attachment analysis missing a confident NF number OR a confident issuer CNPJ, **When** the build step runs, **Then** no document row and no link is created from it.
3. **Given** the build step has already created a document, **When** it runs again (same or another period), **Then** it does not duplicate the document; it refreshes the total and adds any new entry links idempotently.
4. **Given** the same logical NF number formatted differently across scans (whitespace/punctuation), **When** the build step runs, **Then** both resolve to one document via normalization.

---

### Edge Cases

- **Total-value drift across siblings**: different copies/siblings of the same NF report slightly different totals — the system MUST pick a single deterministic total per document (see FR-009).
- **Single-entry document**: a document referenced by exactly one entry is still listed (for browsing); it can only be flagged overpaid if that one entry's amount alone exceeds the document total beyond tolerance.
- **Missing document total**: a document whose total value could not be extracted cannot be reconciled — it is listed (no status badge / "unknown" status) and raises no overpayment alert.
- **Confidence threshold not met**: attachment with a present-but-low-confidence NF number or CNPJ does not create a document.
- **Re-runs / idempotency**: re-analyzing a period must not double-link entries or duplicate documents.
- **Entry amount source**: linked-entry amounts are read live from the ledger at reconciliation/listing time (the link stores provenance, not a frozen amount), so a later correction to an entry amount is reflected without rebuilding links.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist a **document** entity, one row per unique fiscal document, identified by the pair (normalized NF/document number, issuer CNPJ). This identity MUST be globally unique (not scoped to a period).
- **FR-002**: The system MUST persist a many-to-many relationship linking documents to ledger entries, with each (document, entry) pair represented at most once.
- **FR-003**: After attachment analyses are available, the system MUST derive documents from them: for every analysis that confidently carries BOTH a document number AND an issuer CNPJ, upsert exactly one document keyed by the normalized (number, CNPJ) pair and upsert a link to that attachment's entry.
- **FR-004**: The system MUST NOT create a document or a link from an attachment analysis that lacks a confident document number, lacks a confident issuer CNPJ, or both.
- **FR-005**: The system MUST normalize the document number before using it as part of the identity key (trim surrounding whitespace and strip non-significant formatting), so the same invoice rendered with different incidental formatting resolves to one document.
- **FR-006**: Document creation and linking MUST be idempotent and MUST accrue links across periods: re-running over the same or additional periods MUST NOT duplicate a document or a link, and MUST add links from newly-analyzed entries to the existing document.
- **FR-007**: Each document MUST store the issuer name and document type (NF / NFS-e / receipt / boleto / …) and a total value representing the invoice's gross amount.
- **FR-008**: The document total value MUST be set from the invoice gross using the existing reconciliation total rule (the persisted analysis's invoice total, falling back to its roll-up amount).
- **FR-009**: When sibling copies of the same document disagree on the total, the system MUST resolve to one deterministic total per document via a defined rule (see Assumptions).
- **FR-010**: The system MUST raise a **`document_overpayment`** alert (critical) for any document where the sum of its linked entries' amounts exceeds the document total value beyond the existing reconciliation tolerance.
- **FR-011**: The overpayment alert metadata MUST carry the document id, document number, the affected entry ids, the document total value, the summed linked-entry amount, and the over-amount, and MUST deep-link to each affected entry using the same alert→entry deep-link mechanism the alerts page already uses.
- **FR-012**: The new overpayment alert MUST supersede the prior transient over-claim signal so the same case is not double-reported (the prior over-claim alert is removed/replaced).
- **FR-013**: The system MUST compute linked-entry sums from the live ledger entry amounts (not a frozen snapshot); the link MAY store the source attachment id for provenance.
- **FR-014**: The system MUST provide a documents listing view, auth-gated like the other dashboard routes, showing for each document: NF/document number, issuer name, type, total value, number of linked entries, sum of linked-entry amounts, and a status badge indicating whether that sum is over / within / under the total (or unknown when the total is missing).
- **FR-015**: The listing MUST support filtering by document type and free-text search by document number and/or issuer.
- **FR-016**: From a document the auditor MUST be able to see all linked entries, each providing a deep link to the entries view for that entry's period with the entry selected/highlighted.
- **FR-017**: Project documentation MUST be updated so the "Attachments vs. Documents" guidance describes documents as a built entity rather than a reserved one, and the pipeline/flow docs describe the new build step.

### Key Entities *(include if feature involves data)*

- **Document**: a unique real fiscal document (NF/NFS-e/receipt/boleto). Identity = (normalized document number, issuer CNPJ). Attributes: document number (normalized), issuer CNPJ, issuer name, document type, total value (invoice gross), timestamps. Global across periods.
- **Document↔Entry link**: a many-to-many association between one document and one ledger entry it is referenced by. Unique per (document, entry). May carry provenance (the source attachment id). Entry amount is read live, not stored on the link.
- **Ledger entry** (existing): an accountability line item with an amount and a period; the target of document links and of deep links.
- **Attachment analysis** (existing): the per-attachment roll-up + per-page records from which a document's number, issuer CNPJ, type, and total are sourced.
- **Alert** (existing): the user-facing finding record; gains the `document_overpayment` type and loses the superseded `duplicate_billing` over-claim case.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After analyzing a dataset, the number of persisted documents equals the number of unique (normalized number, issuer CNPJ) pairs confidently present in the analyses — no duplicates and no rows from attachments missing either field.
- **SC-002**: Every entry whose attachment confidently carries a given (number, CNPJ) is linked to that one document, including entries from different periods (links accrue across runs).
- **SC-003**: Every shared-document over-claim (linked entries summing above the document total beyond tolerance) produces exactly one `document_overpayment` alert with correct totals and working per-entry deep links, and produces no `duplicate_billing` alert for the same case.
- **SC-004**: Re-running the pipeline over already-analyzed periods changes neither the document count nor the link count (idempotent) when inputs are unchanged.
- **SC-005**: An auditor can locate a specific document by type filter + number/issuer search and reach a referencing entry's highlighted row in the entries view in a single click from the document.

## Assumptions

- **Confidence threshold for keying**: a field is "confident" when the analysis populates it with a non-empty, structurally-valid value — a non-empty normalized document number, and an issuer CNPJ matching the Brazilian CNPJ shape (14 digits after stripping punctuation). Both must be present to key a document. (Refined in clarify if needed.)
- **NF-number normalization**: trim whitespace and strip non-alphanumeric separators (spaces, dots, slashes, hyphens) for the identity key, preserving the displayed original where useful. Issuer CNPJ is normalized to its 14 digits for keying.
- **Total-value drift rule (FR-009)**: per-analysis total is `nf_total_for_reconciliation` (invoice `valor_total` else roll-up); the document's stored `total_value` is the **maximum** confident total across its analyses — order-independent, deterministic, and conservative (never inflates the over-amount). The build step refreshes it as a monotonic max on each run. (Clarified 2026-06-10.)
- **Build-step placement**: a standalone `build-documents` CLI command, also invoked by the `analyze` flow after `apply-extractions` and before the checks. (Clarified 2026-06-10.)
- **duplicate_billing replacement**: the over-claim case of `duplicate_billing` is fully replaced by `document_overpayment` (recommended in the issue). The separate split-reconciliation that sets `amount_match` during `apply-extractions` is unrelated and is retained.
- **Single-entry documents**: kept in the listing for browsing; flagged overpaid only if that one entry's amount alone exceeds the document total beyond tolerance.
- **No new third-party dependencies**: pipeline stays Python stdlib-only via the existing D1/R2 wrapper; frontend reuses existing UI primitives and the existing deep-link.

## Dependencies

- Existing attachment-analysis pipeline (`apply-extractions` must have run so `attachment_analyses` exist).
- Existing reconciliation math (`nf_total_for_reconciliation`, `reconcile_group`, tolerance bands) — reused, not reinvented.
- Existing alert→entry deep-link behavior (feature 018) on the alerts page and entries view.
- Existing auth-gating for dashboard routes and the D1 database / Drizzle migration mechanism.
