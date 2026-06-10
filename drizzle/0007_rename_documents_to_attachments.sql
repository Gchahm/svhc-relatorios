CREATE TABLE `attachment_analyses` (
	`id` text PRIMARY KEY NOT NULL,
	`attachment_id` text NOT NULL,
	`analyzed_at` integer NOT NULL,
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
	FOREIGN KEY (`attachment_id`) REFERENCES `attachments`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `attachment_analyses_attachment_id_unique` ON `attachment_analyses` (`attachment_id`);--> statement-breakpoint
CREATE INDEX `attachment_analyses_attachment_id_idx` ON `attachment_analyses` (`attachment_id`);--> statement-breakpoint
CREATE TABLE `attachment_analysis_records` (
	`id` text PRIMARY KEY NOT NULL,
	`attachment_analysis_id` text NOT NULL,
	`analysis_type` text(50) NOT NULL,
	`page_index` integer,
	`page_label` text(20),
	`artifact_role` text(30),
	`response` text,
	`raw_text` text,
	`parse_error` text,
	`analyzed_at` integer NOT NULL,
	FOREIGN KEY (`attachment_analysis_id`) REFERENCES `attachment_analyses`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `attachment_analysis_records_attachment_analysis_id_idx` ON `attachment_analysis_records` (`attachment_analysis_id`);--> statement-breakpoint
CREATE TABLE `attachments` (
	`id` text PRIMARY KEY NOT NULL,
	`entry_id` text NOT NULL,
	`external_document_id` integer NOT NULL,
	`file_path` text,
	FOREIGN KEY (`entry_id`) REFERENCES `entries`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `attachments_entry_id_unique` ON `attachments` (`entry_id`);--> statement-breakpoint
CREATE INDEX `attachments_entry_id_idx` ON `attachments` (`entry_id`);--> statement-breakpoint
DROP TABLE `document_analyses`;--> statement-breakpoint
DROP TABLE `document_analysis_records`;--> statement-breakpoint
DROP TABLE `documents`;