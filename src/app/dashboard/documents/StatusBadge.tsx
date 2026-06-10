import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/lib/documents";

/** Over/within/under/unknown reconciliation badge, shared by the documents list and detail page. */
export function StatusBadge({ status }: { status: DocumentStatus }) {
    if (status === "over") return <Badge variant="destructive">over</Badge>;
    if (status === "within") {
        return (
            <Badge variant="outline" className="border-green-400 text-green-700">
                within
            </Badge>
        );
    }
    if (status === "under") {
        return (
            <Badge variant="outline" className="border-yellow-400 text-yellow-700">
                under
            </Badge>
        );
    }
    return <Badge variant="secondary">unknown</Badge>;
}
