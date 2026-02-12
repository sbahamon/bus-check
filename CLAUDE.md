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
- `uv run pytest` — run all tests
- `uv run pytest tests/test_ridership.py -v` — run specific test file
- `uv run python -m bus_check.collector.headway_collector` — run headway collector
- `uv run jupyter lab` — open notebooks

## Project layout
- `src/bus_check/config.py` — all route/phase/service-window constants
- `src/bus_check/data/` — API clients (ridership.py, bus_tracker.py, gtfs.py, db.py)
- `src/bus_check/analysis/` — statistical models (ridership_analysis.py, headway_analysis.py)
- `src/bus_check/viz/` — chart generators
- `src/bus_check/collector/` — real-time Bus Tracker polling pipeline
- `tests/` — mirrors src/ structure, test-first development
- `notebooks/` — Jupyter notebooks for exploration and final output

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
