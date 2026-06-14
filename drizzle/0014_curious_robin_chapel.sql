CREATE TABLE `data_corrections` (
	`id` text PRIMARY KEY NOT NULL,
	`batch_id` text NOT NULL,
	`attachment_id` text NOT NULL,
	`period` text(7),
	`page_label` text(20) NOT NULL,
	`field` text NOT NULL,
	`from_value` text,
	`to_value` text,
	`evidence` text,
	`agent` text NOT NULL,
	`target_finding_key` text,
	`status` text(20) NOT NULL,
	`detail` text,
	`from_staging` text,
	`created_at` integer NOT NULL,
	`reverted_at` integer,
	`reverted_by` text,
	FOREIGN KEY (`attachment_id`) REFERENCES `attachments`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `data_corrections_attachment_id_idx` ON `data_corrections` (`attachment_id`);--> statement-breakpoint
CREATE INDEX `data_corrections_status_idx` ON `data_corrections` (`status`);--> statement-breakpoint
CREATE INDEX `data_corrections_period_idx` ON `data_corrections` (`period`);