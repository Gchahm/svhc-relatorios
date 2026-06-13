"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

/**
 * Client wrapper around next-themes' ThemeProvider so it can be mounted inside the
 * server root layout. Toggles the `.dark` class on <html> (Tailwind `darkMode: ["class"]`),
 * tracks the OS `prefers-color-scheme` for system mode, and persists the choice to
 * localStorage (next-themes' default `theme` key) — applied before first paint via the
 * library's inline script (no flash-of-wrong-theme). Feature 047 (UI-001).
 */
export function ThemeProvider({ children, ...props }: React.ComponentProps<typeof NextThemesProvider>) {
    return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
