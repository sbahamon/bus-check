# Bus-Check

## What this project does
Analyzes CTA Frequent Network bus routes to determine:
1. Whether ridership increased after routes joined the Frequent Network
2. Whether routes actually achieve the promised 10-minute headways

## Tech stack
- Python 3.11+, managed with `uv` (NO system Python installs)
- `uv run` for all script/test execution
- `uv run pytest` for tests
- SQLite for local data cache, Cloudflare D1 for cloud collection

## Key commands
- `uv sync` — install all deps
- `uv run pytest` — run all tests (163 passing)
- `uv run pytest tests/test_ridership.py -v` — run specific test file
- `uv run python -m bus_check.collector.headway_collector` — run headway collector
- `uv pip install -e . && uv run --no-sync jupyter lab` — open notebooks
- `uv pip install -e . && uv run --no-sync jupyter execute notebooks/<NB>.ipynb --inplace` — execute a notebook

**Critical:** Always use `uv pip install -e .` before `uv run --no-sync` for Jupyter. Plain `uv run` (without `--no-sync`) re-syncs and drops the editable install, causing `ModuleNotFoundError`.

## Project layout
- `src/bus_check/config.py` — all route/phase/service-window constants
- `src/bus_check/data/` — API clients (ridership.py, bus_tracker.py, gtfs.py, db.py, d1_client.py)
- `src/bus_check/analysis/` — statistical models (ridership_analysis.py, headway_analysis.py)
- `src/bus_check/viz/` — chart generators
- `src/bus_check/collector/` — real-time Bus Tracker polling pipeline
- `tests/` — mirrors src/ structure, test-first development
- `notebooks/` — Jupyter notebooks for exploration and final output
- `worker/` — Cloudflare Worker headway collector (polls CTA every 5 min → D1)
- `scripts/` — automation scripts (collect_to_d1.py, update_headways.py)
- `site/` — static website (GitHub Pages): analysis, headways, methodology, reproducibility

## Testing conventions
- pytest with fixtures in conftest.py
- Tests written BEFORE implementation (TDD)
- Mock all external API calls (SODA, Bus Tracker) in tests
- Use `responses` library for HTTP mocking
- Test data fixtures in `tests/fixtures/`

## Environment
- `.env` for secrets (CTA_API_KEY, SOCRATA_APP_TOKEN)
- Never commit .env; .env.example has the template
- GitHub Actions secrets: CTA_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, D1_DATABASE_ID

## Headway collection (Cloudflare Worker)
The headway detection algorithm (`detect_stop_arrivals`) uses crossing+interpolation: it detects
when each vehicle's `pdist` crosses a reference point between consecutive observations and
linearly interpolates the arrival time. A 30-minute minimum gap between same-vehicle arrivals
prevents false duplicates from GPS jitter.

A Cloudflare Worker polls every 5 minutes via cron trigger, writing directly to D1 via native binding.

- `worker/src/index.js` — single-file Worker source
- `worker/wrangler.toml` — config with cron trigger + D1 binding
- Deploy: `cd worker && npx wrangler deploy`
- Logs: `cd worker && npx wrangler tail`
- Health: `curl https://bus-check-collector.sbahamon1.workers.dev/health`
- CTA_API_KEY stored as Worker secret (set via Cloudflare dashboard)
- D1 database: `bus-check-headways` (ID: `cfaca7b6-4312-4d15-b861-18851989403d`)

**Data:** D1 contains only Worker-era data (5-min polling, Feb 16, 2026 onward). Earlier
prototype data (60s local, 30min GHA) was cleaned out on Feb 17, 2026. The 60s data is
preserved locally in `data/headway.db` for algorithm validation (see `scripts/validate_algorithm.py`).

## Automated analysis (GitHub Actions)
- `.github/workflows/update-headways.yml` — daily: reads D1, updates site/headways.html, deploys to Pages
- `.github/workflows/deploy.yml` — deploys site/ to GitHub Pages on push to main
- `.github/workflows/collect-headways.yml` — OLD 30-min collector (cron disabled), kept as emergency fallback
- `src/bus_check/data/d1_client.py` — Cloudflare D1 REST API client (used by update script)

## Data sources
- Chicago Data Portal SODA API: `https://data.cityofchicago.org/resource/jyb9-n7fm.json` (ridership by route)
- CTA Bus Tracker API: `http://www.ctabustracker.com/bustime/api/v2/` (real-time vehicle positions)
- CTA GTFS: `http://www.transitchicago.com/downloads/sch_data/google_transit.zip` (scheduled service)

## Reproducing results
See `REPRODUCING.md` for step-by-step instructions to verify all findings.
Run `uv run pytest` (163 tests) and execute all 8 notebooks to confirm.
