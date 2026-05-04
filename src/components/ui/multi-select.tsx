"use client";

import * as React from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface MultiSelectOption {
    value: string;
    label: string;
}

interface MultiSelectProps {
    options: MultiSelectOption[];
    selected: string[];
    onSelectedChange: (selected: string[]) => void;
    placeholder?: string;
    className?: string;
}

export function MultiSelect({ options, selected, onSelectedChange, placeholder = "All", className }: MultiSelectProps) {
    const [open, setOpen] = React.useState(false);

    const toggle = (value: string) => {
        onSelectedChange(
            selected.includes(value) ? selected.filter((s) => s !== value) : [...selected, value]
        );
    };

    const clear = (e: React.MouseEvent) => {
        e.stopPropagation();
        onSelectedChange([]);
    };

    const selectedLabels = selected
        .map((v) => options.find((o) => o.value === v)?.label ?? v)
        .slice(0, 2);
    const remaining = selected.length - selectedLabels.length;

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className={cn("h-9 justify-between font-normal", className)}
                >
                    <span className="flex items-center gap-1 truncate text-sm">
                        {selected.length === 0 ? (
                            <span className="text-muted-foreground">{placeholder}</span>
                        ) : (
                            <>
                                {selectedLabels.map((label) => (
                                    <Badge key={label} variant="secondary" className="px-1 py-0 text-xs font-normal">
                                        {label}
                                    </Badge>
                                ))}
                                {remaining > 0 && (
                                    <Badge variant="secondary" className="px-1 py-0 text-xs font-normal">
                                        +{remaining}
                                    </Badge>
                                )}
                            </>
                        )}
                    </span>
                    <span className="flex items-center gap-0.5 shrink-0 ml-1">
                        {selected.length > 0 && (
                            <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" onClick={clear} />
                        )}
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                    </span>
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[220px] p-0" align="start">
                <Command>
                    <CommandInput placeholder="Search..." className="h-8" />
                    <CommandList>
                        <CommandEmpty>No results.</CommandEmpty>
                        <CommandGroup>
                            {options.map((option) => (
                                <CommandItem key={option.value} value={option.label} onSelect={() => toggle(option.value)}>
                                    <div
                                        className={cn(
                                            "mr-2 flex h-4 w-4 items-center justify-center rounded-sm border border-primary",
                                            selected.includes(option.value)
                                                ? "bg-primary text-primary-foreground"
                                                : "opacity-50"
                                        )}
                                    >
                                        {selected.includes(option.value) && <Check className="h-3 w-3" />}
                                    </div>
                                    {option.label}
                                </CommandItem>
                            ))}
                        </CommandGroup>
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
