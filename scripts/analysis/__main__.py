#!/usr/bin/env python3
"""Analysis CLI — ``python -m analysis <command>``.

Decoupled from the scraper: imports only the stdlib analysis pipeline, never the
Playwright scraping stack. Commands: docs-plan, record-classification, apply-extractions,
mark-pending, analyze, mismatches, document-evidence (the document→attachment(s) triage evidence
resolver — see specs/051-document-evidence-resolver/contracts/document-evidence-cli.md;
see also specs/008-decouple-analysis-scripts/contracts/analysis-cli.md
and specs/017-classify-to-d1/contracts/record-classification-cli.md); record-verdict,
loop-state (the self-improving loop's bookkeeping — see
specs/007-classification-improve-loop/contracts/verdict-cli.md).
"""

import argparse
import json
import logging
import sys

from . import run_analysis
from .corrections import apply_correction, list_corrections, undo_correction
from .documents import DocumentNotFound, build_documents, document_evidence
from .extractions import apply_extractions, mark_pending, plan_extractions, summarize_mismatches
from .page_classifications import record_classification
from .verdicts import (
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_NO_PROGRESS_WINDOW,
    loop_state,
    record_verdict,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Ephemeral local scratch (materialized R2 images + per-page classifications/verdicts); repo-root, gitignored.
CACHE_DIR = "../.cache/analysis"


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--periodo", type=str, nargs="*", help="Periods in YYYY-MM (default: all).")
    p.add_argument("--remote", action="store_true", help="Read/write the REMOTE (production) D1/R2 instead of local.")
    p.add_argument("--cache-dir", default=CACHE_DIR, help="Ephemeral local scratch dir (default: ../.cache/analysis).")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m analysis",
        description="SVHC fiscal attachment analysis (decoupled from the scraper).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("docs-plan", help="Print the DB-derived extraction plan as JSON to stdout (no manifest file)")
    _add_common(p)
    # Selection is DB-controlled: the plan is the PENDING set (classified_at IS NULL).
    # To (re)classify specific attachments, mark them pending in D1 (`mark-pending`),
    # not via id flags here. --min-amount/--limit are orthogonal filters on the pending set.
    p.add_argument("--min-amount", type=float, help="Only plan pending attachments for entries >= this amount.")
    p.add_argument("--limit", type=int, help="Maximum number of pending attachments to plan.")

    p = sub.add_parser("apply-extractions", help="Merge per-page classifications (D1 page_classifications) into attachment_analyses (D1)")
    _add_common(p)
    # Same DB-controlled selection as docs-plan (the pending set); mark-pending controls scope.
    p.add_argument("--min-amount", type=float, help="Only apply pending attachments for entries >= this amount.")
    p.add_argument("--limit", type=int, help="Maximum number of pending attachments to apply.")

    p = sub.add_parser(
        "record-classification",
        help="Record ONE page's extraction into the page_classifications staging table (D1)",
    )
    p.add_argument("--attachment-id", required=True, help="Attachment the page belongs to (plan representative id).")
    p.add_argument("--page", dest="page_label", required=True, help="Page label (e.g. p1, page2) from the plan page.")
    p.add_argument("--page-index", type=int, help="0-based page index from the plan page (stored for reference).")
    p.add_argument(
        "--json",
        dest="payload_json",
        help="Extraction as a JSON string (fields object or {\"error\": ...}). Omit or '-' to read stdin.",
    )
    p.add_argument("--remote", action="store_true", help="Write the REMOTE (production) D1 instead of local.")

    p = sub.add_parser("mark-pending", help="Clear classified_at (re-queue attachments for classification) — SQL-controlled scope")
    p.add_argument("--periodo", type=str, help="Period YYYY-MM (for logging; ids are globally unique).")
    p.add_argument("--remote", action="store_true", help="Write the REMOTE (production) D1 instead of local.")
    p.add_argument("--attachment-id", type=str, nargs="*", help="Re-queue these attachment ids.")
    p.add_argument("--entry-id", type=str, nargs="*", help="Re-queue attachments for these entry ids.")

    p = sub.add_parser(
        "build-documents",
        help="Build the global documents entity + entry links from attachment_analyses (D1)",
    )
    # Intentionally GLOBAL — no --periodo: documents dedup across all periods.
    p.add_argument("--remote", action="store_true", help="Write the REMOTE (production) D1 instead of local.")

    p = sub.add_parser(
        "document-evidence",
        help="Resolve a document id to its source attachment(s) and print scoped findings + page_refs (read-only)",
    )
    # GLOBAL — no --periodo: a document is not period-scoped (it dedups across all periods).
    p.add_argument("--id", dest="document_id", required=True, help="Document id (as shown by the UI/alert).")
    p.add_argument("--remote", action="store_true", help="Read the REMOTE (production) D1 instead of local.")
    p.add_argument("--cache-dir", default=CACHE_DIR, help="Ephemeral local scratch dir (default: ../.cache/analysis).")

    p = sub.add_parser("analyze", help="Run financial/consistency/fraud checks; write alerts to D1")
    _add_common(p)

    p = sub.add_parser("mismatches", help="Print a terse JSON summary of classification mismatches")
    _add_common(p)
    p.add_argument("--attachment-id", type=str, nargs="*", help="Scope to these attachment ids.")
    p.add_argument("--entry-id", type=str, nargs="*", help="Scope to these entry ids.")

    p = sub.add_parser("record-verdict", help="Record one review verdict into <period>.verdicts.json (cache)")
    p.add_argument("--periodo", type=str, required=True, help="Period YYYY-MM.")
    p.add_argument("--cache-dir", default=CACHE_DIR, help="Ephemeral local scratch dir (default: ../.cache/analysis).")
    p.add_argument("--iteration", type=int, required=True, help="Loop iteration (>=1) this verdict belongs to.")
    p.add_argument("--json", dest="verdict_json", required=True, help="Verdict object as JSON (from review-mismatch).")
    p.add_argument("--fix-branch", help="Attach a FixProposal: branch name.")
    p.add_argument("--fix-pr", help="Attach a FixProposal: PR url.")
    p.add_argument("--fix-status", choices=["pr-open", "failed"], help="Attach a FixProposal: status (never 'merged').")
    p.add_argument("--fix-summary", help="Attach a FixProposal: one-line summary.")

    p = sub.add_parser("loop-state", help="Recompute & print the deterministic loop state for a period")
    p.add_argument("--periodo", type=str, required=True, help="Period YYYY-MM.")
    p.add_argument("--remote", action="store_true", help="Read the REMOTE (production) D1 instead of local.")
    p.add_argument("--cache-dir", default=CACHE_DIR, help="Ephemeral local scratch dir (default: ../.cache/analysis).")
    p.add_argument("--iteration", type=int, help="Iteration to record (default: infer next).")
    p.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS, help="Max-iteration cap (default 3).")
    p.add_argument(
        "--no-progress-window", type=int, default=DEFAULT_NO_PROGRESS_WINDOW,
        help="Consecutive-iteration window for the no-progress guard (default 2).",
    )

    p = sub.add_parser(
        "apply-correction",
        help="Record + apply one data correction to an attachment, gated by verify-after (TRIAGE-003)",
    )
    p.add_argument("--attachment-id", required=True, help="Attachment to correct (plan representative id).")
    p.add_argument("--target-finding", required=True, help="mismatch_key of the finding the correction should clear.")
    p.add_argument(
        "--pages",
        dest="pages_json",
        help='Corrected per-page extraction(s) as JSON: {"<page_label>": <fields-object>}. Omit or "-" to read stdin.',
    )
    p.add_argument("--evidence", help="Page image read_path the decision was based on (recorded with each row).")
    p.add_argument("--agent", default=None, help="Acting agent id (default: triage-agent).")
    p.add_argument("--cache-dir", default=CACHE_DIR, help="Ephemeral local scratch dir (default: ../.cache/analysis).")
    p.add_argument("--remote", action="store_true", help="Write the REMOTE (production) D1 instead of local.")

    p = sub.add_parser("list-corrections", help="List recorded data corrections, optionally scoped (read-only)")
    p.add_argument("--attachment-id", type=str, nargs="*", help="Scope to these attachment ids.")
    p.add_argument("--periodo", type=str, help="Scope to this period (YYYY-MM).")
    p.add_argument("--status", choices=["applied", "rolled-back", "flagged", "reverted"], help="Scope to a status.")
    p.add_argument("--remote", action="store_true", help="Read the REMOTE (production) D1 instead of local.")

    p = sub.add_parser("undo-correction", help="Reverse a previously-applied data correction (restore + re-derive)")
    p.add_argument("--id", dest="correction_id", required=True, help="A correction row id OR a batch_id (reverses the whole batch).")
    p.add_argument("--actor", default=None, help="Who is performing the undo (default: human).")
    p.add_argument("--cache-dir", default=CACHE_DIR, help="Ephemeral local scratch dir (default: ../.cache/analysis).")
    p.add_argument("--remote", action="store_true", help="Write the REMOTE (production) D1 instead of local.")

    args = parser.parse_args(argv)
    target = "remote" if getattr(args, "remote", False) else "local"

    if args.command == "docs-plan":
        plan_extractions(
            target=target,
            periods_filter=args.periodo,
            cache_dir=args.cache_dir,
            min_amount=args.min_amount,
            limit=args.limit,
        )
    elif args.command == "apply-extractions":
        apply_extractions(
            target=target,
            periods_filter=args.periodo,
            cache_dir=args.cache_dir,
            min_amount=args.min_amount,
            limit=args.limit,
        )
    elif args.command == "record-classification":
        raw = args.payload_json
        if raw is None or raw == "-":
            raw = sys.stdin.read()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"error: extraction is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            from .typed_gate import validate_typed

            record_classification(
                args.attachment_id,
                args.page_label,
                payload,
                page_index=args.page_index,
                target=target,
                typed_validator=validate_typed,
            )
        except ValueError as e:
            print(f"error: classification rejected: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Recorded classification for {args.attachment_id} {args.page_label}.")
    elif args.command == "mark-pending":
        n = mark_pending(
            target=target,
            period=args.periodo,
            attachment_ids=args.attachment_id,
            entry_ids=args.entry_id,
        )
        print(f"Marked {n} id(s) pending (classified_at = NULL).")
    elif args.command == "build-documents":
        n_docs, n_links = build_documents(target=target)
        print(f"Built {n_docs} document(s) with {n_links} entry link(s).")
    elif args.command == "document-evidence":
        try:
            result = document_evidence(args.document_id, target=target, cache_dir=args.cache_dir)
        except DocumentNotFound:
            print(f"error: document not found: {args.document_id}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "analyze":
        run_analysis(target=target, periods_filter=args.periodo, cache_dir=args.cache_dir)
    elif args.command == "mismatches":
        rows = summarize_mismatches(
            target=target,
            periods_filter=args.periodo,
            cache_dir=args.cache_dir,
            attachment_ids=args.attachment_id,
            entry_ids=args.entry_id,
        )
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif args.command == "record-verdict":
        try:
            verdict_obj = json.loads(args.verdict_json)
        except json.JSONDecodeError as e:
            print(f"error: --json is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        fix = None
        if any([args.fix_branch, args.fix_pr, args.fix_status, args.fix_summary]):
            fix = {
                "branch": args.fix_branch,
                "pr_url": args.fix_pr,
                "status": args.fix_status,
                "summary": args.fix_summary,
            }
        try:
            record_verdict(
                cache_dir=args.cache_dir,
                period=args.periodo,
                iteration=args.iteration,
                verdict_obj=verdict_obj,
                fix=fix,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Recorded verdict for {verdict_obj.get('mismatch_key')} (iteration {args.iteration}).")
    elif args.command == "loop-state":
        state = loop_state(
            target=target,
            period=args.periodo,
            cache_dir=args.cache_dir,
            iteration=args.iteration,
            max_iterations=args.max_iterations,
            no_progress_window=args.no_progress_window,
        )
        print(json.dumps(state, ensure_ascii=False, indent=2))
    elif args.command == "apply-correction":
        raw = args.pages_json
        if raw is None or raw == "-":
            raw = sys.stdin.read()
        try:
            corrected_pages = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"error: --pages is not valid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        if not isinstance(corrected_pages, dict):
            print('error: --pages must be a JSON object {"<page_label>": <fields>}', file=sys.stderr)
            sys.exit(1)
        try:
            result = apply_correction(
                args.attachment_id,
                args.target_finding,
                corrected_pages,
                evidence=args.evidence,
                agent=args.agent or "triage-agent",
                target=target,
                cache_dir=args.cache_dir,
            )
        except ValueError as e:
            print(f"error: correction rejected: {e}", file=sys.stderr)
            sys.exit(1)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("result") not in ("applied", "no-op"):
            sys.exit(1)
    elif args.command == "list-corrections":
        rows = list_corrections(
            attachment_ids=args.attachment_id,
            period=args.periodo,
            status=args.status,
            target=target,
        )
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif args.command == "undo-correction":
        result = undo_correction(
            args.correction_id,
            actor=args.actor or "human",
            target=target,
            cache_dir=args.cache_dir,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("result") != "reverted":
            sys.exit(1)


main()
