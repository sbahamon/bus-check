# Reproducing the Bus-Check Analysis

Instructions for AI coding assistants (Claude Code, Cursor, Copilot, etc.) to verify every finding in this project. Human-readable version: [site/reproducibility.html](https://sbahamon.github.io/bus-check/reproducibility.html).

## Prerequisites

- Python 3.11+
- `uv` (Astral's package manager) — do NOT use pip, conda, or system Python
- Internet access (notebooks fetch data live from public APIs)
- No API keys needed for ridership analysis. `CTA_API_KEY` only needed for headway collector.

## Environment Setup

```bash
uv sync
uv pip install -e .
```

## Critical: The `uv` Gotcha

- `uv run` (without `--no-sync`) re-syncs the venv and **removes** the editable install
- This causes `ModuleNotFoundError: No module named 'bus_check'`
- **Always** use `uv run --no-sync` after `uv pip install -e .`
- If you see `ModuleNotFoundError`, run `uv pip install -e .` again

## Running Tests

```bash
uv run pytest          # all 159 tests should pass
uv run pytest -v       # verbose output
```

## Running Notebooks

Individual execution:

```bash
uv pip install -e . && uv run --no-sync jupyter execute notebooks/01_ridership_exploration.ipynb --inplace
```

All at once:

```bash
uv pip install -e .
for nb in notebooks/0{1..8}_*.ipynb; do
  echo "=== Running $nb ==="
  uv run --no-sync jupyter execute "$nb" --inplace
done
```

## Notebook Reference

| Notebook | Purpose | Data Source | Key Output |
|----------|---------|-------------|------------|
| 01_ridership_exploration | 20-route YoY ridership comparison + pooled DiD | SODA API | YoY changes, pooled DiD estimate |
| 02_headway_exploration | GTFS scheduled vs. observed headway comparison | GTFS + Cloudflare D1 | Headway adherence rates |
| 03_ridership_phases_1_3 | Phase 1-3 only analysis (excludes Phase 4) | SODA API | Filtered YoY comparison |
| 04_ridership_without_79 | Sensitivity: excludes Route 79 outlier | SODA API | Robustness check |
| 05_ridership_share | FN share of total CTA ridership over time | SODA API | Share trend lines |
| 06_did_by_phase | Phase-level DiD with bootstrap CIs | SODA API | **Main finding**: P1 +428, P2 +514, P3 +1,142 |
| 07_did_staggered | Callaway-Sant'Anna staggered DiD | SODA API | ATT estimate |
| 08_did_regression | OLS with route+time FE, clustered SEs, placebo | SODA API | Regression DiD, placebo test |

## Expected Results to Verify

Key numbers that notebook outputs should match:

- **Phase 1 DiD**: +428 rides/day (+5.9%), 95% CI [+42, +799]
- **Phase 2 DiD**: +514 rides/day (+4.2%), 95% CI [+163, +832]
- **Phase 3 DiD**: +1,142 rides/day (+10.4%), 95% CI [+213, +2,492]
- **J14 Jeffery Jump YoY**: +26.1%
- **13 of 16** Phase 1-3 routes gained riders YoY
- **Placebo test p-value**: 0.925 (no pre-trends)
- **Regression DiD**: +236/day (p=0.002 homoskedastic, p=0.22 clustered)

## Data Sources

- **Ridership**: `https://data.cityofchicago.org/resource/jyb9-n7fm.json` (public SODA API, no auth)
- **GTFS**: `http://www.transitchicago.com/downloads/sch_data/google_transit.zip` (auto-downloaded)
- **Bus Tracker**: `http://www.ctabustracker.com/bustime/api/v2/` (needs CTA_API_KEY)

## What You CAN'T Reproduce from a Fresh Clone

- Observed headway data — collected by a Cloudflare Worker (`worker/`) that polls CTA Bus Tracker every 5 min and writes to Cloudflare D1. For local reproduction, run the local collector (`uv run python -m bus_check.collector.headway_collector`) with a `CTA_API_KEY` in `.env`.
- Notebook 02's observed headway charts (skip these, or run the local collector first)
- Exact numbers may drift slightly if Chicago updates the SODA dataset

## Project Structure

```
src/bus_check/
  config.py          # Route lists, phase dates, service windows — START HERE
  data/              # API clients (ridership.py, bus_tracker.py, gtfs.py, db.py, d1_client.py)
  analysis/          # Statistical models (ridership_analysis.py, headway_analysis.py)
  collector/         # Local Bus Tracker polling (writes to SQLite)
notebooks/           # 8 analysis notebooks
tests/               # 159 tests (pytest + responses HTTP mocking)
site/                # Static website (GitHub Pages)
worker/              # Cloudflare Worker: polls CTA every 5 min → D1 (live data collection)
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'bus_check'` | Run `uv pip install -e .` then use `uv run --no-sync` |
| `uv run` drops the editable install | Always use `uv run --no-sync` after editable install |
| Notebook 02 fails on observed headways | Expected without headway data — run the local collector (`uv run python -m bus_check.collector.headway_collector`) or skip |
| SODA API rate limit | Wait and retry; notebooks have no auth requirement |
| Test failures | Run `uv sync` first, then `uv run pytest` |
