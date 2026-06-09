import { redirect } from "next/navigation";

// The standalone Document Analyses page has been merged into the Entries page.
// Redirect old links/bookmarks to the merged, period-scoped view.
export default function DocumentAnalysesPage() {
    redirect("/dashboard/entries");
}
