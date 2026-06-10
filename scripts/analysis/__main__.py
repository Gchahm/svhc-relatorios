#!/usr/bin/env python3
"""Analysis CLI — ``python -m analysis <command>``.

Decoupled from the scraper: imports only the stdlib analysis pipeline, never the
Playwright scraping stack. Commands: docs-plan, apply-extractions, analyze,
mismatches (see specs/008-decouple-analysis-scripts/contracts/analysis-cli.md);
record-verdict, loop-state (the self-improving loop's bookkeeping — see
specs/007-classification-improve-loop/contracts/verdict-cli.md).
"""

import argparse
import json
import logging
import sys

from . import run_analysis
from .extractions import apply_extractions, plan_extractions, summarize_mismatches
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

# Ephemeral local scratch (materialized R2 images + manifests/verdicts); repo-root, gitignored.
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

    p = sub.add_parser("docs-plan", help="Plan attachment extraction: write <period>.extract-todo.json (cache)")
    _add_common(p)
    p.add_argument("--min-amount", type=float, help="Only plan attachments for entries >= this amount.")
    p.add_argument("--limit", type=int, help="Maximum number of attachments to plan.")
    p.add_argument("--reanalyze", action="store_true", help="Re-plan already analyzed attachments.")
    p.add_argument("--attachment-id", type=str, nargs="*", help="Only these attachment ids (implies re-analysis).")
    p.add_argument("--entry-id", type=str, nargs="*", help="Only attachments for these entry ids (implies re-analysis).")

    p = sub.add_parser("apply-extractions", help="Merge per-page <image>.classify.json into attachment_analyses (D1)")
    _add_common(p)

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
    p.add_argument("--attachment-id", type=str, nargs="*", help="Scope the join to these attachment ids.")
    p.add_argument("--entry-id", type=str, nargs="*", help="Scope the join to these entry ids.")

    args = parser.parse_args(argv)
    target = "remote" if getattr(args, "remote", False) else "local"

    if args.command == "docs-plan":
        plan_extractions(
            target=target,
            periods_filter=args.periodo,
            cache_dir=args.cache_dir,
            min_amount=args.min_amount,
            limit=args.limit,
            reanalyze=args.reanalyze,
            attachment_ids=args.attachment_id,
            entry_ids=args.entry_id,
        )
    elif args.command == "apply-extractions":
        apply_extractions(target=target, periods_filter=args.periodo, cache_dir=args.cache_dir)
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
            attachment_ids=args.attachment_id,
            entry_ids=args.entry_id,
        )
        print(json.dumps(state, ensure_ascii=False, indent=2))


main()
