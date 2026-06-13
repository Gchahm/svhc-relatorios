"use client";

import { useState } from "react";
import { ImageOff, ZoomIn } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useTranslation } from "@/lib/i18n/client";

type Status = "loading" | "loaded" | "error";

/**
 * Renders one document page image fetched from the auth-gated image route.
 *
 * - Lazy-loads the image so it never blocks the surrounding extracted fields (FR-007).
 * - Shows a loading skeleton, and an "image unavailable" placeholder on any load error /
 *   non-200 response (FR-006).
 * - Click to open a full-resolution lightbox for fine-detail inspection (US2 / FR-008).
 *
 * A plain <img> is used intentionally: the source is an authenticated, dynamic API route, which
 * next/image's optimizer cannot proxy cleanly on the Workers runtime.
 */
export default function PageImageViewer({ src, alt }: { src: string; alt: string }) {
    const t = useTranslation();
    const [status, setStatus] = useState<Status>("loading");
    const [open, setOpen] = useState(false);

    if (status === "error") {
        return (
            <div className="flex h-40 flex-col items-center justify-center gap-1 rounded-md border border-dashed bg-muted/30 text-muted-foreground">
                <ImageOff className="h-5 w-5" />
                <span className="text-xs">{t("viewer.image_unavailable")}</span>
            </div>
        );
    }

    return (
        <>
            <button
                type="button"
                onClick={() => status === "loaded" && setOpen(true)}
                className="group relative block w-full overflow-hidden rounded-md border bg-muted/30"
                aria-label={t("viewer.enlarge").replace("{alt}", alt)}
            >
                {status === "loading" && <div className="h-40 w-full animate-pulse bg-muted" />}
                {/* eslint-disable-next-line @next/next/no-img-element -- auth-gated dynamic route; next/image cannot proxy it on Workers */}
                <img
                    src={src}
                    alt={alt}
                    loading="lazy"
                    onLoad={() => setStatus("loaded")}
                    onError={() => setStatus("error")}
                    className={`max-h-80 w-full object-contain transition-opacity ${
                        status === "loaded" ? "opacity-100" : "absolute h-0 w-0 opacity-0"
                    }`}
                />
                {status === "loaded" && (
                    <span className="pointer-events-none absolute right-2 top-2 rounded bg-background/80 p-1 opacity-0 transition-opacity group-hover:opacity-100">
                        <ZoomIn className="h-4 w-4" />
                    </span>
                )}
            </button>

            <Dialog open={open} onOpenChange={setOpen}>
                <DialogContent className="max-w-[95vw] p-2 sm:max-w-5xl">
                    <DialogTitle className="sr-only">{alt}</DialogTitle>
                    {/* eslint-disable-next-line @next/next/no-img-element -- see above */}
                    <img src={src} alt={alt} className="max-h-[85vh] w-full object-contain" />
                </DialogContent>
            </Dialog>
        </>
    );
}
