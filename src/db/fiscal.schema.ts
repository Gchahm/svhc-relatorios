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

// ─── Documents (documento) ───────────────────────────────────────────────────

export const documents = sqliteTable(
    "documents",
    {
        id: uuid(),
        entryId: text("entry_id")
            .notNull()
            .unique()
            .references(() => entries.id),
        externalDocumentId: integer("external_document_id").notNull(),
        filePath: text("file_path"),
    },
    table => [index("documents_entry_id_idx").on(table.entryId)]
);

// ─── Document Analyses (analise_documento) ───────────────────────────────────

export const documentAnalyses = sqliteTable(
    "document_analyses",
    {
        id: uuid(),
        documentId: text("document_id")
            .notNull()
            .unique()
            .references(() => documents.id),
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
        rawResponse: text("raw_response"),
        error: text("error"),
    },
    table => [index("document_analyses_document_id_idx").on(table.documentId)]
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
    document: one(documents),
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

export const documentsRelations = relations(documents, ({ one }) => ({
    entry: one(entries, {
        fields: [documents.entryId],
        references: [entries.id],
    }),
    analysis: one(documentAnalyses),
}));

export const documentAnalysesRelations = relations(documentAnalyses, ({ one }) => ({
    document: one(documents, {
        fields: [documentAnalyses.documentId],
        references: [documents.id],
    }),
}));
