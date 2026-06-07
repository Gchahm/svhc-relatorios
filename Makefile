.PHONY: scrape setup analyze docs-plan apply-extractions mismatches sync-dev sync-prod

setup:
	cd scripts && uv sync && uv run playwright install chromium

scrape:
	cd scripts && uv run python -m scraper

# Document analysis (decoupled from the scraper — no Playwright needed).
# The vision step (classify-doc-page / classify-period skills, analyze-docs agent)
# runs inside Claude Code between docs-plan and apply-extractions.
docs-plan:
	cd scripts && uv run python -m analysis docs-plan

apply-extractions:
	cd scripts && uv run python -m analysis apply-extractions

analyze:
	cd scripts && uv run python -m analysis analyze

mismatches:
	cd scripts && uv run python -m analysis mismatches

sync-dev:
	node scripts/import-to-d1.mjs

sync-prod:
	node scripts/import-to-d1.mjs --remote
