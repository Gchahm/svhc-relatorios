# Feature Specification: Deterministic Entry IDs for Duplicate Natural Keys

**Feature Branch**: `034-deterministic-entry-id`
**Created**: 2026-06-12
**Status**: Draft
**Input**: User description: "Make entry id derivation deterministic regardless of portal row order for duplicate natural keys by keying the deterministic id on a portal-native discriminator (the entry external document ids) when present, falling back to the occurrence index only when no portal id exists, logging fallback cases and detecting natural-key id drift on re-scrape"

## Context

Ledger entries scraped from the brcondos portal are assigned stable, deterministic ids so a
re-scrape produces byte-identical ids and the whole upsert/reconciliation design stays
re-scrape-safe (everything keyed by entry id — attachments, document links, alert evidence,
dashboard deep links — survives a re-scrape unchanged).

An entry's id is currently derived from its *natural key* (date, description, amount,
subcategory) plus an **occurrence index** — a 1-based counter that disambiguates two ledger
lines sharing the same natural key (which happens with split charges). The occurrence index is
assigned in the order the rows appear in the portal HTML. If the portal ever reorders two such
rows between scrapes, the two entries swap ids, and everything keyed by those ids silently
re-points to the sibling. This is the gap addressed here (issue #40 / IMP-003).

Today this rarely bites because table order is stable in practice and duplicate natural keys are
rare, but it undermines the "deterministic ids make re-scrape safe" assumption the upsert design
rests on. Observed in the current data: of four duplicate-natural-key groups, one group of three
identical "ENERGIA ELÉTRICA" charges each carries a *distinct* portal document id — exactly the
case a portal-native discriminator stabilizes — while the rest carry no portal id at all.

## Clarifications

### Session 2026-06-12

- Q: When a duplicate doc-bearing entry's id changes under the new derivation, is a data
  migration performed or is correction left to the next re-scrape? → A: No migration; the
  authoritative re-scrape reconciliation self-heals on the next scrape (bounded to the rare
  duplicate-doc rows; unique entries keep their ids).
- Q: How is the id-drift finding surfaced — a new storage table/dashboard element, or the existing
  per-period notes/findings channel? → A: The existing per-period scrape notes channel (the same
  one the consistency check uses); no new schema, migration, or dashboard work, and it does not
  fail the scrape run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Duplicate entries with portal document ids keep stable ids across a reorder (Priority: P1)

When two or more ledger lines share an identical natural key but each references a different
portal document, the entries' ids are derived from those portal document references rather than
from the order the rows happened to appear in. Re-scraping the same period — even if the portal
returns the rows in a different order — yields the same id for the same underlying ledger line.

**Why this priority**: This is the core fix. Without it, a portal reorder of duplicate lines
silently re-points attachments, document links, alert evidence, and dashboard deep links to the
wrong sibling — a correctness/evidence-integrity failure for an auditing tool. The data already
contains a real instance of this exact case.

**Independent Test**: Take a period whose duplicate-natural-key entries each carry a distinct
portal document id. Scrape it, record the entry ids. Re-scrape it with the duplicate rows in the
reverse order. The id assigned to each ledger line (identified by its portal document id) is
unchanged.

**Acceptance Scenarios**:

1. **Given** two entries with the identical natural key but different portal document references,
   **When** the period is scraped twice with the two rows in opposite order, **Then** each ledger
   line keeps the same id across both scrapes.
2. **Given** an entry whose natural key is unique in the period, **When** the period is scraped,
   **Then** its id is identical to the id the previous derivation produced (no id churn for the
   common, non-duplicate case).

---

### User Story 2 - Order-dependent fallback cases are logged so the fragile rows are enumerable (Priority: P2)

When duplicate ledger lines share a natural key AND carry no portal document reference (so no
portal-native discriminator is available), the id necessarily falls back to the order-dependent
occurrence index. Each such fallback is logged with enough detail (period, natural key, count) to
let an operator find the remaining fragile rows.

**Why this priority**: The fallback is unavoidable when the portal gives nothing to key on, but
making those cases visible turns an invisible, untrackable risk into an enumerable, monitorable
one — directly per the issue's suggestion #2.

**Independent Test**: Scrape a period containing duplicate entries with no portal document id and
confirm the run log records a fallback note naming the period and the offending natural key.

**Acceptance Scenarios**:

1. **Given** duplicate entries sharing a natural key with no portal document reference, **When**
   the period is scraped, **Then** a fallback log/note records the period, natural key, and
   duplicate count.
2. **Given** a duplicate group that DOES carry portal document ids, **When** the period is
   scraped, **Then** no fallback note is recorded for that group (it used the portal discriminator).

---

### User Story 3 - Natural-key id drift on re-scrape is detected and surfaced (Priority: P3)

On a re-scrape, the scraper detects entries whose id is newly minted while an entry with the same
natural key already existed in storage under a different id — i.e. the id moved. This drift is
surfaced as a finding (row deletions/movements are a fraud signal, consistent with the existing
re-scrape reconciliation) so an operator can review it.

**Why this priority**: Cheap insurance per the issue's suggestion #3. It catches any residual
fragility (or genuine portal mutation) that the discriminator alone cannot prevent — e.g. the
no-portal-id fallback rows. It pairs with the existing re-scrape reconciliation pass.

**Independent Test**: Seed storage with a duplicate-natural-key entry that has no portal id, then
re-scrape the period with the duplicate rows reordered so the fallback index reassigns ids; confirm
a drift finding is surfaced for the period.

**Acceptance Scenarios**:

1. **Given** an entry already in storage, **When** a re-scrape mints a new id for a row whose
   natural key already existed under a different id, **Then** a drift finding is recorded for the
   period with the affected ids as evidence.
2. **Given** a re-scrape that reproduces every existing id exactly, **When** the drift check runs,
   **Then** no drift finding is recorded.

---

### Edge Cases

- **Duplicate natural key where the duplicates share the SAME single portal document id** (a true
  line-item split of one invoice across rows): the portal id alone does not disambiguate them, so
  the occurrence index must still disambiguate WITHIN that portal-id group, and a fallback note is
  recorded. The id stays as deterministic as the portal data allows.
- **An entry with several portal document ids**: the discriminator is derived from the full set in
  a stable, order-independent way (sorting/normalizing the set) so the multi-doc value does not
  itself depend on link order in the source.
- **Existing stored entries minted under the old derivation**: a re-scrape will re-mint the ids of
  *duplicate* doc-bearing entries (their discriminator changes). This is the intended, self-healing
  path — the existing authoritative re-scrape reconciliation hard-deletes vanished ids and
  cascade-cleans their dependents, and the global document rebuild re-links. Unique (non-duplicate)
  entries keep their existing ids, so the churn is bounded to the rare duplicate-doc rows.
- **First scrape of a period** (nothing in storage): the drift check finds no prior natural keys
  and records nothing.
- **A row whose amount failed to parse** (skipped before id assignment): unaffected — it never
  reaches id derivation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST derive an entry's id such that, for two or more entries sharing an
  identical natural key, the disambiguating component prefers a portal-native discriminator derived
  from the entry's portal document reference(s) when one is available, rather than the order in
  which the rows appeared in the source.
- **FR-002**: The portal-native discriminator MUST be computed from the entry's portal document
  reference set in an order-independent way, so that the same set of references yields the same
  discriminator regardless of the order the references appeared in the source.
- **FR-003**: When no portal-native discriminator is available for a duplicate natural key (no
  portal document reference, or duplicates that share the identical reference set), the system MUST
  fall back to an occurrence-index discriminator to keep ids unique within the period.
- **FR-004**: An entry whose natural key is unique within the period MUST keep the same id it
  received under the previous derivation (no id change for the non-duplicate common case).
- **FR-005**: When the occurrence-index fallback is used for a duplicate natural key, the system
  MUST record a log/note identifying the period, the natural key, and the duplicate count, so the
  fragile cases are enumerable. Groups disambiguated by a portal discriminator MUST NOT produce a
  fallback note.
- **FR-006**: On a re-scrape of a period, the system MUST detect entries whose id is newly minted
  while an entry with the same natural key already existed in storage under a different id, and
  surface that drift as a finding for the period (with the affected ids as evidence). A re-scrape
  that reproduces every existing id MUST surface no drift finding.
- **FR-007**: All entry ids MUST remain deterministic — the same scraped period (with the same
  portal references) produces byte-identical ids on every run, independent of row order — and MUST
  remain unique within a period.
- **FR-008**: The change MUST NOT alter any non-entry deterministic id derivation, the entries
  mirror schema, or the meaning of the existing natural-key fields; entries remain an exact mirror
  of the portal.

### Key Entities *(include if feature involves data)*

- **Entry**: one ledger line mirrored from the portal. Identified by a deterministic id derived
  from its natural key (date, description, amount, subcategory) plus a disambiguating component.
  May reference zero or more portal documents.
- **Natural key**: the tuple (date, description, amount, subcategory) shared by genuinely identical
  ledger lines.
- **Portal-native discriminator**: a stable value derived from an entry's portal document
  reference set, used to disambiguate duplicate natural keys without depending on row order.
- **Occurrence index**: the order-dependent fallback discriminator, used only when no portal-native
  discriminator distinguishes the duplicates.
- **Id-drift finding**: a per-period record surfaced on re-scrape when a natural key's id moved.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of duplicate-natural-key entries whose duplicates carry distinct portal
  document references, scraping the period in two different row orders produces identical entry ids
  per ledger line.
- **SC-002**: 100% of entries with a unique natural key keep the exact id the previous derivation
  produced (zero id churn for the non-duplicate case).
- **SC-003**: 100% of occurrence-index fallback uses are recorded in the run log/notes with the
  period and natural key; 0% of portal-discriminated groups produce a fallback note.
- **SC-004**: A re-scrape that moves a natural key's id surfaces exactly one drift finding for that
  period; a re-scrape that reproduces every id surfaces zero.
- **SC-005**: Entry-id derivation remains fully deterministic and order-independent for the
  portal-discriminated case, verified by an automated test that derives ids for the same rows in
  multiple orders and asserts equality.

## Assumptions

- **Portal-native discriminator source**: The entry's portal document id set (the `/ViewDocuments/`
  ids already extracted as the entry's document references) is the portal-native identifier. There
  is no per-row source element id exposed by the portal that is more granular, so the document id
  set is the best available portal-native key. (Issue suggestion #1.)
- **Backward-compatibility scope**: Re-minting the ids of *duplicate, doc-bearing* entries on the
  next re-scrape is acceptable and intended — it is exactly the order-fragile set the issue wants
  to stabilize, and the existing authoritative re-scrape reconciliation + global document rebuild
  self-heal the dependents. Unique entries' ids are deliberately preserved to keep the change
  bounded. No data migration is performed; correction happens on the next re-scrape.
- **Drift finding surfacing**: The drift finding is surfaced through the existing per-period
  findings/notes channel used by the other scrape-time consistency checks (so no new storage schema
  or dashboard work is required). It is informational/monitoring, consistent with the existing
  reconciliation philosophy that row movements are evidence to review, and it does not make the
  scrape run fail.
- **Tolerance/identity of "same natural key"**: Two entries share a natural key when their
  (date, description, amount, subcategory) tuple is byte-equal, matching the existing duplicate-
  detection used for the occurrence index.
- **No new dependencies**: The work reuses the existing deterministic-id, logging, and per-period
  notes mechanisms; it adds no new runtime dependency, storage table, or migration.
