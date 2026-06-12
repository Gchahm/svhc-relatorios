"use client";

import { useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { ChevronRight, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n/client";

interface CategoryNode {
    category: string;
    subcategories: string[];
}

interface CategoryTreeProps {
    data: { category: string; subcategory: string }[];
    selected: string[];
    onSelectedChange: (selected: string[]) => void;
}

export function CategoryTree({ data, selected, onSelectedChange }: CategoryTreeProps) {
    const t = useTranslation();
    const [expanded, setExpanded] = useState<Set<string>>(new Set());

    const tree = useMemo(() => {
        const map = new Map<string, string[]>();
        for (const r of data) {
            if (!map.has(r.category)) map.set(r.category, []);
            const subs = map.get(r.category)!;
            if (!subs.includes(r.subcategory)) subs.push(r.subcategory);
        }
        return [...map.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, subs]): CategoryNode => ({ category: cat, subcategories: subs.sort() }));
    }, [data]);

    const toggleCollapse = (cat: string) => {
        setExpanded(prev => {
            const next = new Set(prev);
            if (next.has(cat)) next.delete(cat);
            else next.add(cat);
            return next;
        });
    };

    const toggleCategory = (cat: string) => {
        const node = tree.find(n => n.category === cat);
        if (!node) return;
        const allSelected = node.subcategories.every(s => selected.includes(s));
        if (allSelected) {
            onSelectedChange(selected.filter(s => !node.subcategories.includes(s)));
        } else {
            onSelectedChange([...new Set([...selected, ...node.subcategories])]);
        }
    };

    const toggleSubcategory = (sub: string) => {
        onSelectedChange(selected.includes(sub) ? selected.filter(s => s !== sub) : [...selected, sub]);
    };

    return (
        <Card className="flex-1 flex flex-col min-h-0">
            <CardContent className="p-3 flex flex-col min-h-0 gap-1">
                <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-muted-foreground">
                        {t("filter.categories_subcategories")}
                    </span>
                    {selected.length > 0 && (
                        <button
                            onClick={() => onSelectedChange([])}
                            className="text-xs text-muted-foreground hover:text-foreground"
                        >
                            <X className="h-3 w-3" />
                        </button>
                    )}
                </div>
                <div className="overflow-auto flex-1 min-h-0">
                    {tree.map(({ category, subcategories }) => {
                        const allSelected = subcategories.every(s => selected.includes(s));
                        const someSelected = subcategories.some(s => selected.includes(s));
                        const collapsed = !expanded.has(category);
                        return (
                            <div key={category} className="mb-0.5">
                                <div className="flex items-center gap-0.5">
                                    <button
                                        onClick={() => toggleCollapse(category)}
                                        className="p-0.5 text-muted-foreground hover:text-foreground"
                                    >
                                        <ChevronRight
                                            className={cn("h-3 w-3 transition-transform", !collapsed && "rotate-90")}
                                        />
                                    </button>
                                    <button
                                        onClick={() => toggleCategory(category)}
                                        className={cn(
                                            "flex-1 text-left px-1.5 py-1 rounded text-xs truncate transition-colors font-medium",
                                            allSelected
                                                ? "bg-primary text-primary-foreground"
                                                : someSelected
                                                  ? "bg-primary/20 text-primary"
                                                  : "hover:bg-muted"
                                        )}
                                        title={category}
                                    >
                                        {category}
                                    </button>
                                </div>
                                {!collapsed && (
                                    <div className="ml-4 space-y-0.5 mt-0.5">
                                        {subcategories.map(sub => (
                                            <button
                                                key={sub}
                                                onClick={() => toggleSubcategory(sub)}
                                                className={cn(
                                                    "w-full text-left px-1.5 py-0.5 rounded text-xs truncate transition-colors",
                                                    selected.includes(sub)
                                                        ? "bg-primary text-primary-foreground"
                                                        : "hover:bg-muted text-muted-foreground"
                                                )}
                                                title={sub}
                                            >
                                                {sub}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            </CardContent>
        </Card>
    );
}
