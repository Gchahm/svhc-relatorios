#!/usr/bin/env python3
"""Analysis CLI — ``python -m analysis <command>``.

Decoupled from the scraper: imports only the stdlib analysis pipeline, never the
Playwright scraping stack. Commands: docs-plan, apply-extractions, analyze,
mismatches (see specs/008-decouple-analysis-scripts/contracts/analysis-cli.md).
"""

import argparse
import json
import logging

from . import run_analysis
from .extractions import apply_extractions, plan_extractions, summarize_mismatches

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DATA_DIR = "../data/scrape"


def _add_periodo_datadir(p: argparse.ArgumentParser) -> None:
    p.add_argument("--periodo", type=str, nargs="*", help="Periods in YYYY-MM (default: all).")
    p.add_argument(
        "--data-dir", "-d", default=DATA_DIR,
        help="Directory containing period JSON files (default: ../data/scrape).",
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m analysis",
        description="SVHC fiscal document analysis (decoupled from the scraper).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("docs-plan", help="Plan document extraction: write <period>.extract-todo.json")
    _add_periodo_datadir(p)
    p.add_argument("--min-amount", type=float, help="Only plan documents for entries >= this amount.")
    p.add_argument("--limit", type=int, help="Maximum number of documents to plan.")
    p.add_argument("--reanalyze", action="store_true", help="Re-plan already analyzed documents.")
    p.add_argument("--document-id", type=str, nargs="*", help="Only these document ids (implies re-analysis).")
    p.add_argument("--entry-id", type=str, nargs="*", help="Only documents for these entry ids (implies re-analysis).")

    p = sub.add_parser("apply-extractions", help="Merge per-page <image>.classify.json into period JSON")
    _add_periodo_datadir(p)

    p = sub.add_parser("analyze", help="Run financial/consistency/fraud checks; write alerts")
    _add_periodo_datadir(p)

    p = sub.add_parser("mismatches", help="Print a terse JSON summary of classification mismatches")
    _add_periodo_datadir(p)
    p.add_argument("--document-id", type=str, nargs="*", help="Scope to these document ids.")
    p.add_argument("--entry-id", type=str, nargs="*", help="Scope to these entry ids.")

    args = parser.parse_args(argv)

    if args.command == "docs-plan":
        plan_extractions(
            data_dir=args.data_dir,
            periods_filter=args.periodo,
            min_amount=args.min_amount,
            limit=args.limit,
            reanalyze=args.reanalyze,
            document_ids=args.document_id,
            entry_ids=args.entry_id,
        )
    elif args.command == "apply-extractions":
        apply_extractions(data_dir=args.data_dir, periods_filter=args.periodo)
    elif args.command == "analyze":
        run_analysis(data_dir=args.data_dir, periods_filter=args.periodo)
    elif args.command == "mismatches":
        rows = summarize_mismatches(
            data_dir=args.data_dir,
            periods_filter=args.periodo,
            document_ids=args.document_id,
            entry_ids=args.entry_id,
        )
        print(json.dumps(rows, ensure_ascii=False, indent=2))


main()
