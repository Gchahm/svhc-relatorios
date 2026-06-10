CREATE TABLE `document_entries` (
	`id` text PRIMARY KEY NOT NULL,
	`document_id` text NOT NULL,
	`entry_id` text NOT NULL,
	`source_attachment_id` text,
	`created_at` integer NOT NULL,
	FOREIGN KEY (`document_id`) REFERENCES `documents`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`entry_id`) REFERENCES `entries`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`source_attachment_id`) REFERENCES `attachments`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `document_entries_doc_entry_idx` ON `document_entries` (`document_id`,`entry_id`);--> statement-breakpoint
CREATE INDEX `document_entries_document_id_idx` ON `document_entries` (`document_id`);--> statement-breakpoint
CREATE INDEX `document_entries_entry_id_idx` ON `document_entries` (`entry_id`);--> statement-breakpoint
CREATE TABLE `documents` (
	`id` text PRIMARY KEY NOT NULL,
	`document_number` text(100) NOT NULL,
	`issuer_cnpj` text(14) NOT NULL,
	`issuer_name` text(200),
	`document_type` text(50),
	`total_value` real,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `documents_number_cnpj_idx` ON `documents` (`document_number`,`issuer_cnpj`);--> statement-breakpoint
CREATE INDEX `documents_type_idx` ON `documents` (`document_type`);