# Phase 1 Data Model: Dark theme

This feature persists no server-side data — no D1 table, no migration, no API. The only persisted state is a single browser-local preference owned by `next-themes`.

## Entity: Theme preference (client/browser-local)

| Field | Type | Values | Storage | Notes |
|-------|------|--------|---------|-------|
| theme | string | `"light"` \| `"dark"` \| `"system"` | `localStorage["theme"]` (next-themes default key) | The user's chosen mode. Absent on first visit → resolves to `system` (FR-005). An unrecognized stored value is treated as no preference → falls back to `system`/light (edge case). |

### Derived (not stored)

| Derived value | Source | Notes |
|---------------|--------|-------|
| resolvedTheme | next-themes `useTheme().resolvedTheme` | `"light"` or `"dark"` — the concrete palette actually applied. When `theme === "system"`, this reflects the OS `prefers-color-scheme` and updates live (FR-007). Drives the `.dark` class on `<html>`. |

### Lifecycle / state transitions

- **First visit** (no `localStorage["theme"]`): effective mode = `system`; `.dark` class follows OS preference.
- **User selects a mode**: `theme` written to `localStorage`; `.dark` class applied immediately (FR-003); persists across reload/navigation/return visit (FR-004).
- **System mode + OS preference changes**: `resolvedTheme` flips, `.dark` class updates, no user action (FR-007).
- **Corrupt/unknown stored value**: next-themes ignores it; effective mode = default (`system`).

### Validation rules

- Only the three enumerated values are settable through the toggle (the menu offers exactly Light/Dark/System).
- No server validation — the value never leaves the browser (A2/A8).
