# Quickstart: Vision transcriber (EXTRACT-002)

## Library

```python
from doc_transcribe import transcribe

# Default cli backend (no API key, no anthropic SDK needed)
result = transcribe("data/scrape/2025-12/abc_p1.png")          # doc_type="auto"
print(result["doc_type"], result["schema_version"])
print(result["fields"]["raw_text"])                            # the evidence floor
if "parse_errors" in result:
    print("validation issues:", result["parse_errors"])

# Force a type
result = transcribe("recibo.png", doc_type="recibo")

# API backend (bulk) — needs `pip install anthropic` + ANTHROPIC_API_KEY
result = transcribe("nf.png", backend="api", model="claude-opus-4-8")
```

## CLI

```bash
# Default cli backend, auto-detect type → typed JSON on stdout
python -m doc_transcribe --image data/scrape/2025-12/abc_p1.png

# Force a type, use the api backend
python -m doc_transcribe --image nf.png --type danfe --backend api
```

## Run the tests

```bash
uv run python -m unittest discover -s tools/doc_transcribe/tests -t tools
```

Tests use a `FakeBackend` (no real `claude` subprocess, no Anthropic API, no network).

## Manual verification (against a live page)

With the local data present, point the `cli` backend at a real page image materialized under
`.cache/analysis/<period>/` (or `data/scrape/<period>/`) and confirm the result validates clean:

```bash
python -m doc_transcribe --image <a real page .png> | python -c "import json,sys; r=json.load(sys.stdin); print('doc_type=',r['doc_type'],'parse_errors=',r.get('parse_errors'))"
```

## Notes

- The module imports without `anthropic`; only the `api` backend touches it (lazy import).
- Validation is `doc_transcribe.validate_transcription` (EXTRACT-001) — the transcriber reuses it; the
  schemas/registry are unchanged.
- `prettier --check .` covers `tools/` — run `pnpm format` (or `prettier --write 'tools/**'`) before
  committing if you touch any json/md under the module.
