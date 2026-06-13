# Phase 0 Research: Document→attachment(s) evidence resolver

## Decision: dedicated `document-evidence --id <id>` subcommand (not a `mismatches --document-id` flag)

- **Rationale**: The design doc §4.3 offers both. A dedicated subcommand isolates the
  document-resolution concern, gives a natural home for the unknown-id error (`mismatches` has no
  notion of "the id you scoped to doesn't exist"), and leaves the existing `mismatches` flag surface
  (`--attachment-id` / `--entry-id`) unchanged. The triage agent gets one named entry point.
- **Alternatives considered**: a `--document-id` flag on `mismatches` — rejected because it muddies
  the scoping semantics (the flag would have to silently expand to attachment ids, and an unknown
  document would print an empty list indistinguishable from "no findings", violating FR-005).

## Decision: resolve via `document_entries.source_attachment_id`

- **Rationale**: A document is global and N:N with entries via `document_entries`; each link row
  carries `source_attachment_id` (the attachment that produced that link — feature 020 provenance).
  The distinct, non-NULL set of `source_attachment_id` for a given `document_id` is exactly the
  attachment set corrections happen on. One read-only `SELECT DISTINCT source_attachment_id FROM
  document_entries WHERE document_id = ?` (NULLs excluded) yields it.
- **Unknown-id detection**: `document_entries` rows can be absent for a real-but-unlinked document,
  so existence is checked against the `documents` table itself (`SELECT id FROM documents WHERE
  id = ?`). A missing row ⇒ unknown id ⇒ non-zero exit (FR-005). A present document with no
  resolvable source attachments ⇒ empty findings result (FR-006).
- **Alternatives considered**: deriving attachments from `attachment_analyses` by re-matching
  (number, cnpj) — rejected as it re-implements `build_documents` and risks drift; the persisted
  link provenance is the authoritative, already-computed mapping.

## Decision: reuse `summarize_mismatches(attachment_ids=...)` untouched

- **Rationale**: `summarize_mismatches` already produces the exact per-finding shape + `page_refs`
  (materialized image `read_path`s) the agent needs, and already scopes by attachment ids and
  materializes images for the scoped set. Calling it with the resolved attachment ids gives identical
  output to the existing `mismatches` command, so the two cannot drift (FR-003). No `periods_filter`
  is passed (a document is global; the summary's attachment-id scope is what matters).
- **Alternatives considered**: a bespoke finding builder — rejected (duplication + drift risk).

## Decision: strictly read-only

- **Rationale**: FR-004. The resolver issues only `SELECT`s; the reused summary's only side effect is
  materializing page images into the ephemeral, git-ignored local cache (`.cache/analysis/`), which
  the existing `mismatches` command already does and which is not a data write. No table is mutated.

## Decision: stdlib `unittest` for the pure resolver seam

- **Rationale**: matches the existing Python test surface (`scripts/tests/`, `pnpm test:py`). The
  document→attachment resolution and the unknown-id / empty-set branching are pure given an injected
  `query`-like callable, so they are unit-testable with no D1/R2/network — the project's no-mock,
  pure-seam convention. The `summarize_mismatches` delegation is stubbed (it has its own tests).
