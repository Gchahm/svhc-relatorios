"use client";

import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/documents";
import { useTranslation } from "@/lib/i18n/client";

/** Over/within/under/unknown reconciliation badge, shared by the documents list and detail page. */
export function StatusBadge({ status }: { status: DocumentStatus }) {
    const t = useTranslation();
    if (status === "over") return <Badge variant="destructive">{t("status.over")}</Badge>;
    if (status === "within") {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700">
                {t("status.within")}
            </Badge>
        );
    }
    if (status === "under") {
        return (
            <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                {t("status.under")}
            </Badge>
        );
    }
    return <Badge variant="secondary">{t("status.unknown")}</Badge>;
}
