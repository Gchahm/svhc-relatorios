#!/usr/bin/env python3
"""
BRCondos scraper — outputs one JSON file per period, compatible with import-to-d1.mjs.

Usage:
    cd scripts
    uv run --with playwright --with python-dotenv -- python -m scraper scrape [options]
    uv run --with playwright --with python-dotenv -- python -m scraper download-docs [options]
"""

import argparse
import asyncio
import logging
import sys

from .runner import run_download_docs, run_scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="BRCondos fiscal data scraper")
    subparsers = parser.add_subparsers(dest="command")

    scrape_parser = subparsers.add_parser("scrape", help="Scrape accountability data to JSON")
    scrape_parser.add_argument(
        "--periodo", type=str, nargs="*",
        help="Periods to scrape in YYYY-MM format (e.g. 2026-01 2025-12).",
    )
    scrape_parser.add_argument(
        "--book-ids", type=int, nargs="*",
        help="Specific BRCondos accountability_book_ids to scrape.",
    )
    scrape_parser.add_argument(
        "--download-docs", action="store_true",
        help="Download documents attached to entries.",
    )
    scrape_parser.add_argument(
        "--output-dir", "-o", default="../data/scrape",
        help="Output directory for period JSON files (default: ../data/scrape).",
    )

    docs_parser = subparsers.add_parser("download-docs", help="Download documents for existing scraped JSON files")
    docs_parser.add_argument(
        "--periodo", type=str, nargs="*",
        help="Only download docs for these periods (e.g. 2024-12 2025-01).",
    )
    docs_parser.add_argument(
        "--data-dir", "-d", default="../data/scrape",
        help="Directory containing period JSON files (default: ../data/scrape).",
    )

    args = parser.parse_args()

    if args.command == "scrape":
        asyncio.run(
            run_scrape(
                output_dir=args.output_dir,
                book_ids=args.book_ids,
                periodos_filter=args.periodo,
                download_docs=args.download_docs,
            )
        )
    elif args.command == "download-docs":
        asyncio.run(
            run_download_docs(
                data_dir=args.data_dir,
                periodos_filter=args.periodo,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


main()
