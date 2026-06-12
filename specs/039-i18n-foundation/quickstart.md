# Quickstart: I18N-001 Localization Foundation

**Date**: 2026-06-12 | **Feature**: 039-i18n-foundation

## For Developers: How to Use the Localization System

Once I18N-001 is implemented, adding localized UI text to new features or components is straightforward.

### Step 1: Add Your Text to the Message Catalog

Open `src/lib/i18n/catalog.ts` and add your text to the appropriate section under the `pt-BR` locale:

```typescript
const catalog = {
  pt_BR: {
    // ... existing sections ...
    myFeature: {
      title: "Meu Recurso",
      description: "Esta é uma descrição do meu recurso",
      button_label: "Clique aqui",
    },
  },
  en: {
    // Optional: add English translations for your feature
    myFeature: {
      title: "My Feature",
      // ... etc
    },
  },
};
```

**Key naming convention**: Use kebab-case for multi-word keys, e.g., `button_label` (not `buttonLabel`). Organize under logical sections (e.g., `myFeature`, `nav`, `alert`).

### Step 2: Use the Translation Function in Server Components

In a server component (the default in Next.js 15 App Router), import `t()` and call it with your key:

```typescript
// app/my-feature/page.tsx (server component)
import { t } from "@/lib/i18n";

export default function MyFeaturePage() {
  return (
    <div>
      <h1>{t("myFeature.title")}</h1>
      <p>{t("myFeature.description")}</p>
      <button>{t("myFeature.button_label")}</button>
    </div>
  );
}
```

TypeScript will **error at build time** if you reference a key that doesn't exist in the catalog. This prevents silent failures.

### Step 3: Use the Translation Hook in Client Components

In a client component (marked with `"use client"`), use the `useTranslation()` hook:

```typescript
// components/my-feature-button.tsx (client component)
"use client";
import { useTranslation } from "@/lib/i18n/client";

export function MyFeatureButton() {
  const t = useTranslation();
  
  return (
    <button>
      {t("myFeature.button_label")}
    </button>
  );
}
```

The hook returns a function `t` that works the same way as the server-side `t()`.

### Step 4: Use Formatting Helpers for Numbers, Dates, and Currency

For values that need locale-aware formatting (currency, dates, numbers), use the centralized formatters:

```typescript
import { formatCurrency, formatDate, formatPercent, formatNumber } from "@/lib/i18n/formatters";

export function PriceCard({ amount, date, percentage }) {
  return (
    <div>
      <p>Preço: {formatCurrency(amount)}</p>
      <p>Data: {formatDate(date)}</p>
      <p>Percentual: {formatPercent(percentage)}</p>
      <p>Número: {formatNumber(1234.56)}</p>
    </div>
  );
}
```

**Example outputs (pt-BR)**:
- `formatCurrency(1234.56)` → `"R$ 1.234,56"`
- `formatDate(new Date("2026-06-12"))` → `"12/06/2026"`
- `formatPercent(0.75)` → `"75%"`
- `formatNumber(1234.56)` → `"1.234,56"`

### Step 5: Reference Alert Type Labels

Alert types (e.g., `"attachment_amount_mismatch"`) have localized labels in the catalog. To render an alert label:

```typescript
import { getAlertTypeLabel } from "@/lib/i18n";

export function AlertBadge({ alertType }) {
  const label = getAlertTypeLabel(alertType);
  return <span className="badge">{label}</span>;
}
```

This automatically resolves to the Portuguese label (or falls back to pt-BR if the locale is `en`).

---

## For Designers / Product: What Changed for Users

- All UI text is now in Portuguese (pt-BR) by default
- All numbers, dates, and currency are formatted according to Brazilian conventions
- Alert type labels are human-readable Portuguese phrases instead of machine keys
- The `<html lang>` attribute is set to `"pt-BR"` for accessibility
- Everything respects a consistent locale; if a locale switcher is added later (I18N-002), all text and formatting will update together

---

## For QA / Testing

### Test Catalog Completeness

Before release, verify that the catalog test passes:

```bash
cd /home/agent/workspace/svhc-relatorios
npm run test  # or pnpm test
```

The test `tests/i18n/catalog.test.mjs` checks:
- Every key in pt-BR is defined (no missing translations)
- en keys (if present) don't include orphan keys not in pt-BR
- All values are non-empty strings

**Test failure** = a developer added a key to the catalog but forgot to translate it, or there's a typo. The developer must fix it before merge.

### Manual Testing

1. Load the app in a browser and verify:
   - Page title in `<title>` is in Portuguese
   - All navigation labels are in Portuguese
   - All button labels are in Portuguese
   - All form placeholders are in Portuguese
   - All alert type labels are in Portuguese (not machine keys like `"attachment_amount_mismatch"`)
   - All dates are formatted as DD/MM/YYYY (e.g., `"12/06/2026"`)
   - All currency amounts are formatted as R$ X.XXX,XX (e.g., `"R$ 1.234,56"`)

2. Check browser developer tools → right-click page → View Page Source → verify `<html lang="pt-BR">`

---

## Common Mistakes to Avoid

### ❌ Hardcoding English Text

```typescript
// DON'T do this:
<button>Submit</button>
```

### ✅ Use the Catalog

```typescript
// DO this:
<button>{t("button.submit")}</button>
```

---

### ❌ Forgetting `"use client"` When Using `useTranslation()`

```typescript
// This will fail (useTranslation is a hook, needs client context):
export default function Page() {
  const t = useTranslation(); // ❌ ERROR
  return <div>{t("page.title")}</div>;
}
```

### ✅ Mark the Component as Client

```typescript
// Do this:
"use client";
import { useTranslation } from "@/lib/i18n/client";

export default function Page() {
  const t = useTranslation();
  return <div>{t("page.title")}</div>;
}
```

---

### ❌ Using Interpolation in Catalog Keys

```typescript
// DON'T put variables in the catalog:
catalog.pt_BR = { message: "Hello {name}" };
```

### ✅ Interpolate in Components

```typescript
// DO interpolation in the component:
const greeting = t("message.greeting"); // "Olá"
const fullText = `${greeting}, ${name}!`;
```

---

## Troubleshooting

### TypeScript Error: `Property 'unknown_key' does not exist on type 'CatalogShape'`

**Cause**: You referenced a catalog key that doesn't exist.

**Fix**: Check the spelling, or add the key to `catalog.pt_BR` in `src/lib/i18n/catalog.ts`.

### Page Shows English Text Instead of Portuguese

**Cause**: The text is hardcoded in the component, not using the catalog.

**Fix**: Replace hardcoded strings with `t("catalog.key")` calls.

### Formatting Helpers Return English Format (e.g., `"1,234.56"` instead of `"1.234,56"`)

**Cause**: You're using `toLocaleString()` directly instead of the centralized helpers.

**Fix**: Use `formatCurrency()`, `formatDate()`, etc. from `@/lib/i18n/formatters`.

---

## Next Steps

Once I18N-001 is deployed:
- **I18N-002**: Add cookie-based locale persistence so users can switch locales and have their choice remembered
- **I18N-003**: Add regional formatting variations (e.g., handling different date/number formats per region)
- **I18N-004**: Build a user-facing locale switcher UI
