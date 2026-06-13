"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Check, Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslation } from "@/lib/i18n/client";

type ThemeMode = "light" | "dark" | "system";

/**
 * Theme toggle for the dashboard shell header (feature 047 / UI-001). A sun/moon icon button
 * (CSS-crossfade keyed off the `.dark` class) opens a menu offering Light / Dark / System.
 * Labels come from the I18N-001 catalog (`theme.*`). The active-mode checkmark is gated behind
 * a `mounted` flag so the server render (where `theme` is unknown) matches first client paint.
 */
export default function ThemeToggle() {
    const t = useTranslation();
    const { theme, setTheme } = useTheme();
    const [mounted, setMounted] = useState(false);

    useEffect(() => setMounted(true), []);

    const modes: { value: ThemeMode; label: string; icon: React.ReactNode }[] = [
        { value: "light", label: t("theme.light"), icon: <Sun className="h-3.5 w-3.5" /> },
        { value: "dark", label: t("theme.dark"), icon: <Moon className="h-3.5 w-3.5" /> },
        { value: "system", label: t("theme.system"), icon: <Monitor className="h-3.5 w-3.5" /> },
    ];

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 w-8 px-0" aria-label={t("theme.toggle_label")}>
                    <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
                    <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
                    <span className="sr-only">{t("theme.toggle_label")}</span>
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
                {modes.map(mode => (
                    <DropdownMenuItem
                        key={mode.value}
                        onClick={() => setTheme(mode.value)}
                        className="cursor-pointer gap-2"
                    >
                        {mode.icon}
                        <span className="flex-1">{mode.label}</span>
                        {mounted && theme === mode.value ? <Check className="h-3.5 w-3.5" /> : null}
                    </DropdownMenuItem>
                ))}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
