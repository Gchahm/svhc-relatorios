# Feature Specification: I18N-001 Localization Foundation

**Feature Branch**: `039-i18n-foundation`  
**Created**: 2026-06-12  
**Status**: Draft  
**Input**: User description: "I18N-001: Localization foundation — locale infrastructure with pt-BR as the default, typed message catalog, shared locale-aware formatters, localizable alert-type labels, one reference surface wired end-to-end"

## Context

The app is a fiscal auditing tool for a Brazilian condominium (SVHC) whose users read Portuguese, yet every UI string is hardcoded English (`"Select period"`, `"Search description..."`, page titles, badges, button labels) and the root layout declares `<html lang="en">`. Meanwhile number/currency/date formatting is already pt-BR — copy-pasted into ~12 client components — creating inconsistency and incompleteness.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Administrator views localized UI in pt-BR (Priority: P1)

An administrator opens the dashboard and all UI text appears in Portuguese (pt-BR), not English. Labels, buttons, placeholders, page titles, badge text, and alert descriptions are all in Portuguese.

**Why this priority**: This is the foundation value. The app serves a Portuguese-speaking user base; displaying their native language is the primary user-facing outcome of localization.

**Independent Test**: Deploy the localized build, navigate to the dashboard, and verify that all user-facing text strings are in Portuguese. No English strings should be visible unless intentionally untranslated.

**Acceptance Scenarios**:

1. **Given** a user with no locale preference, **When** they access the app, **Then** the page renders with pt-BR locale and the `<html lang>` attribute is `"pt-BR"`
2. **Given** the Entries page is loaded, **When** a user views the table headers, buttons, and dialogs, **Then** all text is in Portuguese
3. **Given** the Alerts page is loaded, **When** a user views alert type labels (e.g., `"attachment_amount_mismatch"`), **Then** they see localized, human-readable Portuguese labels (e.g., `"Divergência de Valor"`)
4. **Given** the app displays a number, date, or currency value, **When** the user views it, **Then** it is formatted according to pt-BR conventions (e.g., `"R$ 1.234,56"` for currency, `"12/06/2026"` for dates)

---

### User Story 2 - Developer adds a new UI string using the typed message catalog (Priority: P1)

A developer working on a new feature needs to display a message (e.g., "No data available"). Instead of hardcoding English text, they import the message catalog, call a translation function with a typed key, and the text resolves to Portuguese.

**Why this priority**: This is the foundation for all future localization work. Without a typed, discoverable catalog and resolution mechanism, developers will revert to hardcoding strings.

**Independent Test**: A new feature can be built using only catalog keys, with no hardcoded English strings. TypeScript catches missing keys at build/test time.

**Acceptance Scenarios**:

1. **Given** a developer wants to display a message in a component, **When** they import the message catalog and use a catalog key, **Then** TypeScript validates the key exists and the message resolves to the correct Portuguese text
2. **Given** a developer mistypes a catalog key, **When** they attempt to build the project, **Then** TypeScript raises a type error preventing the build
3. **Given** the catalog is extended with new keys (e.g., for a new feature), **When** the developer runs tests, **Then** a test verifies that every key in pt-BR is present and no orphan keys exist

---

### User Story 3 - Alert type labels render as localized text in the UI (Priority: P1)

When the dashboard displays an alert (e.g., type `"attachment_amount_mismatch"`), the alert badge/label shows a human-readable, localized string (e.g., `"Divergência de Valor"`) instead of the machine key.

**Why this priority**: Alerts are a critical user-facing feature (feature 018). Labels must be localized alongside the rest of the UI for consistency and usability.

**Independent Test**: Trigger or display an alert, and verify that its type label is rendered in Portuguese and comes from the localized catalog.

**Acceptance Scenarios**:

1. **Given** an alert of type `"attachment_amount_mismatch"` is displayed, **When** the label is rendered, **Then** it shows `"Divergência de Valor"` in Portuguese
2. **Given** multiple alert types on the Alerts page, **When** the page renders, **Then** all alert type labels are localized via the catalog
3. **Given** a new alert type is added to the system, **When** the developer adds its label to the catalog, **Then** it renders automatically without code changes to the alert display logic

---

### User Story 4 - Reference surface (e.g., nav or sign-in page) is fully localized end-to-end (Priority: P2)

The dashboard navbar and sign-in page are fully localized as the reference example for future features. All text, labels, buttons, and error messages are in Portuguese.

**Why this priority**: Provides a concrete, tested example that other features can follow. Demonstrates the complete flow: locale resolution → catalog lookup → rendering.

**Independent Test**: Navigate the sign-in flow and dashboard navigation, and verify all text is localized. Can serve as a code example for other features.

**Acceptance Scenarios**:

1. **Given** the sign-in page loads, **When** no user is authenticated, **Then** all text (button labels, placeholders, error messages) is in Portuguese
2. **Given** a user is logged in and on the dashboard, **When** they view the navigation bar, **Then** all labels are in Portuguese
3. **Given** the development team reviews the nav and sign-in components, **When** they examine the code, **Then** they see a clear example of how to use the catalog API in both server and client components

### Edge Cases

- **Missing catalog entry**: If a developer references a catalog key that doesn't exist in pt-BR, the build/test should fail, not silently fall back to English or a key name.
- **New locale added later**: The infrastructure must not assume pt-BR is the only locale. Adding `en` or another locale should not require architectural changes.
- **Server vs. client locale resolution**: Server components and client components must both be able to resolve the active locale and translate without redundant logic.
- **Cloudflare Workers edge runtime**: The locale resolution and catalog lookup must work on Cloudflare Workers (Edge Runtime); no Node.js-only APIs.
- **Formatting helpers**: Existing formatting helpers (currency, date, percent) that are currently hardcoded with `"pt-BR"` must be centralized and derive locale from the i18n layer, so they remain consistent if locale handling changes.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: System MUST provide a typed message catalog with Portuguese (pt-BR) as the canonical, complete translation and English (en) as an optional, secondary translation.
- **FR-002**: The message catalog MUST include all hardcoded UI strings from the dashboard, including page titles, button labels, form placeholders, page headers, section labels, and badge/label text.
- **FR-003**: The message catalog MUST include localized labels for all alert types defined in `ALERT_TYPE_LABELS` (feature 038), with a mapping from machine key (e.g., `"attachment_amount_mismatch"`) to human-readable Portuguese text.
- **FR-004**: System MUST provide a server-side way to resolve the active locale and translate keys in both server and client components (e.g., a `getLocale()` function and a `t(key)` function).
- **FR-005**: System MUST provide a client-side way to resolve the active locale and translate keys in client components.
- **FR-006**: The active locale MUST default to `pt-BR` when no user preference exists.
- **FR-007**: System MUST ensure that `<html lang>` attribute in the root layout reflects the active locale (default: `"pt-BR"`).
- **FR-008**: System MUST centralize all number, currency, date, and percentage formatting helpers into a single module that derives its locale from the i18n layer, replacing scattered hardcoded `toLocaleString("pt-BR", ...)` calls.
- **FR-009**: TypeScript MUST validate that all catalog keys are typed; referencing a non-existent key MUST result in a type error.
- **FR-010**: The system MUST include a unit test that verifies every key present in the pt-BR catalog is represented and no orphan keys exist.
- **FR-011**: The catalog structure MUST be compatible with Cloudflare Workers / Edge Runtime; no Node.js-only APIs.
- **FR-012**: The sign-in page and dashboard navigation (nav bar) MUST be fully localized as the reference example, with all text coming from the catalog.

### Key Entities

- **Message Catalog**: A typed dictionary mapping keys (e.g., `"nav.home"`, `"button.submit"`, `"alert.attachment_amount_mismatch"`) to Portuguese strings. Optionally extended with English translations.
- **Locale**: A language code (e.g., `"pt-BR"`, `"en"`) representing the active user locale. Defaults to `"pt-BR"`.
- **Translation Function**: A function (e.g., `t(key)` or `useTranslation()` hook) that resolves the active locale and returns the translated string for a given key.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: All user-facing text on the dashboard (headers, buttons, labels, dialogs, badges, placeholders) is rendered in Portuguese with no English strings visible.
- **SC-002**: TypeScript build fails if a catalog key is missing from pt-BR or if a developer references a non-existent key.
- **SC-003**: All alert type labels in the app are localized via the catalog (100% of alert types have pt-BR labels defined).
- **SC-004**: The sign-in page and dashboard navigation are fully localized, with all text sourced from the catalog and serving as a reference example for future features.
- **SC-005**: A unit test suite verifies catalog completeness (every pt-BR key is defined, no orphan keys) and runs as part of the CI pipeline.
- **SC-006**: Currency, date, and number formatting helpers are centralized in a single module, used across all dashboard components, and derive locale from the i18n layer (not hardcoded strings).
- **SC-007**: The active locale (default: pt-BR) is correctly reflected in the `<html lang>` attribute on page load and any subsequent locale changes.

## Assumptions

1. **Single-tenant, internal tool**: The app serves a single organization with Portuguese-speaking users. English is optional; no need for user-facing locale switcher in this foundation feature.
2. **No routing-based locales**: Non-routed locale (e.g., a context or server context variable) is acceptable; no need for `/pt-BR/...` URL structure.
3. **pt-BR is canonical**: pt-BR is the complete, authoritative catalog. English translations may be partial or added later.
4. **Typesafety over runtime fallback**: Missing keys should fail at build/test time, not silently fall back to key names or English.
5. **Shared infrastructure**: The i18n layer is foundational; future features (I18N-002, I18N-003, I18N-004) will depend on it.
6. **No new dependencies**: Homegrown typed-dictionary approach preferred over `next-intl` or similar, consistent with the project's no-new-dependencies culture.
7. **Locale resolution at request time**: Server components resolve locale via `getLocale()` (reading from Cloudflare context, cookies, or defaults). Client components use a context or hook. Both share the same catalog.
8. **Formatting helpers centralized**: Existing scattered `toLocaleString("pt-BR", ...)` calls in client components are replaced with calls to centralized helpers that derive locale from the i18n layer.

## Out of Scope

- User-facing locale switcher or cookie persistence (possible in I18N-002 or later).
- Python pipeline localization (this is presentation-layer only; alerts are surfaced with machine keys, rendered with localized labels in the UI).
- Migration of historical data or API responses (all string localization is client/server-side rendering; no schema or data changes).
- Support for locales beyond English (en); pt-BR is the foundation.
