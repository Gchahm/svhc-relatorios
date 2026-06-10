# Feature Specification: Rename "documents" → "attachments" (reserve "documents" for the real N:N entity)

**Feature Branch**: `015-rename-documents-attachments`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "now I need to do some updates to the tables structure, we have been downloading the 'attachments' from brcondos and calling them documents, but they are really just 'attachments' since an attachment has multiple pages and these pages might be different documents like a NF or a receipt etc. The reason I want to name them correctly is to pave the way for the actual 'documents' feature, that is a N to N relationship with 'entries' so we can do things like check that the NF xxxx is linked to 4 entries and the sum of the entries does not exceed the value on the NF and other things like that."

## Context & Motivation

The system scrapes the brcondos accountability portal. For each ledger **entry** it downloads one file — today that file is modeled and named a **document** (the `documents` table, one row per entry). In reality each downloaded file is an **attachment**: a single multi-page bundle whose individual pages may be _different_ real fiscal documents — a Nota Fiscal (NF), a receipt, a boleto, a payment proof, etc.

Calling the per-entry bundle a "document" blocks the next capability the owner wants: a **real document** entity (e.g. "NF #12345") that can be **linked to several entries** (a many-to-many relationship) so the system can verify things like _"NF #12345 is linked to 4 entries and the sum of those entries does not exceed the NF's face value."_ That future entity needs the name **document**.

This feature corrects the terminology — the current per-entry bundle becomes an **attachment** — so the name "document" is freed and the data model accurately reflects "an attachment is a multi-page bundle that contains documents." It establishes the conceptual seam for the future N:N documents feature without necessarily building that feature's reconciliation logic yet.

## Clarifications

### Session 2026-06-09

- Q: How far should this feature go regarding the new N:N "documents" entity? → A: Rename only — free the name and document the seam; no new `documents` table, join, or cross-entry check (FR-009).
- Q: How should existing production data be handled during the rename? → A: Drop & re-scrape — destructive schema change, no in-place migration; fiscal data is reproducible from the portal (FR-008).
- Q: Should the R2 storage binding/bucket (`DOCUMENTS` / `fiscal-documents`) and the portal-facing external id (`external_document_id`) also be renamed? → A: No — page-image storage scheme and portal-mapping fields are preserved (Assumptions); only the per-entry _bundle entity_ and its analysis tables are renamed.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Accurate terminology across the system (Priority: P1)

As the auditor/maintainer, I want the per-entry multi-page bundle to be named **attachment** everywhere — the data model, the analysis pipeline, the API, and the UI — so the vocabulary matches reality and "document" is no longer overloaded.

**Why this priority**: This is the core deliverable. Everything else ("paving the way") depends on the name being freed and the concept being correctly modeled. It is a behavior-preserving rename: nothing about _what the system computes_ changes, only the names.

**Independent Test**: Run the full scrape → classify → analyze → mismatches pipeline for a period and confirm it produces the same alerts and roll-ups as before; confirm the entries page and the analysis detail dialog render the same data, now labelled "attachment(s)". No reference to the old per-entry "document" naming remains in user-facing surfaces.

**Acceptance Scenarios**:

1. **Given** a scraped period, **When** the scraper runs, **Then** each entry's downloaded multi-page bundle is stored as an **attachment** (with its external id and page-image storage keys), exactly one per entry, identical in content to what the old `documents` row held.
2. **Given** an analyzed attachment, **When** I open the entries/analysis UI, **Then** the bundle is labelled "attachment" and its per-page extracted records are shown, with no remaining "document" label for the bundle itself.
3. **Given** the analysis pipeline (classify → apply-extractions → analyze → mismatches), **When** it runs end-to-end after the rename, **Then** it produces equivalent alerts, roll-ups, and mismatch summaries to a pre-rename run on the same period.
4. **Given** the shared-NF grouping (byte-identical pages across entries) and duplicate-billing checks, **When** they run after the rename, **Then** they behave identically — they continue to group by page content and reconcile sums against the NF total.

---

### User Story 2 - "Document" reserved as a distinct, future-facing concept (Priority: P2)

As the maintainer, I want the term **document** to refer exclusively to a _real fiscal document_ (an NF, receipt, boleto, …) that lives **inside** one or more attachment pages and can relate to **many entries**, so the next feature can build cross-entry reconciliation (e.g. "NF linked to 4 entries, sum ≤ NF value") on a clean foundation.

**Why this priority**: This is the "pave the way" goal. It need not ship the reconciliation logic, but the data model and naming must leave an unambiguous, documented place for the future N:N `documents`↔`entries` relationship so it can be added without re-naming anything again.

**Independent Test**: Inspect the data model and project documentation; confirm there is a clearly documented, reserved concept of a real "document" (distinct from an attachment) that is many-to-many with entries, and that no existing table/code occupies that name.

**Acceptance Scenarios**:

1. **Given** the corrected model, **When** a future feature introduces a real "document" entity, **Then** the name "document" is free and the intended relationship (a document links to many entries; an entry can be backed by many documents) is documented and unobstructed by the attachment rename.
2. **Given** the per-page extracted records (each page may be a distinct NF/receipt/boleto), **When** the future documents feature is built, **Then** those page-level records are the natural source from which real documents are identified, and the spec records that lineage.

---

### Edge Cases

- **Existing stored data**: production may already hold scraped attachments + analyses + alerts. The rename must not silently lose them — see FR-008 (data handling) and the open clarification on migrate-vs-rescrape.
- **Page-image storage keys**: page images are stored under per-period keys derived from the bundle's stored path. The rename must keep the key-derivation rule and stored values consistent so existing/re-materialized images still resolve.
- **Auth tables untouched**: this change is confined to the fiscal data model; authentication tables are out of scope and must be unaffected.
- **Single-entry vs split**: an attachment is one-per-entry; a _document_ inside it may be shared across entries. The rename must not conflate the two cardinalities — attachments stay one-per-entry; the future document is the N:N side.
- **Mixed-language identifiers**: portal field names are Portuguese (e.g. `documento`); the rename must keep external/portal mappings working while internal naming becomes "attachment".

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The system MUST model the per-entry, multi-page downloaded bundle as an **attachment** (renamed from the current "document" concept), preserving all of its current attributes: its external identifier, its stored page-image keys/path, and its one-to-one association with an entry.
- **FR-002**: The system MUST rename the analysis-of-an-attachment concept and its per-page records to attachment-scoped names (the current `document_analyses` and `document_analysis_records`), so the entire chain reads as "attachment → its analysis → its per-page records" with no "document" naming for the bundle.
- **FR-003**: The rename MUST be behavior-preserving: the scrape, classification, extraction-apply, analysis, alerting, shared-NF grouping, duplicate-billing detection, and the self-improving classification loop MUST all produce equivalent results to before the rename.
- **FR-004**: All user-facing surfaces (entries page, analysis detail dialog, page-image viewer, any labels/headings) MUST present the bundle as an "attachment" (or localized equivalent), with no leftover "document" label referring to the bundle.
- **FR-005**: All code, API routes, CLI commands, scripts, and internal identifiers that refer to the per-entry bundle MUST use the "attachment" name consistently; references that point at the _portal's_ external concept may retain the portal's own term where that mapping is required.
- **FR-006**: The term **document** MUST be reserved for a real fiscal document (NF/receipt/boleto/…) that is many-to-many with entries; after this feature no table, route, or primary code path may use "document" to mean the per-entry bundle.
- **FR-007**: The project's living documentation (CLAUDE.md / AGENTS.md and the relevant patterns notes) MUST be updated so the attachment-vs-document distinction and the intended N:N documents↔entries relationship are recorded for future work.
- **FR-008**: The schema change MAY be applied destructively (**drop & recreate**, then re-scrape from the portal) rather than data-preservingly. There is no requirement to migrate existing production rows in place — fiscal data is reproducible from brcondos, and the local database has already been cleared. The change MUST therefore leave the system in a state where a fresh scrape repopulates all renamed tables correctly.
- **FR-009**: The scope of _this_ feature is **rename-only**: rename the per-entry bundle concept (and its analysis + per-page-record tables) to attachment-scoped names, free the name "document," and document the future N:N `documents`↔`entries` seam. This feature MUST NOT create the new `documents` table, the documents↔entries join, or any cross-entry reconciliation check — those belong to a separate future feature. Per-page records that hint at distinct real documents MUST remain available as the lineage that future feature will build on (FR-002, US2).

### Key Entities _(include if feature involves data)_

- **Attachment** _(renamed from "document")_: the single multi-page file downloaded from the portal for one entry. Attributes: external identifier, stored page-image keys/path, one-to-one link to its entry. Holds no semantic claim about what _kind_ of document each page is — that lives in its per-page analysis records.
- **Attachment analysis** _(renamed from "document analysis")_: the heterogeneity-aware roll-up of analyzing one attachment (type, extracted amount and match flags, issuer/CNPJ, dates, etc.). One per attachment.
- **Attachment page record** _(renamed from "document analysis record")_: one extracted record per page (per analysis kind) — each page may be a distinct real document (NF/receipt/boleto/payment proof). These page-level records are the lineage from which the future "document" entity is identified.
- **Entry** _(unchanged)_: a ledger line item in an accountability report. One entry has one attachment today; in the future an entry may be backed by many documents and a document by many entries.
- **Document** _(reserved, future)_: a real fiscal document (e.g. "NF #12345") identified from attachment pages, **many-to-many with entries**, enabling cross-entry reconciliation such as "this NF is linked to N entries and the sum of those entries must not exceed the NF's face value." Defined here **only to reserve the name and relationship** — this rename-only feature creates no `documents` table or join; a later feature builds it (FR-009).

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: After the change, **zero** primary code paths, data-model tables, API routes, or user-facing labels use "document" to mean the per-entry bundle (verifiable by search and UI inspection).
- **SC-002**: A full pipeline run on a previously-analyzed period produces the **same** set of alerts, roll-up values, and mismatch summary entries as a pre-rename run on that period (no regressions from the rename).
- **SC-003**: The analysis detail UI and entries page render attachments and their per-page records with correct "attachment" labelling and no broken references (page images still resolve and display).
- **SC-004**: The data model and project documentation unambiguously describe a reserved "document" concept that is many-to-many with entries, such that a developer can begin the future documents feature without renaming anything introduced here.

## Assumptions

- An attachment remains **one-per-entry** (mirrors the current `documents.entry_id` uniqueness and the brcondos per-entry download). The many-to-many cardinality belongs to the _future_ document entity, not to attachments.
- Page images continue to be stored under the existing per-period storage scheme; only the naming around the owning record changes, and the key-derivation rule is preserved.
- Authentication tables and any non-fiscal data are entirely out of scope.
- The portal exposes data in Portuguese; external/portal field mappings keep their source terms where required, while internal naming standardizes on "attachment."
- Both local and production data are reproducible from the portal, so the rename is applied destructively (drop & recreate + re-scrape); no in-place data migration is required (FR-008).
- This feature is rename-only; the new N:N `documents` entity and any cross-entry NF reconciliation are explicitly a **separate future feature**, out of scope here (FR-009).
