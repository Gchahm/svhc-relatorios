#!/usr/bin/env python3
"""
BRCondos scraper — outputs one JSON file per period, compatible with import-to-d1.mjs.

Usage:
    cd scripts
    uv run python -m scraper                     # interactive mode
    uv run python -m scraper scrape [options]     # CLI mode
    uv run python -m scraper download-docs [options]
"""

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

from .analise import run_analysis
from .analise.documentos import run_document_analysis
from .runner import run_download_docs, run_scrape

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DATA_DIR = "../data/scrape"


def _pick(prompt: str, options: list[str]) -> str:
    """Show a numbered menu and return the chosen option."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        try:
            choice = int(input("\n> "))
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except (ValueError, EOFError):
            pass
        print(f"Choose 1-{len(options)}")


def _pick_multi(prompt: str, options: list[str]) -> list[str]:
    """Show a numbered menu, allow selecting multiple (comma-separated)."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"\nEnter numbers separated by commas (e.g. 1,3,5) or 'all'")
    while True:
        try:
            raw = input("\n> ").strip()
            if raw.lower() == "all":
                return list(options)
            indices = [int(x.strip()) for x in raw.split(",")]
            if all(1 <= i <= len(options) for i in indices):
                return [options[i - 1] for i in indices]
        except (ValueError, EOFError):
            pass
        print(f"Enter comma-separated numbers (1-{len(options)}) or 'all'")


def _yes_no(prompt: str, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    try:
        answer = input(f"\n{prompt} [{hint}]: ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer.startswith("y")


def _existing_periods() -> list[str]:
    """List periods that already have JSON files."""
    data_path = Path(DATA_DIR)
    if not data_path.exists():
        return []
    return sorted(f.stem for f in data_path.glob("*.json"))


def _years_from_periods(periods: list[str]) -> list[str]:
    """Extract unique years from period strings."""
    return sorted(set(p.split("-")[0] for p in periods))


def _ask_periods(existing: list[str], action: str) -> list[str] | None:
    """Ask user which periods to process. Returns None for 'all'."""
    if action == "scrape":
        choices = ["All new periods", "Full year", "Specific periods"]
    elif action == "analyze":
        choices = ["All periods", "Full year", "Specific periods"]
    else:
        choices = ["All periods with pending docs", "Full year", "Specific periods"]

    mode = _pick("Which periods?", choices)

    if mode.startswith("All"):
        return None

    if mode == "Full year":
        if existing:
            years = _years_from_periods(existing)
            # Also suggest adjacent years
            all_years = sorted(set(years) | {str(int(max(years)) + 1)} if years else set())
        else:
            import datetime
            y = datetime.date.today().year
            all_years = [str(y - 1), str(y)]

        year = _pick("Which year?", all_years)
        return [f"{year}-{m:02d}" for m in range(1, 13)]

    # Specific periods
    if existing:
        if action == "download-docs":
            # Only show periods that have files
            selected = _pick_multi("Select periods:", existing)
        else:
            # Show existing + let them type new ones
            by_year: dict[str, list[str]] = defaultdict(list)
            for p in existing:
                by_year[p.split("-")[0]].append(p)

            print("\nExisting periods:")
            for year in sorted(by_year):
                months = ", ".join(p.split("-")[1] for p in by_year[year])
                print(f"  {year}: {months}")

            raw = input("\nEnter periods (YYYY-MM, comma-separated):\n> ").strip()
            selected = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        raw = input("\nEnter periods (YYYY-MM, comma-separated):\n> ").strip()
        selected = [p.strip() for p in raw.split(",") if p.strip()]

    return selected if selected else None


def interactive():
    """Run the scraper interactively."""
    existing = _existing_periods()
    if existing:
        print(f"Found {len(existing)} existing period(s) in {DATA_DIR}/")

    action = _pick("What would you like to do?", [
        "Scrape periods", "Download documents", "Analyze data", "Analyze documents (VLM)",
    ])

    if action == "Scrape periods":
        periods = _ask_periods(existing, "scrape")
        download_docs = _yes_no("Download documents?")

        if periods:
            print(f"\nWill scrape: {', '.join(periods)}")
        else:
            print("\nWill scrape all new periods")
        if download_docs:
            print("Will download documents")

        if not _yes_no("Proceed?", default=True):
            print("Aborted.")
            return

        asyncio.run(
            run_scrape(
                output_dir=DATA_DIR,
                periodos_filter=periods,
                download_docs=download_docs,
            )
        )

    elif action == "Download documents":
        if not existing:
            print("\nNo scraped data found. Run scrape first.")
            return

        periods = _ask_periods(existing, "download-docs")

        if periods:
            print(f"\nWill download docs for: {', '.join(periods)}")
        else:
            print("\nWill download docs for all periods with pending documents")

        if not _yes_no("Proceed?", default=True):
            print("Aborted.")
            return

        asyncio.run(
            run_download_docs(
                data_dir=DATA_DIR,
                periodos_filter=periods,
            )
        )

    elif action == "Analyze data":
        if not existing:
            print("\nNo scraped data found. Run scrape first.")
            return

        periods = _ask_periods(existing, "analyze")

        if periods:
            print(f"\nWill analyze: {', '.join(periods)}")
        else:
            print("\nWill analyze all periods")

        if not _yes_no("Proceed?", default=True):
            print("Aborted.")
            return

        run_analysis(data_dir=DATA_DIR, periods_filter=periods)

    else:  # Analyze documents (VLM)
        if not existing:
            print("\nNo scraped data found. Run scrape first.")
            return

        periods = _ask_periods(existing, "analyze")
        min_amount = None
        raw = input("\nMinimum expense amount (R$) [0]: ").strip()
        if raw:
            try:
                min_amount = float(raw)
            except ValueError:
                pass

        limit = None
        raw = input("Max documents to analyze [all]: ").strip()
        if raw:
            try:
                limit = int(raw)
            except ValueError:
                pass

        reanalyze = _yes_no("Re-analyze already analyzed docs?")

        if not _yes_no("Proceed?", default=True):
            print("Aborted.")
            return

        run_document_analysis(
            data_dir=DATA_DIR,
            periods_filter=periods,
            limit=limit,
            min_amount=min_amount,
            reanalyze=reanalyze,
        )


def main():
    # If no arguments, run interactive mode
    if len(sys.argv) == 1:
        interactive()
        return

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
        "--output-dir", "-o", default=DATA_DIR,
        help="Output directory for period JSON files (default: ../data/scrape).",
    )

    docs_parser = subparsers.add_parser("download-docs", help="Download documents for existing scraped JSON files")
    docs_parser.add_argument(
        "--periodo", type=str, nargs="*",
        help="Only download docs for these periods (e.g. 2024-12 2025-01).",
    )
    docs_parser.add_argument(
        "--data-dir", "-d", default=DATA_DIR,
        help="Directory containing period JSON files (default: ../data/scrape).",
    )

    analyze_parser = subparsers.add_parser("analyze", help="Run financial analysis on scraped data")
    analyze_parser.add_argument(
        "--periodo", type=str, nargs="*",
        help="Only analyze these periods (e.g. 2024-12 2025-01).",
    )
    analyze_parser.add_argument(
        "--data-dir", "-d", default=DATA_DIR,
        help="Directory containing period JSON files (default: ../data/scrape).",
    )

    adoc_parser = subparsers.add_parser("analyze-docs", help="Analyze document images with VLM")
    adoc_parser.add_argument(
        "--periodo", type=str, nargs="*",
        help="Only analyze these periods (e.g. 2024-12 2025-01).",
    )
    adoc_parser.add_argument(
        "--data-dir", "-d", default=DATA_DIR,
        help="Directory containing period JSON files (default: ../data/scrape).",
    )
    adoc_parser.add_argument(
        "--min-amount", type=float,
        help="Only analyze documents for entries >= this amount.",
    )
    adoc_parser.add_argument(
        "--limit", type=int,
        help="Maximum number of documents to analyze.",
    )
    adoc_parser.add_argument(
        "--reanalyze", action="store_true",
        help="Re-analyze already analyzed documents.",
    )
    adoc_parser.add_argument(
        "--document-id", type=str, nargs="*",
        help="Only analyze these document ids. Implies --reanalyze for them.",
    )
    adoc_parser.add_argument(
        "--entry-id", type=str, nargs="*",
        help="Only analyze documents for these entry ids. Implies --reanalyze for them.",
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
    elif args.command == "analyze":
        run_analysis(
            data_dir=args.data_dir,
            periods_filter=args.periodo,
        )
    elif args.command == "analyze-docs":
        run_document_analysis(
            data_dir=args.data_dir,
            periods_filter=args.periodo,
            limit=args.limit,
            min_amount=args.min_amount,
            reanalyze=args.reanalyze,
            document_ids=args.document_id,
            entry_ids=args.entry_id,
        )
    else:
        parser.print_help()
        sys.exit(1)


main()
