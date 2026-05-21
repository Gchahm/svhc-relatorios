.PHONY: scrape setup

setup:
	cd scripts && uv sync && uv run playwright install chromium

scrape:
	cd scripts && uv run python -m scraper
