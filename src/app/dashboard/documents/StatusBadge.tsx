"use client";

import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/documents";
import { documentStatusLabelKey } from "@/lib/documents-label";
import { useTranslation } from "@/lib/i18n/client";

/** Over/within/under/unknown reconciliation badge, shared by the documents list and detail page. */
export function StatusBadge({ status }: { status: DocumentStatus }) {
    const t = useTranslation();
    // Localized label resolved via the pure, unit-tested key mapping (feature 045 / TEST-003).
    const label = t(documentStatusLabelKey(status));
    if (status === "over") return <Badge variant="destructive">{label}</Badge>;
    if (status === "within") {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700">
                {label}
            </Badge>
        );
    }
    if (status === "under") {
        return (
            <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                {label}
            </Badge>
        );
    }
    return <Badge variant="secondary">{label}</Badge>;
}
