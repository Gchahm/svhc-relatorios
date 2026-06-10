import { Suspense } from "react";
import EntriesClient from "./EntriesClient";

export default function EntriesPage() {
    // EntriesClient reads search params (deep links: ?period=&entry=), which Next 15 requires
    // to live under a Suspense boundary.
    return (
        <Suspense>
            <EntriesClient />
        </Suspense>
    );
}
