# Feature Specification: Scraper and analysis operate directly on the database

**Feature Branch**: `014-scraper-direct-insert`  
**Created**: 2026-06-09  
**Status**: Draft  
**Input**: User description: "I want to change the scrapper behavior so it skips the step of saving data into the data folder and it goes straight to inserting data into our server (local or remote depending on what I run)" — plus clarification: "analysis and classification should move to look into the new structure as well."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scrape a period straight into the database (Priority: P1)

An operator runs the scraper for a period (e.g. `2025-12`). Today this produces a JSON file (and a folder of page images) on disk that must then be loaded into the database with a second, separate command. The operator wants a single command that scrapes the source system and lands the structured ledger data (reports, entries, vendors, categories, units, subcategories, approvers, document references, scrape-run metadata) directly into the database, with no intermediate JSON file to manage.

**Why this priority**: This is the core of the request — collapsing scrape + load into one step removes a manual, error-prone hand-off (stale JSON, forgetting to import, importing the wrong file) and is the minimum viable slice that delivers value.

**Independent Test**: Run the scrape command for a fresh period against an empty local database; confirm the period's rows appear in the database tables and that no period JSON file was required as an input to a separate load step.

**Acceptance Scenarios**:

1. **Given** an operator with valid source-system credentials, **When** they run the scrape command for a period, **Then** the structured ledger data for that period is present in the database and the run reports how many rows were written per table.
2. **Given** a period that was already scraped into the database, **When** the operator scrapes the same period again, **Then** the existing rows for that period are updated in place rather than duplicated (re-running is safe/idempotent).
3. **Given** a scrape that fails partway (network/source error), **When** the operator inspects the database, **Then** the database is not left in a half-written, inconsistent state for that period (the period's write either fully lands or the failure is clearly reported and the prior state preserved).

---

### User Story 2 - Choose local or remote database per run (Priority: P1)

The operator can direct a scrape run at either the local development database or the remote (production) database, choosing per invocation, consistent with how the project already selects local vs. remote for its other database operations.

**Why this priority**: The request explicitly calls for "local or remote depending on what I run." Without target selection the feature cannot be used safely — an operator must never have to guess whether they are writing to production.

**Independent Test**: Run the scrape command once targeting local and once targeting remote; confirm each run's rows land only in the intended database and the run output states which target was used.

**Acceptance Scenarios**:

1. **Given** the operator runs the scrape command with no target option, **When** the run completes, **Then** data is written to the local database (safe default) and the output states the target was local.
2. **Given** the operator runs the scrape command with the remote/production option, **When** the run starts, **Then** the output clearly states it is writing to the remote/production database before any rows are written.

---

### User Story 3 - Analysis and classification operate on the database, not the data folder (Priority: P1)

The document-classification / fiscal-analysis pipeline (vision classification, extraction roll-up, alert generation, the self-improving review loop) reads its inputs from the new structure — the database and the object-storage page images — instead of the on-disk `data/scrape/` files, and writes its results (document analyses and alerts) back into the database. After this change there is no period JSON or `data/scrape/` ledger artifact for the pipeline to depend on.

**Why this priority**: The operator explicitly required that "analysis and classification should move to look into the new structure as well." Since this feature removes the on-disk period JSON and page-image folder that the analysis pipeline currently consumes, the pipeline must be re-pointed at the database/object-storage in the same change, or the system is left broken. It is P1, not a follow-up, because the scraper change and the analysis change share the same data-location contract.

**Independent Test**: Scrape a period directly into the database (no `data/scrape/` JSON produced), then run the document-classification and analysis flow for that period; confirm it reads the document records and page images from the new structure and writes document analyses and alerts back into the database, with the application showing them.

**Acceptance Scenarios**:

1. **Given** a period scraped directly into the database with page images in object storage and no on-disk period JSON, **When** the operator runs the document-classification flow, **Then** the flow locates the document records (from the database) and the page images (from object storage) it needs to classify.
2. **Given** classification has produced per-page extractions, **When** the analysis/roll-up runs, **Then** document analyses and alerts are written into the database for that period.
3. **Given** document analyses and alerts exist for a period, **When** the operator views the period in the application, **Then** the analyses and alerts appear, exactly as they do under the current file-based pipeline.
4. **Given** the self-improving review loop runs for a period, **When** it records review verdicts and re-runs scoped to affected documents, **Then** it operates against the database/object-storage state without depending on the removed `data/scrape/` files.

---

### Edge Cases

- **Re-scraping a period**: re-running must update rows in place (idempotent upsert on the deterministic IDs) rather than duplicating reference data (vendors, categories) or ledger rows.
- **Partial/failed scrape**: a source-system error mid-run must report failure clearly. Because every write is an idempotent upsert keyed on deterministic IDs, re-scraping the period fully reconciles any partially-applied rows. All-or-nothing transactional atomicity is **not** assumed (remote database writes may be batched/chunked); the idempotent re-run is the safety net, so the operator is never left with a state a re-scrape can't repair.
- **Remote target without connectivity/credentials**: if the remote database is unreachable or the operator is not authorized, the run must fail fast with a clear message before scraping, not after.
- **Page images**: page images are binary artifacts that do not live in database tables (they are referenced by path and served from object storage). They are uploaded to object storage *as part of the scrape run* — to the emulated local store for a local run, to the remote store for a remote run — and analysis/classification read them from there. No page image rests in the data folder.
- **Analysis working/scratch files**: once the pipeline reads from the database/object-storage and writes results to the database, transient working state (extraction manifest, per-page classification results, review-loop verdicts) should be eliminated where the database makes it unnecessary. Any genuinely-needed transient artifact MAY remain as ephemeral local scratch for now, provided inputs come from the database/object-storage and outputs are written to the database.
- **Empty period**: scraping a period that has no entries should produce a well-defined result (scrape-run metadata recorded, zero ledger rows) rather than an error.
- **Local target and object storage**: the local development environment emulates object storage; a local scrape that pushes images must target the emulated local store so a developer can run the full scrape→analyze→view loop locally.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The scrape operation MUST write the structured ledger data it collects for a period directly into the target database, without requiring a separate, manually invoked load step.
- **FR-002**: The scrape operation MUST NOT produce an on-disk period JSON file as the hand-off to get data into the database; the database is the destination.
- **FR-003**: The operator MUST be able to choose the database target (local or remote/production) per scrape run, consistent with the project's existing local-vs-remote selection convention.
- **FR-004**: The scrape operation MUST default to the local database when no target is specified.
- **FR-005**: The scrape operation MUST clearly report the chosen target (local vs. remote) and write a per-table summary of rows written.
- **FR-006**: Re-scraping a period MUST be idempotent — existing rows for that period are updated in place (keyed on their deterministic identifiers) and reference data is not duplicated.
- **FR-007**: A scrape that fails before completion MUST report the failure, and MUST be safe to re-run: because every write is an idempotent upsert keyed on deterministic IDs, re-scraping the period fully reconciles any partially-applied rows (no duplicates, no orphans). The system MUST NOT depend on cross-statement transactional atomicity, which the remote database does not guarantee.
- **FR-008**: The scrape operation MUST populate the same tables, with the same fields and identifiers, that the current load step populates for ledger data, so that the application reads the data identically regardless of how it arrived.
- **FR-009**: At scrape time, document-analysis and alert data MUST be left in an empty/initial state for the period, exactly as today, so the analysis pipeline can fill them afterward.
- **FR-010**: The scrape operation MUST upload a scraped period's page images to the object storage the application serves them from, as part of the same run — to the emulated local store for a local run and the remote store for a remote run — so analysis/classification and in-app viewing read them without any on-disk `data/scrape/` folder.
- **FR-011**: The document-classification and fiscal-analysis pipeline (vision classification, extraction roll-up, alert generation, self-improving review loop) MUST read its inputs — document records and page images — from the database and object storage, not from `data/scrape/` files.
- **FR-012**: The analysis pipeline MUST write its outputs — document analyses and alerts — into the target database (local or remote, matching the run), so they are visible in the application without a separate load step.
- **FR-013**: The analysis pipeline MUST target the same database (local vs. remote) selection convention as the scrape operation, so an operator runs the whole flow against one chosen environment.
- **FR-014**: The existing separate file-based path (scrape-to-file, then load-file-to-database, then analyze-on-files) MUST be removed; direct-to-database is the only supported path.
- **FR-015**: Transient analysis working artifacts (extraction manifest, per-page classification results, review-loop verdicts) MUST NOT be required as the data hand-off between pipeline steps; where the database supersedes them they are eliminated, and any that remain are ephemeral local scratch only.

### Key Entities *(include if feature involves data)*

- **Period scrape result**: the full set of structured records collected for one period — scrape-run metadata, reference data (categories, vendors, units, subcategories), accountability report(s), ledger entries, category subtotals, approvers, and document references. The payload that must reach the database.
- **Document reference**: a record pointing at a source document and its page images; carries the location/identifier of the page images. Distinct from the binary page-image files themselves.
- **Page image**: a binary image of a single document page. Not stored in database tables; held in object storage and referenced by path/key.
- **Database target**: the destination of a run — the local development database or the remote/production database — selected per run; the same selection governs both scraping and analysis.
- **Document analysis & alerts**: results produced by the analysis pipeline; empty at scrape time, filled later, and written into the database.
- **Analysis working artifacts**: intermediate state the classification/review flow produces (extraction manifest, per-page classification results, review-loop verdicts). No longer the data hand-off between steps; eliminated where the database supersedes them, otherwise ephemeral local scratch.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can take a freshly scraped period from "not in the database" to "fully queryable in the database" with a single command (down from two distinct commands today).
- **SC-002**: For a given period, the database rows produced by the new direct path are identical (same tables, same row count, same field values, same identifiers) to those produced by today's scrape-then-load path.
- **SC-003**: 100% of scrape (and analysis) runs state their database target (local vs. remote) in their output, and the default target is local.
- **SC-004**: Re-scraping the same period twice produces no duplicate rows (row counts per table are stable across the second run).
- **SC-005**: After adopting the new path, the document-analysis flow and in-app document/page viewing for a scraped period work end-to-end with the data folder absent — no regression versus current behavior.
- **SC-006**: A scrape interrupted by a failure reports the error, and a subsequent re-run restores the period to a fully consistent state via idempotent upsert — no duplicate rows and no orphaned rows from the partial run.
- **SC-007**: A developer can run the full scrape → classify → analyze → view loop against the local environment without any `data/scrape/` ledger JSON existing on disk.

## Assumptions

- "Our server" refers to the project's database (Cloudflare D1), which has both a local development instance and a remote/production instance, selected today by explicit flag in the project's other database operations. The new scrape and analysis commands follow that same local-vs-remote convention (default local).
- "The new structure" the analysis/classification pipeline must read from is the database (for records) plus the object storage the application already serves page images from.
- Database schema, table definitions, and identifier-generation scheme are unchanged; only *how* the rows get written and *where* the pipeline reads from changes.
- Idempotent re-write semantics match today's load step (insert-or-replace on deterministic IDs).
- Redesigning what the analysis pipeline computes (its classification logic, checks, reconciliation rules) is out of scope; only its data source/destination changes.
- Page images upload to object storage during the scrape run (local store for local runs, remote store for remote runs); no page image rests in the data folder.
- The old file-based path (scrape-to-JSON, file load step, file-based analysis) is removed, not retained as a fallback.
