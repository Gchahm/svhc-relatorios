# Feature Specification: Dark theme — switchable light/dark/system mode with persisted preference

**Feature Branch**: `047-dark-theme`
**Created**: 2026-06-13
**Status**: Draft
**Input**: User description: "Dark theme: add next-themes provider to layout, toggle control in dashboard shell header (sun/moon icon), persist choice to localStorage, default to system mode, audit dashboard for hardcoded colors, integrate i18n labels (Tema/Claro/Escuro/Sistema pt-BR)"

## Clarifications

### Session 2026-06-13

Running unattended (one-shot pipeline), no interactive questions were asked; the decisions below were resolved by documented assumption rather than by querying the user. They are recorded here because they materially shaped the requirements and acceptance.

- Q: How should semantic status colors (red/green/yellow/blue/amber badges and text) behave in dark mode — recolor to tokens, or keep hue with a dark variant? → A: Keep hue, add a dark-mode variant so each stays legible on a dark background (per A6). Structural grays that stand in for theme tokens are migrated to tokens instead.
- Q: What is the toggle control's shape — a single cycling icon button, or a menu with explicit modes? → A: A compact sun/moon icon button opening a small menu offering Light / Dark / System, matching the adjacent user-menu pattern, so System is discoverable (per A4).
- Q: Is the theme preference stored per-browser or synced to the user's account? → A: Per-browser only (next-themes localStorage default); no server-side/account state, no D1 schema (per A2/A8).
- Q: Do the auth (sign-in/sign-up) pages get the toggle control, given it lives in the dashboard header? → A: No control on the auth pages, but they still honor the persisted theme via the root-level provider, and must render legibly in dark mode (FR-009).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Switch between light, dark, and system themes (Priority: P1)

A logged-in user opens the dashboard and finds a clearly visible theme control in the shell header. They can switch the entire application's appearance between a light theme, a dark theme, and a "follow my device" (system) mode. The change is applied immediately to the page they are looking at.

**Why this priority**: This is the core deliverable — without a usable switch that flips the application appearance, the feature delivers no value. Everything else (persistence, audit) builds on it.

**Independent Test**: Open the dashboard, click the theme control, choose "Dark" — the page repaints in the dark palette without a reload. Choose "Light" — it repaints light. Choose "System" — it matches the device's current OS preference.

**Acceptance Scenarios**:

1. **Given** the dashboard is open in light mode, **When** the user selects "Dark" from the theme control, **Then** the whole application repaints with the dark palette immediately (no page reload).
2. **Given** the dashboard is open, **When** the user selects "System", **Then** the application matches the operating system's current light/dark preference.
3. **Given** the device's OS preference changes (e.g. the OS switches to dark at night) while "System" is selected, **When** the user is viewing the app, **Then** the application follows the new OS preference.

---

### User Story 2 - Preference persists across reloads and visits (Priority: P1)

After choosing a theme, the user's choice survives a page reload, navigation, and a return visit in the same browser, so they are never forced to re-pick their theme.

**Why this priority**: A theme switch that resets on every reload is effectively unusable; persistence is part of the minimum viable feature, not a nice-to-have.

**Independent Test**: Choose "Dark", reload the page — it loads dark. Navigate to another dashboard page — still dark. Close and reopen the tab — still dark.

**Acceptance Scenarios**:

1. **Given** the user has selected "Dark", **When** they reload the page, **Then** it loads in dark mode with no flash of the light theme first.
2. **Given** the user has selected an explicit theme, **When** they navigate between dashboard pages, **Then** the theme stays consistent.
3. **Given** a first-time visitor who has never chosen a theme, **When** they load the app, **Then** it defaults to following the device (system) preference.

---

### User Story 3 - Every surface is legible in dark mode (Priority: P2)

In dark mode, every dashboard surface a user can reach — list pages, detail pages, dialogs, alert/status badges, the shell header and navigation, and the sign-in/sign-up pages — renders legibly, with no white-on-white, black-on-black, or fixed-color regions that ignore the theme.

**Why this priority**: A switch that leaves half the app unreadable is a poor experience, but it depends on Story 1 existing first. It is the polish that makes the feature trustworthy.

**Independent Test**: With dark mode active, visit each dashboard list page, open a detail page, open an attachment/document/alert dialog, and view the sign-in page — confirm all text and surfaces have legible contrast and no element retains a light-only background or color.

**Acceptance Scenarios**:

1. **Given** dark mode is active, **When** the user visits any dashboard list page, detail page, or dialog, **Then** backgrounds, text, borders, and badges adapt to the dark palette and remain legible.
2. **Given** dark mode is active, **When** the user views a status or alert badge (e.g. over/within/under, severity levels), **Then** the badge color and its text remain legible in dark mode.
3. **Given** dark mode is active, **When** the user views the sign-in / sign-up pages, **Then** they render legibly in the dark palette.

---

### User Story 4 - Localized theme labels (Priority: P3)

All labels and options in the theme control are presented in the application's localized language (pt-BR by default: "Tema", "Claro", "Escuro", "Sistema"), consistent with the rest of the localized interface.

**Why this priority**: Consistency with the localization track; it is required for acceptance but is a small, low-risk addition on top of the working control.

**Independent Test**: Open the theme control with the default (pt-BR) locale and confirm the control's name and its three options read "Tema", "Claro", "Escuro", "Sistema" — no raw English.

**Acceptance Scenarios**:

1. **Given** the default locale, **When** the user opens the theme control, **Then** its accessible name/label and the three mode options are shown in pt-BR ("Tema", "Claro", "Escuro", "Sistema").
2. **Given** the catalog-completeness check runs, **When** the new theme keys are present, **Then** the check passes (every key defined in the catalog shape has a value).

---

### Edge Cases

- **First visit / no stored preference**: defaults to system mode (follow OS).
- **Stored preference is corrupt or unrecognized**: treated as if no preference was stored — falls back to system mode rather than erroring.
- **OS preference unavailable / not reported by the browser**: system mode falls back to the light palette.
- **JavaScript not yet hydrated on first paint**: the persisted/system theme is applied before first paint so there is no flash of the wrong theme.
- **Pages outside the dashboard shell** (sign-in/sign-up): still honor the persisted theme even though the toggle control lives in the dashboard header.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support three theme modes — light, dark, and system (follow the device's OS preference) — and apply the selected mode to the entire application.
- **FR-002**: The system MUST provide a visible theme control in the dashboard shell header, presented as a sun/moon style icon control with selectable light / dark / system options, placed alongside the existing header chrome.
- **FR-003**: Selecting a theme MUST take effect immediately on the current page without requiring a reload.
- **FR-004**: The system MUST persist the user's chosen theme in the browser so it survives reloads, in-app navigation, and return visits in the same browser.
- **FR-005**: On a first visit with no stored preference (or an unrecognized stored value), the system MUST default to system mode.
- **FR-006**: The system MUST apply the resolved theme before first paint so there is no visible flash of the wrong theme on initial load.
- **FR-007**: While system mode is selected, the system MUST track changes to the device's OS light/dark preference and update the appearance accordingly.
- **FR-008**: Every dashboard surface — list pages, detail pages, dialogs, status/alert badges, the shell header and navigation — MUST adapt to the active theme and remain legible in dark mode; no element may retain a fixed light-only background, text color, or border that ignores the theme.
- **FR-009**: The sign-in and sign-up pages MUST render legibly under the persisted theme.
- **FR-010**: All labels and options of the theme control MUST be drawn from the localization catalog (pt-BR default: "Tema", "Claro", "Escuro", "Sistema"); no raw English literals.
- **FR-011**: The localization catalog-completeness check MUST continue to pass with the new theme keys present.

### Key Entities *(include if feature involves data)*

- **Theme preference**: the user's selected mode — one of `light`, `dark`, `system`. Stored per browser. Not associated with the user's server-side account; it is a client/browser-local presentation preference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can switch the application between light, dark, and system appearance using a single visible control in fewer than 3 interactions.
- **SC-002**: 100% of the time, a chosen theme is still in effect after a page reload and after reopening the tab in the same browser.
- **SC-003**: On initial load, there is no visible flash of the opposite theme (the resolved theme is shown from the first painted frame).
- **SC-004**: Across the dashboard list pages, detail pages, dialogs, badges, header, and the sign-in/sign-up pages, 0 surfaces are illegible in dark mode (no white-on-white, black-on-black, or fixed light-only region).
- **SC-005**: 100% of the theme control's visible labels are localized (pt-BR by default), with 0 raw English literals.
- **SC-006**: Existing automated quality gates (lint, formatting, catalog-completeness, existing tests) pass with the change applied.

## Assumptions

- **A1 — Library**: The implementation uses `next-themes` (the standard shadcn/ui approach) for theme state, persistence, and OS-preference tracking. This is the one new npm dependency the issue explicitly anticipates.
- **A2 — Persistence mechanism**: Persistence is browser-local via `next-themes`' default `localStorage` storage (the user's choice is browser-local, not synced to their account). No D1 schema, migration, API route, or server-side state is added.
- **A3 — Default mode**: First-visit default is `system`; the supported stored values are exactly `light`, `dark`, `system`.
- **A4 — Toggle control shape**: The header control is a compact icon button (sun/moon) that opens a small menu offering Light / Dark / System, matching the existing header's dropdown-menu pattern (consistent with the adjacent user menu). A simple cycling icon button would also satisfy the issue, but the menu makes the three explicit modes (including System) discoverable, which the acceptance criteria require.
- **A5 — Palette source**: Dark colors come from the existing `.dark` CSS-variable palette already defined in the global stylesheet and the `class`-based dark mode already configured in the Tailwind config; no palette redesign is in scope. The audit's job is to route stragglers to the existing token system (`bg-background`, `text-foreground`, `border`, `bg-muted`, `text-muted-foreground`, etc.) or add `dark:` variants to semantic status colors.
- **A6 — Hardcoded-color audit scope**: The audit covers all reachable dashboard surfaces plus the shell and the auth pages. Structural grays that stand in for theme tokens (e.g. header dividers, nav-link text/hover, user-menu text) are migrated to tokens; semantic status colors (red/green/yellow/blue/amber badges and text) keep their hue but gain a dark-mode variant so they stay legible on a dark background. Chart and data-visualization palettes already have dark CSS-variable values and are out of scope beyond confirming they read those tokens.
- **A7 — Flash avoidance**: The root document element opts into the framework's hydration-warning suppression so the pre-paint theme class injected by the theme library does not trigger a hydration mismatch, and the resolved theme is present before first paint.
- **A8 — No behavioral/data change**: This is a presentation-layer feature. It reads no data, writes no data, adds no D1 schema/migration, and changes no API contract. Server components keep rendering server-side; the theme control and provider are client components.
- **A9 — Locale coupling**: The control's labels go through the existing localization catalog used elsewhere in the app; new keys (theme name + three mode labels) are added to the canonical pt-BR catalog (and the optional en fallback) under a `theme` namespace.

## Dependencies

- Localization foundation (I18N-001, issue #64) — provides the catalog and translation hook the theme control's labels go through. Already present in the codebase.
- One new npm dependency: `next-themes`.
