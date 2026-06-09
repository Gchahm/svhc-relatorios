# Research: Merge Document Analyses into the Entries page

No open `NEEDS CLARIFICATION` markers — the three high-impact scope decisions were resolved during specify (see spec Clarifications). This file records the design decisions that shape the implementation.

## Decision 1 — How analyses reach the period-scoped page

**Decision**: Add an **optional `?period=` query parameter** to the existing `GET /api/document-analyses`. When present, scope the result to analyses whose entry belongs to that period (join `entries.reportId → accountability_reports.period`). `EntriesClient` fetches `/api/entries?period=P` and `/api/document-analyses?period=P` together and joins them client-side by `entryId`.

**Rationale**:
- The detail dialog already consumes the exact `DocAnalysisRow` shape returned by this endpoint and self-fetches its records/pages by `analysisId` — reusing the endpoint means zero changes to the dialog's data contract.
- Adding one optional filter is simpler than introducing a new endpoint or denormalizing analysis columns into `/api/entries` (which would force reconstructing the `DocAnalysisRow` shape and duplicate the join logic).
- Backwards compatible: with no `period`, the endpoint behaves exactly as today (the redirect-era callers and any other consumer are unaffected).

**Alternatives considered**:
- *Extend `/api/entries` with a LEFT JOIN to `document_analyses`*: rejected — would mix two concerns into one row shape and require rebuilding the dialog's expected object; more churn, more risk to the existing Entries contract.
- *Fetch all analyses (no period) and filter client-side*: rejected — ships every period's analyses to scope one period; wasteful and contradicts FR-012's period scoping.

## Decision 2 — Joining analyses to entries (one row per entry)

**Decision**: Build `Map<string, DocAnalysisRow>` keyed by `entryId`, keeping the **latest** analysis per entry (the endpoint already orders by `analyzedAt DESC`, so first-seen wins). Entry rows look up their analysis by `String(entry.id)`.

**Rationale**: An entry's merged row reflects a single rolled-up match status (spec edge cases). The endpoint's existing ordering gives a deterministic "latest" without extra sorting. Shared-NF siblings each have their own entry and therefore their own row/status — no collapsing.

**Alternatives considered**:
- *Show every analysis as its own row even when sharing an entry*: rejected — breaks the "Entries page is the organizing unit" model and would duplicate ledger rows.

## Decision 3 — Where the shared detail components live

**Decision**: Move `DocumentAnalysisDetailDialog.tsx` and `PageImageViewer.tsx` into `src/app/dashboard/entries/`. Redefine and export the `DocAnalysisRow` type from `EntriesClient.tsx` (the dialog imports it from there). Delete `DocumentAnalysesClient.tsx`. Replace `document-analyses/page.tsx` with a server redirect.

**Rationale**: After the merge the only consumer of the dialog is the Entries page; co-locating avoids an awkward cross-folder import into a folder that is otherwise just a redirect. Keeps the `document-analyses/` folder minimal (one redirect file).

**Alternatives considered**:
- *Keep components in `document-analyses/` and import across folders*: rejected — leaves dead-feeling client code beside a redirect and an inverted dependency (the live page importing from the retired one).
- *Create a new `components/` subfolder for them*: rejected (YAGNI) — single consumer; co-location is simpler.

## Decision 4 — Old route handling

**Decision**: `document-analyses/page.tsx` becomes a server component that calls `redirect("/dashboard/entries")` (`next/navigation`). The "Docs" `NavLink` is removed from `dashboard/layout.tsx` (and the now-unused `FileSearch` import dropped).

**Rationale**: A server redirect satisfies FR-013 (old links keep working) with no client flash; the redirect target is inside the same auth-gated layout, so no new auth surface. Removing the nav item satisfies FR-014.

## Decision 5 — Inline surfacing without breaking virtualization

**Decision**: Reuse the existing `MatchBadge` pattern (compact `[10px]` badges) as additional fixed-width columns on the entries virtual rows; only render badges when an analysis exists for the entry (otherwise neutral em-dash / blank). Keep the `@tanstack/react-virtual` setup; adjust `estimateSize` only if row height changes.

**Rationale**: Preserves SC-006 (smooth scrolling). Fixed-width columns keep the virtualized flrow layout stable. No per-row data fetching (the analysis map is built once after both fetches resolve).

## Decision 6 — Document-health summary scope

**Decision**: Compute the period summary (counts of amount/vendor/date mismatches and analysis errors) from the period-scoped analyses currently loaded, mirroring the standalone page's `summary` memo but over the period subset.

**Rationale**: Satisfies FR-010 and SC-005 (counts equal the previous page's counts for that period because they read the same rows, just period-filtered).
