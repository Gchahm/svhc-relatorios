# Quickstart: Verify the rename is behavior-preserving

No automated tests (constitution III). Verification is a full pipeline run + UI inspection on one period, plus a search assertion. Default target is **local** (Miniflare); the local DB was already cleared.

## 0. Pre-flight

```bash
node_modules/.bin/tsc --noEmit        # or: pnpm build — type-check the renamed TS
pnpm lint && pnpm format              # constitution III gates
```

## 1. Apply the regenerated schema (drop & recreate)

```bash
node_modules/.bin/drizzle-kit generate   # produces the rename migration in drizzle/
pnpm db:migrate:dev                       # recreates attachments / attachment_analyses / attachment_analysis_records locally
```

Confirm the renamed tables exist and the old names are gone:

```bash
npx wrangler d1 execute DATABASE --local --json \
  --command "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%attachment%' OR name LIKE '%document%';"
# expect: attachments, attachment_analyses, attachment_analysis_records — and NO 'documents'/'document_analyses'
```

## 2. Re-scrape + analyze one period

```bash
python -m scraper scrape --download-docs --periodo 2025-12        # local; populates attachments + R2 page images
python -m analysis classify ... / apply-extractions --periodo 2025-12
python -m analysis analyze --periodo 2025-12
python -m analysis mismatches --periodo 2025-12                   # terse summary uses attachment_id / attachment_ids
```

Or drive the `analyze-docs` agent for the period. Confirm the run completes with no `document_id`/table-not-found errors.

## 3. Behavior-preserving assertions (SC-002)

- The alert set, roll-up amounts, and mismatch entries for `2025-12` match a pre-rename run on the same period (no new/missing alerts purely from the rename).
- Shared-NF grouping and duplicate-billing still fire on the same groups.

## 4. UI assertions (SC-003)

```bash
pnpm dev    # open /dashboard/entries
```

- The entries page loads; opening an entry shows the **attachment** analysis with its per-page records.
- Page images render (the renamed `/api/attachment-analyses/[id]/image/[page]` route streams bytes).
- No label calls the per-entry bundle a "document".

## 5. Name-freed assertion (SC-001 / SC-004)

```bash
# No primary code path uses 'document' to mean the per-entry bundle (allowing the documented KEEP set):
grep -rnE "documentAnalyses|documentAnalysisRecords|\bdocument_analyses\b|\bdocument_analysis_records\b|'documents'|\"documents\"" \
  --include='*.ts' --include='*.tsx' --include='*.py' src scripts \
  | grep -vE 'external_document_id|document_type|document_number|tipo_documento|ViewDocuments'
# expect: no matches
```

Confirm `docs/` + `CLAUDE.md` describe the reserved N:N **document** concept and the attachment-vs-document distinction.
