CREATE TABLE `page_classifications` (
	`id` text PRIMARY KEY NOT NULL,
	`attachment_id` text NOT NULL,
	`page_label` text(20) NOT NULL,
	`page_index` integer,
	`response` text,
	`error` text,
	`recorded_at` integer NOT NULL,
	FOREIGN KEY (`attachment_id`) REFERENCES `attachments`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `page_classifications_attachment_id_idx` ON `page_classifications` (`attachment_id`);--> statement-breakpoint
ALTER TABLE `attachment_analyses` DROP COLUMN `raw_response`;--> statement-breakpoint
ALTER TABLE `attachment_analysis_records` DROP COLUMN `raw_text`;