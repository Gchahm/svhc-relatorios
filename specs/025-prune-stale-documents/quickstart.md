# Quickstart: verify the documents prune

## Run the unit tests (no D1 needed)

```bash
cd /home/agent/workspace/svhc-relatorios/scripts
python -m unittest discover -s tests -t scripts
```

Expect `test_document_prune.py` to pass alongside the existing writeback tests.

## End-to-end against local data

```bash
cd /home/agent/workspace/svhc-relatorios

# 1. Build documents from the current analyses.
uv run --project scripts python -m analysis build-documents   # local D1

# 2. Inspect a document + its links.
npx wrangler d1 execute DATABASE --local \
  --command "SELECT id, document_number, issuer_cnpj FROM documents LIMIT 5;"

# 3. Simulate a re-classification: change one attachment_analysis's document_number to a new value,
#    then rebuild and confirm the OLD document/link are gone and the NEW one is present.
#    (See specs/025-prune-stale-documents/spec.md User Story 1.)

# 4. Confirm no orphan documents remain (a document with zero links should not exist after a rebuild
#    unless an analysis still produces it):
npx wrangler d1 execute DATABASE --local --command \
  "SELECT d.id FROM documents d LEFT JOIN document_entries de ON de.document_id = d.id WHERE de.id IS NULL;"
```

## UI verification

Log into the dashboard (`ui-login` skill), open `/dashboard/documents`, note a document, run a rebuild
after re-classification, and confirm the obsolete document no longer appears.
