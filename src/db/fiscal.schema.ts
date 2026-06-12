import { relations } from "drizzle-orm";
import { sqliteTable, text, integer, real, index, uniqueIndex } from "drizzle-orm/sqlite-core";

const uuid = () =>
    text("id")
        .primaryKey()
        .$defaultFn(() => crypto.randomUUID());

const timestamps = {
    createdAt: integer("created_at", { mode: "timestamp_ms" as const })
        .notNull()
        .$defaultFn(() => new Date()),
    updatedAt: integer("updated_at", { mode: "timestamp_ms" as const })
        .notNull()
        .$defaultFn(() => new Date())
        .$onUpdate(() => new Date()),
};

// ─── Scrape Runs (coleta) ────────────────────────────────────────────────────

export const scrapeRuns = sqliteTable("scrape_runs", {
    id: uuid(),
    executedAt: integer("executed_at", { mode: "timestamp_ms" })
        .notNull()
        .$defaultFn(() => new Date()),
    status: text("status", { length: 20 }).notNull(), // running, success, error
    errors: text("errors"),
    durationSeconds: real("duration_seconds"),
});

// ─── Accountability Reports (prestacao_contas) ───────────────────────────────

export const accountabilityReports = sqliteTable(
    "accountability_reports",
    {
        id: uuid(),
        scrapeRunId: text("scrape_run_id")
            .notNull()
            .references(() => scrapeRuns.id),
        period: text("period", { length: 7 }).notNull(), // YYYY-MM
        externalBookId: integer("external_book_id").unique(),
        totalRevenue: real("total_revenue").notNull(),
        totalExpenses: real("total_expenses").notNull(),
        openingBalance: real("opening_balance").notNull(),
        monthBalance: real("month_balance").notNull(),
        accumulatedBalance: real("accumulated_balance").notNull(),
        sourceUrl: text("source_url").notNull(),
        ...timestamps,
    },
    table => [
        index("accountability_reports_scrape_run_id_idx").on(table.scrapeRunId),
        index("accountability_reports_period_idx").on(table.period),
    ]
);

// ─── Categories (categoria_ref) ──────────────────────────────────────────────

export const categories = sqliteTable("categories", {
    id: uuid(),
    name: text("name", { length: 100 }).notNull().unique(),
    movementType: text("movement_type", { length: 1 }).notNull(), // D or C
});

// ─── Subcategories (subcategoria_ref) ────────────────────────────────────────

export const subcategories = sqliteTable(
    "subcategories",
    {
        id: uuid(),
        categoryId: text("category_id")
            .notNull()
            .references(() => categories.id),
        name: text("name", { length: 100 }).notNull(),
    },
    table => [
        uniqueIndex("subcategories_category_id_name_idx").on(table.categoryId, table.name),
        index("subcategories_name_idx").on(table.name),
    ]
);

// ─── Vendors (fornecedor) ────────────────────────────────────────────────────

export const vendors = sqliteTable("vendors", {
    id: uuid(),
    name: text("name", { length: 200 }).notNull().unique(),
});

// ─── Units (unidade) ─────────────────────────────────────────────────────────

export const units = sqliteTable("units", {
    id: uuid(),
    block: text("block", { length: 1 }).notNull(),
    number: integer("number").notNull(),
    code: text("code", { length: 10 }).notNull().unique(), // e.g. "205C"
});

// ─── Entries (lancamento) ────────────────────────────────────────────────────

export const entries = sqliteTable(
    "entries",
    {
        id: uuid(),
        reportId: text("report_id")
            .notNull()
            .references(() => accountabilityReports.id),
        date: text("date").notNull(), // ISO date string YYYY-MM-DD
        description: text("description").notNull(),
        amount: real("amount").notNull(),
        // Scraper-owned raw provenance (feature 030 / IMP-001): verbatim portal cell text, nullable.
        // Only the scraper writes these; analysis never reads/writes them (mirror invariant).
        rawAmount: text("raw_amount"), // verbatim portal amount cell text, before parsing (e.g. "R$ 1.234,56")
        rawDescription: text("raw_description"), // verbatim portal description cell text, before normalization
        movementType: text("movement_type", { length: 1 }).notNull(), // D or C
        subcategoryId: text("subcategory_id")
            .notNull()
            .references(() => subcategories.id),
        unitId: text("unit_id").references(() => units.id),
        vendorId: text("vendor_id").references(() => vendors.id),
        externalDocumentId: integer("external_document_id"),
        sourceUrl: text("source_url").notNull(),
        ...timestamps,
    },
    table => [
        index("entries_report_id_idx").on(table.reportId),
        index("entries_date_idx").on(table.date),
        index("entries_movement_type_idx").on(table.movementType),
        index("entries_subcategory_id_idx").on(table.subcategoryId),
        index("entries_unit_id_idx").on(table.unitId),
        index("entries_vendor_id_idx").on(table.vendorId),
    ]
);

// ─── Category Subtotals (subtotal_categoria) ─────────────────────────────────

export const categorySubtotals = sqliteTable(
    "category_subtotals",
    {
        id: uuid(),
        reportId: text("report_id")
            .notNull()
            .references(() => accountabilityReports.id),
        subcategoryId: text("subcategory_id")
            .notNull()
            .references(() => subcategories.id),
        amount: real("amount").notNull(),
        movementType: text("movement_type", { length: 1 }).notNull(), // D or C
        ...timestamps,
    },
    table => [
        uniqueIndex("category_subtotals_report_subcategory_idx").on(table.reportId, table.subcategoryId),
        index("category_subtotals_report_id_idx").on(table.reportId),
        index("category_subtotals_subcategory_id_idx").on(table.subcategoryId),
    ]
);

// ─── Approvers (aprovador) ───────────────────────────────────────────────────

export const approvers = sqliteTable(
    "approvers",
    {
        id: uuid(),
        reportId: text("report_id")
            .notNull()
            .references(() => accountabilityReports.id),
        name: text("name", { length: 200 }).notNull(),
        status: text("status", { length: 50 }).notNull(),
    },
    table => [index("approvers_report_id_idx").on(table.reportId)]
);

// ─── Attachments (documento) ─────────────────────────────────────────────────
// The per-entry multi-page bundle downloaded from the portal. One per entry. Its
// pages may each be a different real document (NF/receipt/boleto) — those "documents"
// are a reserved, future N:N-with-entries concept, NOT modeled here.

export const attachments = sqliteTable(
    "attachments",
    {
        id: uuid(),
        entryId: text("entry_id")
            .notNull()
            .unique()
            .references(() => entries.id),
        externalDocumentId: integer("external_document_id").notNull(), // portal ("documento") id — KEEP
        filePath: text("file_path"),
        // Shared-NF grouping key: a stable content hash over the attachment's page-image
        // bytes, written at scrape time (and by the scraper's image-download backfill). The
        // ONLY writer is the scraper — analysis no longer backfills it (BUG-002 / issue #33).
        // Byte-identical page sets (the same NF copied per entry) share it; NULL when pages
        // are absent/unreadable or captured pre-016 (grouping falls back to an in-memory hash).
        contentHash: text("content_hash"),
        // NOTE: classification state (`classified_at`) lived here historically but was an
        // analysis-owned write to a mirror table (BUG-002). It now lives in `attachmentState`
        // below. `attachments` is once again an EXACT mirror of brcondos — only the scraper
        // writes it.
    },
    table => [index("attachments_entry_id_idx").on(table.entryId)]
);

// ─── Attachment State (analysis-owned classification state) ──────────────────
// Per-attachment classification state, kept OFF the mirror table `attachments`
// (BUG-002 / issue #33). The analysis pipeline writes here; the scraper never does, so
// `attachments` can be diffed against a fresh scrape to detect portal-side changes/forgery.
// Pending = no row OR `classified_at IS NULL`. apply-extractions stamps `classified_at`
// (atomically with the analysis rows); mark-pending clears it (NULL) to re-queue. The plan
// selects pending via `attachments LEFT JOIN attachment_state … WHERE classified_at IS NULL`.

export const attachmentState = sqliteTable("attachment_state", {
    attachmentId: text("attachment_id")
        .primaryKey()
        .references(() => attachments.id),
    classifiedAt: integer("classified_at", { mode: "timestamp_ms" }),
});

// ─── Attachment Analyses (analise_documento) ─────────────────────────────────

export const attachmentAnalyses = sqliteTable(
    "attachment_analyses",
    {
        id: uuid(),
        attachmentId: text("attachment_id")
            .notNull()
            .unique()
            .references(() => attachments.id),
        analyzedAt: integer("analyzed_at", { mode: "timestamp_ms" })
            .notNull()
            .$defaultFn(() => new Date()),
        documentType: text("document_type", { length: 50 }),
        extractedAmount: real("extracted_amount"),
        amountMatch: integer("amount_match", { mode: "boolean" }),
        extractedCnpj: text("extracted_cnpj", { length: 20 }),
        issuerName: text("issuer_name", { length: 200 }),
        vendorMatch: integer("vendor_match", { mode: "boolean" }),
        extractedDate: text("extracted_date", { length: 10 }),
        dateMatch: integer("date_match", { mode: "boolean" }),
        documentNumber: text("document_number", { length: 100 }),
        serviceDescription: text("service_description"),
        error: text("error"),
    },
    table => [index("attachment_analyses_attachment_id_idx").on(table.attachmentId)]
);

// ─── Attachment Analysis Records (registro_analise) ──────────────────────────
// Normalized per-page (and per-analysis-kind) records for an attachment analysis.
// One row per page per analysis_type; many per attachment, more than one per page
// allowed so future analysis kinds (e.g. forgery detection) attach without a
// schema change. The roll-up lives on attachment_analyses; per-page detail here.

export const attachmentAnalysisRecords = sqliteTable(
    "attachment_analysis_records",
    {
        id: uuid(),
        attachmentAnalysisId: text("attachment_analysis_id")
            .notNull()
            .references(() => attachmentAnalyses.id),
        analysisType: text("analysis_type", { length: 50 }).notNull(), // e.g. page_extraction
        pageIndex: integer("page_index"), // 0-based index into the file_path page list
        pageLabel: text("page_label", { length: 20 }), // e.g. p3 (the _pN suffix) or pageN
        artifactRole: text("artifact_role", { length: 30 }), // invoice/nfse/boleto/payment_proof/other
        response: text("response"), // JSON-serialized parsed page values
        parseError: text("parse_error"), // error when image missing/unreadable or unparseable
        analyzedAt: integer("analyzed_at", { mode: "timestamp_ms" })
            .notNull()
            .$defaultFn(() => new Date()),
    },
    table => [index("attachment_analysis_records_attachment_analysis_id_idx").on(table.attachmentAnalysisId)]
);

// ─── Page Classifications (classificacao_pagina) ─────────────────────────────
// Per-page staging input for the analysis merge: the raw vision result for ONE
// page of ONE attachment, written by the classify-doc-page flow (via the
// `record-classification` CLI) and read by `apply-extractions` to build the
// authoritative roll-up (attachment_analyses + records). One row per
// (attachment, page_label). Replaces the former `<image>.classify.json` file
// seam; NOT the surfaced analysis — pipeline input only.

export const pageClassifications = sqliteTable(
    "page_classifications",
    {
        id: uuid(),
        attachmentId: text("attachment_id")
            .notNull()
            .references(() => attachments.id),
        pageLabel: text("page_label", { length: 20 }).notNull(), // e.g. p3 (the _pN suffix) or pageN
        pageIndex: integer("page_index"), // 0-based index into the file_path page list (reference)
        response: text("response"), // JSON-serialized extracted fields; NULL on an error result
        error: text("error"), // short error reason; NULL on a successful fields object
        recordedAt: integer("recorded_at", { mode: "timestamp_ms" })
            .notNull()
            .$defaultFn(() => new Date()),
    },
    table => [index("page_classifications_attachment_id_idx").on(table.attachmentId)]
);

// ─── Alerts (alerta) ─────────────────────────────────────────────────────────

export const alerts = sqliteTable(
    "alerts",
    {
        id: uuid(),
        createdAt: integer("created_at", { mode: "timestamp_ms" })
            .notNull()
            .$defaultFn(() => new Date()),
        type: text("type", { length: 50 }).notNull(),
        severity: text("severity", { length: 20 }).notNull(), // critical, warning, info
        title: text("title", { length: 200 }).notNull(),
        description: text("description").notNull(),
        referencePeriod: text("reference_period", { length: 7 }).notNull(), // YYYY-MM
        resolved: integer("resolved", { mode: "boolean" }).default(false).notNull(),
        resolvedAt: integer("resolved_at", { mode: "timestamp_ms" }),
        notes: text("notes"),
        metadata: text("metadata"), // JSON string
    },
    table => [
        index("alerts_type_idx").on(table.type),
        index("alerts_severity_idx").on(table.severity),
        index("alerts_reference_period_idx").on(table.referencePeriod),
    ]
);

// ─── Documents (documento real) ──────────────────────────────────────────────
// A real fiscal document (NF / NFS-e / receipt / boleto) identified inside attachment
// pages. GLOBAL (not period-scoped): the same invoice re-submitted in another period
// resolves to one row via the semantic key (normalized document number + issuer CNPJ).
// Built by the analysis pipeline (`build-documents`) from attachment_analyses; linked
// N:N to entries via `document_entries`. Distinct from `attachments` (the per-entry page
// bundle). See specs/020-documents-entity.

export const documents = sqliteTable(
    "documents",
    {
        id: uuid(),
        documentNumber: text("document_number", { length: 100 }).notNull(), // normalized NF number (the key)
        issuerCnpj: text("issuer_cnpj", { length: 14 }).notNull(), // 14 digits (the other key part)
        issuerName: text("issuer_name", { length: 200 }), // display name
        documentType: text("document_type", { length: 50 }), // NF / NFS-e / receipt / boleto / …
        totalValue: real("total_value"), // invoice gross (max confident reconciliation total)
        ...timestamps,
    },
    table => [
        uniqueIndex("documents_number_cnpj_idx").on(table.documentNumber, table.issuerCnpj),
        index("documents_type_idx").on(table.documentType),
    ]
);

// ─── Document Entries (vinculo documento↔lancamento) ─────────────────────────
// The N:N link: one row per (document, entry) it is referenced by. Stores the source
// attachment for provenance; the claimed amount is read LIVE from entries.amount, never
// frozen here. Links accrue across periods as more attachments are analyzed.

export const documentEntries = sqliteTable(
    "document_entries",
    {
        id: uuid(),
        documentId: text("document_id")
            .notNull()
            .references(() => documents.id),
        entryId: text("entry_id")
            .notNull()
            .references(() => entries.id),
        sourceAttachmentId: text("source_attachment_id").references(() => attachments.id), // provenance
        createdAt: integer("created_at", { mode: "timestamp_ms" })
            .notNull()
            .$defaultFn(() => new Date()),
    },
    table => [
        uniqueIndex("document_entries_doc_entry_idx").on(table.documentId, table.entryId),
        index("document_entries_document_id_idx").on(table.documentId),
        index("document_entries_entry_id_idx").on(table.entryId),
    ]
);

// ─── Relations ───────────────────────────────────────────────────────────────

export const scrapeRunsRelations = relations(scrapeRuns, ({ many }) => ({
    accountabilityReports: many(accountabilityReports),
}));

export const accountabilityReportsRelations = relations(accountabilityReports, ({ one, many }) => ({
    scrapeRun: one(scrapeRuns, {
        fields: [accountabilityReports.scrapeRunId],
        references: [scrapeRuns.id],
    }),
    entries: many(entries),
    categorySubtotals: many(categorySubtotals),
    approvers: many(approvers),
}));

export const categoriesRelations = relations(categories, ({ many }) => ({
    subcategories: many(subcategories),
}));

export const subcategoriesRelations = relations(subcategories, ({ one }) => ({
    category: one(categories, {
        fields: [subcategories.categoryId],
        references: [categories.id],
    }),
}));

export const vendorsRelations = relations(vendors, ({ many }) => ({
    entries: many(entries),
}));

export const unitsRelations = relations(units, ({ many }) => ({
    entries: many(entries),
}));

export const entriesRelations = relations(entries, ({ one }) => ({
    report: one(accountabilityReports, {
        fields: [entries.reportId],
        references: [accountabilityReports.id],
    }),
    subcategory: one(subcategories, {
        fields: [entries.subcategoryId],
        references: [subcategories.id],
    }),
    unit: one(units, {
        fields: [entries.unitId],
        references: [units.id],
    }),
    vendor: one(vendors, {
        fields: [entries.vendorId],
        references: [vendors.id],
    }),
    attachment: one(attachments),
}));

export const categorySubtotalsRelations = relations(categorySubtotals, ({ one }) => ({
    report: one(accountabilityReports, {
        fields: [categorySubtotals.reportId],
        references: [accountabilityReports.id],
    }),
    subcategory: one(subcategories, {
        fields: [categorySubtotals.subcategoryId],
        references: [subcategories.id],
    }),
}));

export const approversRelations = relations(approvers, ({ one }) => ({
    report: one(accountabilityReports, {
        fields: [approvers.reportId],
        references: [accountabilityReports.id],
    }),
}));

export const attachmentsRelations = relations(attachments, ({ one, many }) => ({
    entry: one(entries, {
        fields: [attachments.entryId],
        references: [entries.id],
    }),
    analysis: one(attachmentAnalyses),
    pageClassifications: many(pageClassifications),
}));

export const pageClassificationsRelations = relations(pageClassifications, ({ one }) => ({
    attachment: one(attachments, {
        fields: [pageClassifications.attachmentId],
        references: [attachments.id],
    }),
}));

export const attachmentAnalysesRelations = relations(attachmentAnalyses, ({ one, many }) => ({
    attachment: one(attachments, {
        fields: [attachmentAnalyses.attachmentId],
        references: [attachments.id],
    }),
    records: many(attachmentAnalysisRecords),
}));

export const attachmentAnalysisRecordsRelations = relations(attachmentAnalysisRecords, ({ one }) => ({
    attachmentAnalysis: one(attachmentAnalyses, {
        fields: [attachmentAnalysisRecords.attachmentAnalysisId],
        references: [attachmentAnalyses.id],
    }),
}));

export const documentsRelations = relations(documents, ({ many }) => ({
    documentEntries: many(documentEntries),
}));

export const documentEntriesRelations = relations(documentEntries, ({ one }) => ({
    document: one(documents, {
        fields: [documentEntries.documentId],
        references: [documents.id],
    }),
    entry: one(entries, {
        fields: [documentEntries.entryId],
        references: [entries.id],
    }),
    sourceAttachment: one(attachments, {
        fields: [documentEntries.sourceAttachmentId],
        references: [attachments.id],
    }),
}));
