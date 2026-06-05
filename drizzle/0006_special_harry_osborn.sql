CREATE TABLE `document_analysis_records` (
	`id` text PRIMARY KEY NOT NULL,
	`document_analysis_id` text NOT NULL,
	`analysis_type` text(50) NOT NULL,
	`page_index` integer,
	`page_label` text(20),
	`artifact_role` text(30),
	`response` text,
	`raw_text` text,
	`parse_error` text,
	`analyzed_at` integer NOT NULL,
	FOREIGN KEY (`document_analysis_id`) REFERENCES `document_analyses`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `document_analysis_records_document_analysis_id_idx` ON `document_analysis_records` (`document_analysis_id`);