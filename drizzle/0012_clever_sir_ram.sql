CREATE TABLE `attachment_state` (
	`attachment_id` text PRIMARY KEY NOT NULL,
	`classified_at` integer,
	FOREIGN KEY (`attachment_id`) REFERENCES `attachments`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
-- BUG-002 / issue #33: carry existing classification state off the mirror table into the
-- analysis-owned table BEFORE dropping the column, so already-classified attachments are not
-- re-classified after the upgrade (FR-008 / SC-003). content_hash stays on `attachments`.
INSERT INTO `attachment_state` (`attachment_id`, `classified_at`)
SELECT `id`, `classified_at` FROM `attachments` WHERE `classified_at` IS NOT NULL;
--> statement-breakpoint
ALTER TABLE `attachments` DROP COLUMN `classified_at`;