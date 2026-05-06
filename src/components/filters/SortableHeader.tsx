"use client";

import { useCallback, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export type SortDirection = "asc" | "desc" | null;

interface SortableHeaderProps {
    label: string;
    sortKey: string;
    currentSort: string | null;
    currentDirection: SortDirection;
    onSort: (key: string) => void;
    className?: string;
}

export function SortableHeader({
    label,
    sortKey,
    currentSort,
    currentDirection,
    onSort,
    className,
}: SortableHeaderProps) {
    const active = currentSort === sortKey;
    return (
        <button
            onClick={() => onSort(sortKey)}
            className={cn("flex items-center gap-0.5 hover:text-foreground transition-colors", className)}
        >
            {label}
            {active && currentDirection === "asc" && <ArrowUp className="h-3 w-3" />}
            {active && currentDirection === "desc" && <ArrowDown className="h-3 w-3" />}
            {!active && <ArrowUpDown className="h-3 w-3 opacity-30" />}
        </button>
    );
}

export function useSort<T>(defaultKey: string, defaultDir: SortDirection = "asc") {
    const [sortKey, setSortKey] = useState<string>(defaultKey);
    const [sortDir, setSortDir] = useState<SortDirection>(defaultDir);

    const toggleSort = (key: string) => {
        if (sortKey === key) {
            setSortDir(prev => (prev === "asc" ? "desc" : prev === "desc" ? null : "asc"));
        } else {
            setSortKey(key);
            setSortDir("asc");
        }
    };

    const sortFn = useCallback(
        (items: T[], getters: Record<string, (item: T) => string | number>): T[] => {
            if (!sortDir || !sortKey || !getters[sortKey]) return items;
            const getter = getters[sortKey];
            return [...items].sort((a, b) => {
                const va = getter(a);
                const vb = getter(b);
                const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
                return sortDir === "asc" ? cmp : -cmp;
            });
        },
        [sortKey, sortDir]
    );

    return { sortKey, sortDir, toggleSort, sortFn };
}
