# Research: Actionable Alerts

All "unknowns" here are codebase-grounded decisions, not external research. Each is a
**Decision / Rationale / Alternatives** triplet derived from reading the current code.

## R1. Single source of truth for per-attachment mismatch detection (FR-004)

**Decision**: Extract a new stdlib-only module `scripts/analysis/mismatches.py` exposing
`detect_attachment_mismatches(period: PeriodData, refs: RefIndex) -> list[AttachmentMismatch]`.
Rewrite `extractions.summarize_mismatches` to build its per-attachment rows from this
function, and have the new `checks/attachments.py:check_attachment_mismatches` call the same
function.

**Rationale**: `summarize_mismatches` currently inlines the amount/vendor/date/page-error
detection by reading the persisted `attachment_analyses` match flags (`amount_match`,
`vendor_match`, `date_match`, `error`). The check must agree with it exactly (SC-004). One
function read by both guarantees that. A new module avoids an import cycle: `extractions.py`
already imports from `.attachments`/`.images`/`.loader`/`.page_classifications`, and
`checks/*` import from `..models`/`..attachments`/`..nf_groups`; the new module imports only
the model/ref types, so both can import it cleanly.

**Alternatives considered**:
- *Check imports from `extractions.py`*: rejected — `extractions` pulls in the image
  materialization / loader machinery and risks a cycle through `checks`; the check only needs
  the pure detector.
- *Duplicate the detection in the check*: rejected — exactly the drift FR-004 forbids.

## R2. Reconciliation already encoded in the persisted match flags (FR-012)

**Decision**: Read mismatches from the persisted `attachment_analyses.amount_match` /
`vendor_match` / `date_match` / `error` — do not recompute reconciliation in the check.

**Rationale**: `apply_extractions` already applies shared-NF group reconciliation via
`_apply_group_amount_match` (and per-entry comparison for singletons) when it writes
`attachment_analyses`. So a split that reconciles within tolerance has `amount_match = 1`
persisted and yields no amount mismatch — FR-012 holds for free, and the detector stays a
thin read. (The `duplicate_billing` over-claim alert remains a separate, existing check.)

**Alternatives considered**: recomputing reconciliation in the check — rejected as redundant
and a second place to drift.

## R3. Alert type granularity and idempotent id (FR-014, FR-003)

**Decision**: One alert per (attachment, kind) using a **distinct `type` per kind** —
`attachment_amount_mismatch`, `attachment_vendor_mismatch`, `attachment_date_mismatch`,
`attachment_page_error` — with `discriminator = attachment_id`. Id =
`det_id("alert", period, type, attachment_id)` (matches the existing `_alert(...)` helper).

**Rationale**: The existing alert types are granular and the type column drives the UI Type
filter, so distinct types make the new alerts filterable like the rest. Because the type
already encodes the kind, `attachment_id` alone is a sufficient, stable discriminator → the
id is stable across re-runs (FR-003), and `analyze`'s delete-then-insert per
`reference_period` makes re-runs idempotent. This mirrors `duplicate_billing`
(`discriminator = gkey`).

**Alternatives considered**:
- *Single `attachment_mismatch` type with kind in metadata, discriminator = attachment_id+kind*:
  works for idempotency but loses per-kind filterability in the UI. Rejected.
- *One alert per attachment bundling all kinds*: rejected by the issue (individually
  resolvable wins).

## R4. Severity (FR-010)

**Decision**: `warning` for amount/vendor/date; `info` for page-error.

**Rationale**: Directly from the issue's product-owner suggestion; consistent with existing
`info`-level health alerts (e.g. `large_expense_no_attachment`).

## R5. Deep-link contract & key (FR-007, FR-015)

**Decision**: Link is `/dashboard/entries?period=<YYYY-MM>&entry=<entryId>`. The key is the
**entry id** (a UUID string — `entries.id` is `uuid()`), the same value carried in alert
metadata `entry_id` / `entry_ids` and in `attachment_analyses` join output `entryId`.

**Rationale**: `EntriesClient` already builds `analysisByEntry: Map<entryId, AttachmentAnalysisRow>`
keyed by the analysis `entryId` and looked up with `String(entry.id)`. Resolving the URL's
`entry` to that map yields the exact `AttachmentAnalysisRow` to pass to the detail dialog —
zero new fetch. `entry` is stable/user-facing; one attachment per entry today, so the entry
key resolves the attachment unambiguously.

**Note**: The `Entry` TS interface declares `id: number`, but `entries.id` is a UUID string;
at runtime it is a string and all comparisons use `String(...)`, so the URL string compares
correctly. We will not change the (cosmetic) type in this feature beyond what is needed.

**Alternatives considered**: keying by `attachment_id` — equivalent today but the entries
view is entry-indexed, so entry id is the more direct URL key.

## R6. Auto-open + scroll mechanics in EntriesClient (FR-007, US1.3)

**Decision**: On mount, read `useSearchParams()`. If `period` present and valid, set
`selectedPeriod` to it (overriding the default current-period). After the period's entries +
analyses finish loading, resolve `entry` → `analysisByEntry.get(entryParam)`; if found, call
`setSelectedAnalysis(...)` to auto-open the dialog (the dialog opens when `analysis !== null`).
Also locate the row index in `filtered` and `virtualizer.scrollToIndex(idx, { align: "center" })`,
applying a transient highlight class. Guard so this runs once per (period, entry) param set
(a ref/flag), not on every render. Closing the dialog clears `selectedAnalysis` only (period
and row stay), satisfying US1.3.

**Rationale**: Reuses existing state (`selectedPeriod`, `selectedAnalysis`, `analysisByEntry`,
`virtualizer`) — minimal surface. The "after load" timing is handled by keying the effect on
`loading === false` + the analyses array, since data fetch is async.

**Alternatives considered**: a server-side redirect/prefetch — unnecessary; client already
fetches per-period. A new dialog-by-id route — rejected; dialog already takes the row object.

**Edge (FR-008)**: when `entry` resolves to a real row but has **no** analysis
(`analysisByEntry` miss — e.g. large-expense-without-attachment), still scroll/highlight the
row and skip opening the dialog (there is nothing to show) — no error.

## R7. Rendering affected-entry links in the virtualized alerts table (FR-006, FR-009)

**Decision**: Add an "Entries" column to the alerts table. Compute
`affectedEntryIds(alert)` from parsed metadata. Render:
- 0 ids → `—` (period/category-level alerts, FR-009).
- 1 id → a single inline deep link ("Open ↗").
- >1 ids → a shadcn `Popover` trigger ("N entries") whose content lists one deep link per
  entry id (fully satisfies FR-006 without breaking the fixed virtualized row height).

The link/popover trigger calls `e.stopPropagation()` so it does not fire the row's
resolve-toggle `onClick`.

**Rationale**: The alerts table is virtualized with a fixed row height and a row click that
toggles `resolved`; a popover keeps row height fixed while still listing every entry. `popover`
already exists in `src/components/ui/`. Links use Next `<Link>` (client navigation).

**Alternatives considered**: inline wrapped chips (overflow risk against fixed row height);
expanding rows (complicates the virtualizer). Both rejected for the popover.

## R8. Which alerts expose links, and from which metadata keys (FR-005)

**Decision**: `affectedEntryIds(metadata)` = `metadata.entry_ids` (array) if present, else
`[metadata.entry_id]` if present, else `[]`. This covers:
- New per-attachment mismatch alerts → `entry_id` (single).
- `duplicate_billing` → `entry_ids` (list) + `attachment_ids`.
- `duplicate_entry`, `negative_credit`, `large_expense_no_attachment` → `entry_ids` (list).
- All period/category-level alerts (balance/subtotal/trend/vendor/seasonality/delinquency/
  missing-period/new-vendor) → no entry key → `[]` (no links).

**Rationale**: These are exactly the metadata shapes already written by the Python checks
(verified by reading `consistency.py` / `advanced.py`). No Python change needed to expose
the *existing* entry-level alerts — only the API must stop dropping `metadata`.

## R9. Independence from the improve-loop verdicts (FR-011)

**Decision**: No coupling. Alert `resolved`/`notes` live in the `alerts` D1 table (toggled via
`PATCH /api/alerts/[id]`); loop verdicts live in `<period>.verdicts.json`. The new check writes
alerts through the same delete-then-insert path; it never reads or writes verdicts, and the
loop never reads alert `resolved`. A human resolving an alert does not create a verdict and
vice-versa.

**Rationale**: Confirms the issue's decision point — two independent truth systems, already
physically separate. Re-running `analyze` recomputes alerts (and would clear a human's
`resolved` flag on re-insert) — this is the **existing** behavior of every alert and is out of
scope to change here; noted as a known limitation.
