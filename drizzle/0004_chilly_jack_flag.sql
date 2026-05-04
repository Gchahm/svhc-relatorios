CREATE TABLE `accountability_reports` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`scrape_run_id` integer NOT NULL,
	`period` text(7) NOT NULL,
	`external_book_id` integer,
	`total_revenue` real NOT NULL,
	`total_expenses` real NOT NULL,
	`opening_balance` real NOT NULL,
	`month_balance` real NOT NULL,
	`accumulated_balance` real NOT NULL,
	`source_url` text NOT NULL,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`updated_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	FOREIGN KEY (`scrape_run_id`) REFERENCES `scrape_runs`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `accountability_reports_external_book_id_unique` ON `accountability_reports` (`external_book_id`);--> statement-breakpoint
CREATE INDEX `accountability_reports_scrape_run_id_idx` ON `accountability_reports` (`scrape_run_id`);--> statement-breakpoint
CREATE INDEX `accountability_reports_period_idx` ON `accountability_reports` (`period`);--> statement-breakpoint
CREATE TABLE `alerts` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`type` text(50) NOT NULL,
	`severity` text(20) NOT NULL,
	`title` text(200) NOT NULL,
	`description` text NOT NULL,
	`reference_period` text(7) NOT NULL,
	`resolved` integer DEFAULT false NOT NULL,
	`resolved_at` integer,
	`notes` text,
	`metadata` text
);
--> statement-breakpoint
CREATE INDEX `alerts_type_idx` ON `alerts` (`type`);--> statement-breakpoint
CREATE INDEX `alerts_severity_idx` ON `alerts` (`severity`);--> statement-breakpoint
CREATE INDEX `alerts_reference_period_idx` ON `alerts` (`reference_period`);--> statement-breakpoint
CREATE TABLE `approvers` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`report_id` integer NOT NULL,
	`name` text(200) NOT NULL,
	`status` text(50) NOT NULL,
	FOREIGN KEY (`report_id`) REFERENCES `accountability_reports`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `approvers_report_id_idx` ON `approvers` (`report_id`);--> statement-breakpoint
CREATE TABLE `categories` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text(100) NOT NULL,
	`movement_type` text(1) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `categories_name_unique` ON `categories` (`name`);--> statement-breakpoint
CREATE TABLE `category_subtotals` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`report_id` integer NOT NULL,
	`subcategory_id` integer NOT NULL,
	`amount` real NOT NULL,
	`movement_type` text(1) NOT NULL,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`updated_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	FOREIGN KEY (`report_id`) REFERENCES `accountability_reports`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`subcategory_id`) REFERENCES `subcategories`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `category_subtotals_report_subcategory_idx` ON `category_subtotals` (`report_id`,`subcategory_id`);--> statement-breakpoint
CREATE INDEX `category_subtotals_report_id_idx` ON `category_subtotals` (`report_id`);--> statement-breakpoint
CREATE INDEX `category_subtotals_subcategory_id_idx` ON `category_subtotals` (`subcategory_id`);--> statement-breakpoint
CREATE TABLE `document_analyses` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`document_id` integer NOT NULL,
	`analyzed_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`document_type` text(50),
	`extracted_amount` real,
	`amount_match` integer,
	`extracted_cnpj` text(20),
	`issuer_name` text(200),
	`vendor_match` integer,
	`extracted_date` text(10),
	`date_match` integer,
	`document_number` text(100),
	`service_description` text,
	`raw_response` text,
	`error` text,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `document_analyses_document_id_unique` ON `document_analyses` (`document_id`);--> statement-breakpoint
CREATE INDEX `document_analyses_document_id_idx` ON `document_analyses` (`document_id`);--> statement-breakpoint
CREATE TABLE `documents` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`entry_id` integer NOT NULL,
	`external_document_id` integer NOT NULL,
	`file_path` text,
	FOREIGN KEY (`entry_id`) REFERENCES `entries`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `documents_entry_id_unique` ON `documents` (`entry_id`);--> statement-breakpoint
CREATE INDEX `documents_entry_id_idx` ON `documents` (`entry_id`);--> statement-breakpoint
CREATE TABLE `entries` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`report_id` integer NOT NULL,
	`date` text NOT NULL,
	`description` text NOT NULL,
	`amount` real NOT NULL,
	`movement_type` text(1) NOT NULL,
	`subcategory_id` integer NOT NULL,
	`unit_id` integer,
	`vendor_id` integer,
	`external_document_id` integer,
	`source_url` text NOT NULL,
	`created_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`updated_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	FOREIGN KEY (`report_id`) REFERENCES `accountability_reports`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`subcategory_id`) REFERENCES `subcategories`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`unit_id`) REFERENCES `units`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`vendor_id`) REFERENCES `vendors`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `entries_report_id_idx` ON `entries` (`report_id`);--> statement-breakpoint
CREATE INDEX `entries_date_idx` ON `entries` (`date`);--> statement-breakpoint
CREATE INDEX `entries_movement_type_idx` ON `entries` (`movement_type`);--> statement-breakpoint
CREATE INDEX `entries_subcategory_id_idx` ON `entries` (`subcategory_id`);--> statement-breakpoint
CREATE INDEX `entries_unit_id_idx` ON `entries` (`unit_id`);--> statement-breakpoint
CREATE INDEX `entries_vendor_id_idx` ON `entries` (`vendor_id`);--> statement-breakpoint
CREATE TABLE `scrape_runs` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`executed_at` integer DEFAULT (cast(unixepoch('subsecond') * 1000 as integer)) NOT NULL,
	`status` text(20) NOT NULL,
	`errors` text,
	`duration_seconds` real
);
--> statement-breakpoint
CREATE TABLE `subcategories` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`category_id` integer NOT NULL,
	`name` text(100) NOT NULL,
	FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `subcategories_category_id_name_idx` ON `subcategories` (`category_id`,`name`);--> statement-breakpoint
CREATE INDEX `subcategories_name_idx` ON `subcategories` (`name`);--> statement-breakpoint
CREATE TABLE `units` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`block` text(1) NOT NULL,
	`number` integer NOT NULL,
	`code` text(10) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `units_code_unique` ON `units` (`code`);--> statement-breakpoint
CREATE TABLE `vendors` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text(200) NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `vendors_name_unique` ON `vendors` (`name`);