.PHONY: scrape setup analyze docs-plan apply-extractions mismatches sync-dev sync-prod kill-port

# Kill whatever process is listening on PORT (default 3000): make kill-port [PORT=3000]
PORT ?= 3000
kill-port:
	@if command -v lsof >/dev/null 2>&1; then \
		pids=$$(lsof -ti tcp:$(PORT)); \
		if [ -n "$$pids" ]; then \
			echo "Killing process(es) on port $(PORT): $$pids"; kill -9 $$pids; \
		else \
			echo "Nothing is listening on port $(PORT)"; \
		fi; \
	elif command -v fuser >/dev/null 2>&1; then \
		if fuser -k $(PORT)/tcp >/dev/null 2>&1; then \
			echo "Killed process(es) on port $(PORT)"; \
		else \
			echo "Nothing is listening on port $(PORT)"; \
		fi; \
	else \
		echo "Neither lsof nor fuser is available; cannot inspect port $(PORT)"; exit 1; \
	fi

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
