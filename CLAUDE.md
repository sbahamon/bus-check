# Bus-Check

## What this project does
Analyzes CTA Frequent Network bus routes to determine:
1. Whether ridership increased after routes joined the Frequent Network
2. Whether routes actually achieve the promised 10-minute headways

## Tech stack
- Python 3.11+, managed with `uv` (NO system Python installs)
- `uv run` for all script/test execution
- `uv run pytest` for tests
- SQLite for local data cache

## Key commands
- `uv sync` — install all deps
- `uv run pytest` — run all tests (129 passing)
- `uv run pytest tests/test_ridership.py -v` — run specific test file
- `uv run python -m bus_check.collector.headway_collector` — run headway collector
- `uv pip install -e . && uv run --no-sync jupyter lab` — open notebooks
- `uv pip install -e . && uv run --no-sync jupyter execute notebooks/<NB>.ipynb --inplace` — execute a notebook

**Critical:** Always use `uv pip install -e .` before `uv run --no-sync` for Jupyter. Plain `uv run` (without `--no-sync`) re-syncs and drops the editable install, causing `ModuleNotFoundError`.

## Project layout
- `src/bus_check/config.py` — all route/phase/service-window constants
- `src/bus_check/data/` — API clients (ridership.py, bus_tracker.py, gtfs.py, db.py)
- `src/bus_check/analysis/` — statistical models (ridership_analysis.py, headway_analysis.py)
- `src/bus_check/viz/` — chart generators
- `src/bus_check/collector/` — real-time Bus Tracker polling pipeline
- `tests/` — mirrors src/ structure, test-first development
- `notebooks/` — Jupyter notebooks for exploration and final output
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

## Data sources
- Chicago Data Portal SODA API: `https://data.cityofchicago.org/resource/jyb9-n7fm.json` (ridership by route)
- CTA Bus Tracker API: `http://www.ctabustracker.com/bustime/api/v2/` (real-time vehicle positions)
- CTA GTFS: `http://www.transitchicago.com/downloads/sch_data/google_transit.zip` (scheduled service)

## Reproducing results
See `REPRODUCING.md` for step-by-step instructions to verify all findings.
Run `uv run pytest` (129 tests) and execute all 8 notebooks to confirm.
