#!/usr/bin/env python3
"""
BRCondos scraper — writes each period's rows straight into Cloudflare D1 and uploads
page images to R2 (local by default, --remote for production).

Usage:
    cd scripts
    uv run python -m scraper                     # interactive mode (local)
    uv run python -m scraper scrape [options]    # CLI mode
    uv run python -m scraper download-docs [options]

Attachment analysis is a separate package — see `python -m analysis --help`.
"""

import argparse
import asyncio
import logging
import sys
from collections import defaultdict

# The scraping side (`.runner` -> `.browser` -> playwright) is imported lazily, inside
# the scrape/download-docs branches, so this module stays import-light.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Ephemeral local scratch for downloaded images before upload (repo-root .cache/, gitignored).
CACHE_DIR = "../.cache/analysis"


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
    """List periods already present in the local D1 database."""
    from common import d1

    try:
        rows = d1.query("SELECT period FROM accountability_reports", target="local")
    except Exception:
        return []
    return sorted(r["period"] for r in rows)


def _years_from_periods(periods: list[str]) -> list[str]:
    """Extract unique years from period strings."""
    return sorted(set(p.split("-")[0] for p in periods))


def _ask_periods(existing: list[str], action: str) -> list[str] | None:
    """Ask user which periods to process. Returns None for 'all'."""
    if action == "scrape":
        choices = ["All new periods", "Full year", "Specific periods"]
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
    """Run the scraper interactively (scrape / download attachments)."""
    existing = _existing_periods()
    if existing:
        print(f"Found {len(existing)} existing period(s) in the local database")

    action = _pick("What would you like to do?", ["Scrape periods", "Download attachments"])

    if action == "Scrape periods":
        periods = _ask_periods(existing, "scrape")
        download_docs = _yes_no("Download attachments?")

        if periods:
            print(f"\nWill scrape: {', '.join(periods)}")
        else:
            print("\nWill scrape all new periods")
        if download_docs:
            print("Will download attachments")

        if not _yes_no("Proceed?", default=True):
            print("Aborted.")
            return

        from .runner import run_scrape

        asyncio.run(
            run_scrape(
                target="local",
                periodos_filter=periods,
                download_docs=download_docs,
            )
        )

    else:  # Download attachments
        if not existing:
            print("\nNo scraped data found. Run scrape first.")
            return

        periods = _ask_periods(existing, "download-docs")

        if periods:
            print(f"\nWill download docs for: {', '.join(periods)}")
        else:
            print("\nWill download docs for all periods with pending attachments")

        if not _yes_no("Proceed?", default=True):
            print("Aborted.")
            return

        from .runner import run_download_docs

        asyncio.run(
            run_download_docs(
                target="local",
                periodos_filter=periods,
            )
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
        help="Download attachments attached to entries (uploaded to R2 during the run).",
    )
    scrape_parser.add_argument(
        "--remote", action="store_true",
        help="Write to the REMOTE (production) D1 + R2 instead of local.",
    )
    scrape_parser.add_argument(
        "--cache-dir", default=CACHE_DIR,
        help="Ephemeral local scratch for downloaded images before upload (default: ../.cache/analysis).",
    )

    docs_parser = subparsers.add_parser("download-docs", help="Download missing attachment images and upload to R2")
    docs_parser.add_argument(
        "--periodo", type=str, nargs="*",
        help="Only download docs for these periods (e.g. 2024-12 2025-01).",
    )
    docs_parser.add_argument(
        "--remote", action="store_true",
        help="Operate against the REMOTE (production) D1 + R2 instead of local.",
    )
    docs_parser.add_argument(
        "--cache-dir", default=CACHE_DIR,
        help="Ephemeral local scratch for downloaded images before upload (default: ../.cache/analysis).",
    )

    args = parser.parse_args()

    if args.command == "scrape":
        from .runner import run_scrape

        asyncio.run(
            run_scrape(
                target="remote" if args.remote else "local",
                book_ids=args.book_ids,
                periodos_filter=args.periodo,
                download_docs=args.download_docs,
                cache_dir=args.cache_dir,
            )
        )
    elif args.command == "download-docs":
        from .runner import run_download_docs

        asyncio.run(
            run_download_docs(
                target="remote" if args.remote else "local",
                periodos_filter=args.periodo,
                cache_dir=args.cache_dir,
            )
        )
    else:
        parser.print_help()
        sys.exit(1)


main()
