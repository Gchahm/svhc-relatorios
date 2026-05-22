.PHONY: scrape setup analyze

setup:
	cd scripts && uv sync && uv run playwright install chromium

scrape:
	cd scripts && uv run python -m scraper

analyze:
	cd scripts && uv run python -m scraper analyze
