# Contract: Theme preference (client-only)

There is **no network/API contract** for this feature (no endpoint, no D1, no R2). The "contract" is the browser-local storage shape and the component interface, documented here for completeness.

## Storage contract (localStorage)

- **Key**: `theme` (next-themes default; not overridden).
- **Value**: one of `"light"`, `"dark"`, `"system"`. Any other value is treated as unset.
- **Owner/writer**: `next-themes` `ThemeProvider` (via `setTheme`). Application code never writes this key directly.
- **Read by**: `next-themes` on load (sets `<html class="dark">` before paint via its inline script) and `useTheme()` in components.

## Component contracts

### `ThemeProvider` (`src/components/theme-provider.tsx`)

- `"use client"` wrapper re-exporting next-themes' `ThemeProvider`.
- Mounted in `RootLayout` with props: `attribute="class"`, `defaultTheme="system"`, `enableSystem`, `disableTransitionOnChange` (optional, avoids a flash of transition on switch).
- Children: the rest of the app (including `LocaleProvider`).

### `ThemeToggle` (`src/app/dashboard/ThemeToggle.tsx`)

- `"use client"`. No props.
- Renders a ghost icon `Button` (Sun/Moon crossfade) as a `DropdownMenuTrigger`.
- Menu items call `setTheme("light" | "dark" | "system")` from `useTheme()`.
- Labels via `useTranslation()`: `theme.toggle_label`, `theme.light`, `theme.dark`, `theme.system`.
- Accessible name (`sr-only` / `aria-label`) = `t("theme.toggle_label")`.
- Guards theme-dependent active-state on a `mounted` flag to avoid SSR hydration mismatch.

## Catalog contract (i18n)

`CatalogShape.theme` (both `pt-BR` and `en` must define all keys — enforced by the type + `catalog.test.mjs`):

| Key | pt-BR | en |
|-----|-------|-----|
| `theme.toggle_label` | Tema | Theme |
| `theme.light` | Claro | Light |
| `theme.dark` | Escuro | Dark |
| `theme.system` | Sistema | System |
