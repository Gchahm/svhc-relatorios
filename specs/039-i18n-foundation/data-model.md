# Data Model: I18N-001 Localization Foundation

**Date**: 2026-06-12 | **Feature**: 039-i18n-foundation

## Overview

No database schema changes for this feature. All data is static, compile-time, and in-memory. The message catalog is a TypeScript constant; locale is a runtime session value.

## Core Entities

### Message Catalog

**Description**: A typed, nested dictionary mapping locale-specific keys to UI strings. Source of truth for all localized text in the application.

**Storage**: TypeScript module `src/lib/i18n/catalog.ts` (not persisted)

**Structure**:

```typescript
type SupportedLocale = "pt-BR" | "en";

type CatalogShape = {
  nav: {
    home: string;
    entries: string;
    documents: string;
    alerts: string;
    dashboard: string;
  };
  button: {
    submit: string;
    cancel: string;
    save: string;
    delete: string;
    close: string;
    search: string;
  };
  page: {
    entries_title: string;
    entries_description: string;
    documents_title: string;
    documents_description: string;
    alerts_title: string;
    alerts_description: string;
  };
  dialog: {
    attachment_detail_title: string;
    confirm_delete_title: string;
    confirm_delete_message: string;
  };
  table: {
    period: string;
    date: string;
    amount: string;
    vendor: string;
    description: string;
    attachment: string;
    actions: string;
  };
  form: {
    search_placeholder: string;
    select_period: string;
    select_placeholder: string;
    no_results: string;
  };
  badge: {
    pending: string;
    classified: string;
    analyzed: string;
    error: string;
  };
  alert: {
    types: {
      attachment_amount_mismatch: string;
      attachment_vendor_mismatch: string;
      attachment_date_mismatch: string;
      attachment_page_error: string;
      duplicate_billing: string;
      duplicate_entry: string;
      [key: string]: string; // Extensible for all alert types
    };
  };
  error: {
    not_found: string;
    unauthorized: string;
    server_error: string;
    network_error: string;
  };
  common: {
    loading: string;
    no_data: string;
    error: string;
    success: string;
  };
};

const catalog: Record<SupportedLocale, CatalogShape> = {
  "pt-BR": { /* complete translations */ },
  "en": { /* optional partial translations, fallback to pt-BR */ }
};
```

**Attributes**:

| Attribute | Type | Notes |
|-----------|------|-------|
| locale | `"pt-BR" \| "en"` | Language code |
| key | string (dot-notation path) | e.g., `"nav.home"`, `"alert.types.attachment_amount_mismatch"` |
| value | string | Localized UI text |
| fallback_locale | `"pt-BR"` | Used when locale is `"en"` and key not found |

**Validation Rules**:

- Every key in pt-BR is **canonical** and **must be defined**
- Every key in en is **optional**; missing keys fall back to pt-BR
- All keys must be non-empty strings
- Key names must follow kebab-case for multi-word keys (e.g., `"button.submit"`, not `"button.Submit"`)
- No circular references (message values are plain strings, not references to other keys)

**Lifecycle**:

- **Created**: At project build time when `src/lib/i18n/catalog.ts` is parsed
- **Updated**: When adding new UI strings (developer edits `catalog.ts`, commits to repo, new keys become available in next build)
- **No runtime mutations**: Catalog is frozen (`Object.freeze` or implicit via `as const`)

---

### Locale

**Description**: The active language/regional setting for the current request/session. Controls which catalog section is read for translation lookups.

**Storage**: 
- **Server-side**: Derived from Cloudflare context (future: cookies via I18N-002)
- **Client-side**: React context, seeded by server at layout render time

**Structure**:

```typescript
type Locale = "pt-BR" | "en";
type LocaleContext = {
  locale: Locale;
  setLocale?: (locale: Locale) => void; // Future: I18N-002
};
```

**Attributes**:

| Attribute | Type | Default | Notes |
|-----------|------|---------|-------|
| locale | `"pt-BR" \| "en"` | `"pt-BR"` | Current active locale |
| source | string | "default" or "cookie" | Where locale came from (informational) |

**Resolution Logic** (priority order):

1. **Server**: Check Cloudflare context / request headers for locale hint (future: I18N-002 cookie)
2. **Fallback**: Default to `"pt-BR"`
3. **Client**: Inject into `LocaleProvider` context; all client components read from context

**Constraints**:

- Locale must be one of the supported values (`"pt-BR"` or `"en"`)
- Invalid/unknown locale values default to `"pt-BR"`
- Locale does not persist across sessions in this foundation (I18N-002 adds persistence)

**Lifecycle**:

- **Created**: At request start (server) or on app mount (client)
- **Updated**: Via `setLocale()` hook (future feature; not in I18N-001)
- **Destroyed**: At request end (server) or on app unmount (client)

---

### Translation Function

**Description**: The mechanism by which components resolve a catalog key to a localized string in the active locale.

**Interface**:

```typescript
// Server-side
function t(key: CatalogKey, locale?: Locale): string;

// Client-side
function useTranslation(): (key: CatalogKey) => string;
```

**Behavior**:

1. Accepts a catalog key (type-safe, validated by TypeScript)
2. Looks up the key in `catalog[activeLocale]`
3. If found, returns the string
4. If not found (e.g., en key missing):
   - Checks `catalog["pt-BR"]` (fallback)
   - If found, returns pt-BR value
   - If still not found, raises a build-time or test-time error (never silently fails at runtime)
5. Returns the string without mutation or interpolation (interpolation is component's responsibility)

**Validation**:

- TypeScript enforces that only valid catalog keys are passed
- Missing keys cause a build error, not a runtime error or fallback string like `"nav.unknown_key"`

---

## Key Entities Relationships

```
┌─────────────────────┐
│   Message Catalog   │
│  (TypeScript object)│
├─────────────────────┤
│ pt-BR: {...}        │  ◄─── Canonical, complete
│ en: {...}           │  ◄─── Optional, partial (fallback to pt-BR)
└──────────────────────┘
         ▲
         │ (lookup via t())
         │
    ┌────────────────┐
    │ Active Locale  │
    ├────────────────┤
    │ pt-BR (default)│
    │ en (optional)  │
    └────────────────┘
         ▲
         │ (read from)
         │
    ┌────────────────┐
    │ Components     │
    ├────────────────┤
    │ call t(key)    │
    │ or useT()      │
    └────────────────┘
```

---

## No Schema Changes

This feature makes **no changes** to:
- `src/db/` (database schema, migrations)
- `src/db/fiscal.schema.ts` (table definitions)
- `wrangler.toml` (bindings, environment)
- API response formats
- Python pipeline

All localization is **presentation-layer only**: catalog in TypeScript, rendering in React, no data persistence.

---

## Testing Strategy

**Unit Tests** (`tests/i18n/catalog.test.mjs`):

1. Catalog completeness: Every key in pt-BR is defined
2. Fallback coverage: Every en key is a subset of pt-BR (no orphan en keys)
3. Type validation: Catalog shape matches `CatalogShape` type
4. No empty strings: All values are non-empty
5. Key naming: All keys follow kebab-case convention

Run on CI; prevent merging if any test fails.

---

## Future Extensions (Out of Scope)

- **I18N-002**: Add cookie-based locale persistence
- **I18N-003**: Regional number/currency/date formatting variants
- **I18N-004**: User locale switcher UI + preference storage
- **I18N-005**: Dynamic content localization (e.g., vendor names, category descriptions from D1)
