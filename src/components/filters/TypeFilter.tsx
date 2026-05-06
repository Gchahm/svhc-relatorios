"use client";

import { Card, CardContent } from "@/components/ui/card";
import { MultiSelect } from "@/components/ui/multi-select";

const MOVEMENT_TYPE_OPTIONS = [
    { value: "D", label: "Debit (D)" },
    { value: "C", label: "Credit (C)" },
];

interface TypeFilterProps {
    selected: string[];
    onSelectedChange: (selected: string[]) => void;
}

export function TypeFilter({ selected, onSelectedChange }: TypeFilterProps) {
    return (
        <Card>
            <CardContent className="p-3 space-y-2">
                <span className="text-xs font-medium text-muted-foreground">Type</span>
                <MultiSelect
                    options={MOVEMENT_TYPE_OPTIONS}
                    selected={selected}
                    onSelectedChange={onSelectedChange}
                    placeholder="All"
                    className="w-full"
                />
            </CardContent>
        </Card>
    );
}
