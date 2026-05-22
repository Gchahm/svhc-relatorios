.PHONY: scrape setup analyze analyze-docs setup-vlm

setup:
	cd scripts && uv sync && uv run playwright install chromium

setup-vlm:
	cd scripts && uv sync --extra vlm

scrape:
	cd scripts && uv run python -m scraper

analyze:
	cd scripts && uv run python -m scraper analyze

analyze-docs:
	cd scripts && uv run python -m scraper analyze-docs
