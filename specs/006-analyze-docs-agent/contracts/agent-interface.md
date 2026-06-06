# Contract: `analyze-docs` agent interface

The agent lives at `.claude/agents/analyze-docs.md` (a Claude Code subagent, same convention as
`pm.md`). It is invoked inside a Claude Code session.

## Frontmatter

```yaml
---
name: analyze-docs
description: >-
    Extracts structured fiscal fields from document page images for a scraped period — the Claude
    vision replacement for the retired mlx_vlm extraction step. Reads the work manifest for a
    period, views each representative page image, and writes a per-page extractions file that the
    deterministic `apply-extractions` step merges into the period JSON. Invoke it for requests like
    "analyze the documents for 2025-12" or "extract document fields for this period".
tools: Read, Glob, Bash, Write
model: inherit
color: blue
---
```

`Read` is required for native image vision; `Bash` to run `docs-plan`/`apply-extractions` and locate
files; `Write` to emit the extractions file; `Glob` to discover manifests/periods.

## Inputs

- A **period** (e.g. `2025-12`) and/or an explicit **manifest path**
  (`data/scrape/<period>.extract-todo.json`).
- Optional pass-through selection flags (min amount, limit, document/entry ids, reanalyze) when the
  agent is asked to generate the manifest itself.

## Procedure (defined in the agent body)

1. **Ensure a manifest.** If a manifest path is given, read it. Otherwise run
   `cd scripts && uv run python -m scraper docs-plan --periodo <period> [flags]` to produce
   `data/scrape/<period>.extract-todo.json`, then read it.
2. **Extract.** For each group, for each page, open `read_path` with the Read tool and produce the
   frozen field set (`contracts/page-extraction-fields.md`). On a missing/unreadable/illegible page,
   record `{ "error": "<reason>" }` for that page's `path`. Never fabricate values.
3. **Write** `data/scrape/<period>.extractions.json` keyed by each page's `path`
   (`contracts/extractions.schema.md`). Write incrementally / re-write the full map so a long run is
   resumable and inspectable.
4. **Report** how to finish: `cd scripts && uv run python -m scraper apply-extractions --periodo
<period>` (the agent MAY run it via Bash, or leave it to the maintainer).

## Guarantees / boundaries

- The agent only **reads** page images and **writes** the extractions file (plus, optionally, runs
  the two deterministic commands). It does not edit application code, schema, or the period JSON
  directly — the deterministic `apply-extractions` is the only writer of `document_analyses`.
- The agent extracts each representative page once; byte-identical siblings are handled by the
  deterministic fan-out, so the agent never re-views them (SC-005).
- Output conforms to the extractions contract so `apply-extractions` and the import are unaffected.
