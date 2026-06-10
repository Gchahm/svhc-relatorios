# Contract: Entries deep link

## URL

```
/dashboard/entries?period=<YYYY-MM>&entry=<entryId>
```

- `period` (required for the deep link to act) — selects the period; entries + analyses for
  it are fetched as usual.
- `entry` (optional) — the entry id (UUID string) to focus. When present and resolvable, the
  attachment-analysis detail dialog auto-opens for that entry.

## Behavior (`EntriesClient`)

1. On first mount, read `period` / `entry` from the URL.
2. If `period` is present, set it as the selected period (overrides the default
   current-month). If absent, default behavior is unchanged.
3. After that period's entries **and** analyses have loaded:
   - Scroll the matching entry row into view (centered) and apply a transient highlight.
   - If `analysisByEntry.get(entry)` resolves, open the detail dialog for it.
   - If the entry exists but has no analysis, scroll/highlight only (no dialog) — no error
     (FR-008).
   - If the entry id matches nothing in the period, no-op (no crash) — stale link (edge case).
4. The deep-link effect runs **once** per (period, entry) param set; manual period changes or
   closing the dialog do not re-trigger it. Closing the dialog leaves the period and row
   selection intact (US1.3).

## Producer (`AlertsClient`)

For each alert, `affectedEntryIds = metadata.entry_ids ?? (metadata.entry_id ? [metadata.entry_id] : [])`.
Each id becomes a link `?period=<alert.referencePeriod>&entry=<id>`:
- 0 ids → render no link.
- 1 id → a single inline link.
- >1 ids → a popover listing one link per id.

Link clicks `stopPropagation()` so they don't toggle the alert's resolved state.
