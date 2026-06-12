# Research: I18N-001 Localization Foundation

**Date**: 2026-06-12 | **Feature**: 039-i18n-foundation

## Overview

All unknowns from the plan's Technical Context have been resolved through requirements analysis and project context review. This feature introduces no architectural or technological unknowns.

## Resolved Decisions

### 1. Typed Message Catalog Structure

**Decision**: Use a nested TypeScript object with `as const` assertion and generic type helpers for strict key validation.

**Rationale**:
- Simplest approach that ensures type safety at build time
- No runtime overhead or external dependencies
- Keys are validated at TypeScript compile time; missing keys cause build errors
- Developers cannot reference non-existent keys without a type error

**Alternatives considered**:
- **JSON files + dynamic import**: Would lose type safety; missing keys only caught at runtime
- **next-intl library**: Adds external dependency; contradicts project's no-new-dependencies culture
- **Simple object without `as const`**: Would allow `any` key access, losing type safety

**Implementation**: See `src/lib/i18n/catalog.ts` in the tasks/implementation phase.

### 2. Locale Resolution: Server vs. Client

**Decision**: Server components use `getLocale()` function; client components use React context + hook.

**Rationale**:
- Server components can access Cloudflare context directly; no need for context
- Client components cannot access context outside React tree, so React context is the idiomatic pattern
- Both share the same catalog and defaulting logic, maintaining consistency
- Works on Cloudflare Workers Edge Runtime (no Node.js-only APIs)

**Alternatives considered**:
- **Routing-based locale** (`/pt-BR/...`): Adds URL complexity; unnecessary for single-tenant internal tool
- **Cookie-based locale only**: Requires client-side handling; not available in server components at request time
- **One unified context**: Client components in `layout.tsx` seeded by server is the correct pattern

**Implementation**: See `src/lib/i18n/server.ts` and `src/lib/i18n/client.tsx` in the tasks/implementation phase.

### 3. Centralized Formatting Helpers

**Decision**: Create `src/lib/i18n/formatters.ts` with `formatCurrency()`, `formatDate()`, `formatPercent()`, `formatNumber()` functions that derive locale from the i18n layer.

**Rationale**:
- Currently ~12 components have scattered `toLocaleString("pt-BR", ...)` calls; this centralizes them
- Ensures all formatting respects the active locale (future-proofs for I18N-002 locale switching)
- Single source of truth for formatting behavior across the app
- Simpler than creating per-component hooks

**Alternatives considered**:
- **Keep scattered calls**: Would require updating all components in future when locale changes; brittle
- **Per-component hooks**: Adds boilerplate; formatting logic is simple enough to centralize
- **Locale-specific variants**: Not needed; one `formatCurrency(amount)` function checks locale internally

**Implementation**: See `src/lib/i18n/formatters.ts` in the tasks/implementation phase.

### 4. Alert Type Labels Localization

**Decision**: Move `ALERT_TYPE_LABELS` from `src/lib/alerts.ts` into the message catalog under `alerts.types.*` keys. Create a helper function `getAlertTypeLabel(type)` that looks up the localized label.

**Rationale**:
- Alert types are a critical user-facing feature (feature 018)
- Localizing them via the same catalog ensures consistency with other UI text
- Machine key (e.g., `"attachment_amount_mismatch"`) stays in database; rendering uses localized label
- Single, unified source of truth for all user-visible labels

**Alternatives considered**:
- **Keep static object in alerts.ts**: Would require a separate second localization pass later (duplication risk)
- **Dynamic mapping at render time**: Same end result; catalog-based is cleaner

**Implementation**: See catalog section in `src/lib/i18n/catalog.ts` and `src/lib/alerts.ts` refactoring in the tasks/implementation phase.

### 5. Language Support: pt-BR as Canonical, en Optional

**Decision**: pt-BR is the complete, canonical catalog. en translations are optional; missing en keys fall back to pt-BR at runtime.

**Rationale**:
- App is for Portuguese-speaking users (Brazilian condominium)
- English as secondary locale allows future use or gradual translation
- Fallback pattern prevents missing-key errors if en lags behind pt-BR
- Spec requirement: "pt-BR as the default locale"

**Alternatives considered**:
- **All keys in both languages**: More work; English not prioritized
- **English only**: Contradicts spec requirement for pt-BR default

**Implementation**: Catalog structure supports both; en section is optional/partial in Phase 1 foundation.

## Testing Strategy

**Unit test for catalog completeness** (`tests/i18n/catalog.test.mjs`):
- Verifies every key in pt-BR catalog is present and well-formed
- Checks that en keys (if present) are a subset of pt-BR (no orphan keys)
- Runs on CI; prevents drift between locales
- Uses existing `node:test` pattern already in the project

## Next Steps

Tasks phase (speckit tasks) will break down the catalog creation, component refactoring, and test writing into individual, sequenced tasks ready for implementation.
