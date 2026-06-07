# Contract: `analyze-docs` agent interface

The agent lives at `.claude/agents/analyze-docs.md` (a Claude Code subagent, same convention as
`pm.md`). It is invoked inside a Claude Code session.

## Frontmatter

```yaml
---
name: analyze-docs
description: >-
    Extracts structured fiscal fields from document page images for a scraped period — the Claude
    vision replacement for the retired mlx_vlm extraction step. Reads an existing work manifest for
    a period, views each representative page image, and writes a per-page extractions file that the
    deterministic `apply-extractions` step merges into the period JSON. It does NOT generate the
    manifest. Invoke it for requests like "analyze the documents for 2025-12" or "extract document
    fields for this period".
tools: Read, Glob, Write
model: inherit
color: blue
---
```

`Read` is required for native image vision; `Write` to emit the extractions file; `Glob` to locate
the manifest. The agent intentionally has **no `Bash`** — it does not run `docs-plan` or
`apply-extractions`; those are the maintainer's deterministic steps.

## Inputs

- A **period** (e.g. `2025-12`) and/or an explicit **manifest path**
  (`data/scrape/<period>.extract-todo.json`). The manifest must already exist (produced by the
  maintainer running `docs-plan`); the agent never generates it.

## Procedure (defined in the agent body)

1. **Read the manifest (never create it).** Read `data/scrape/<period>.extract-todo.json` (or the
   given path). If it does not exist, STOP and report that it is missing and the maintainer must run
   `docs-plan --periodo <period>` first — do not run `docs-plan` and do not create the manifest.
2. **Extract.** For each group, for each page, open `read_path` with the Read tool and produce the
   frozen field set (`contracts/page-extraction-fields.md`). On a missing/unreadable/illegible page,
   record `{ "error": "<reason>" }` for that page's `path`. Never fabricate values.
3. **Write** `data/scrape/<period>.extractions.json` keyed by each page's `path`
   (`contracts/extractions.schema.md`). Write incrementally / re-write the full map so a long run is
   resumable and inspectable.
4. **Report** how to finish: tell the maintainer to run
   `cd scripts && uv run python -m scraper apply-extractions --periodo <period>`. The agent does not
   run it.

## Guarantees / boundaries

- The agent only **reads** page images and **writes** the extractions file. It does not generate the
  manifest, run the merge, or edit application code, schema, or the period JSON directly — the
  deterministic `apply-extractions` is the only writer of `document_analyses`.
- The agent extracts each representative page once; byte-identical siblings are handled by the
  deterministic fan-out, so the agent never re-views them (SC-005).
- Output conforms to the extractions contract so `apply-extractions` and the import are unaffected.
