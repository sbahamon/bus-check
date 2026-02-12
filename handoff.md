# Handoff: Bus-Check Project State

## What this project does
Analyzes CTA's Frequent Network (20 bus routes promised 10-min headways) to answer:
1. Has ridership increased on Frequent Network routes?
2. Are they actually delivering 10-minute headways?

Inspired by a Bluesky post from @laurie-merrell asking exactly these questions (screenshot in project root).

## Tech stack
- Python 3.11+, managed with **uv** (never system Python)
- `uv run pytest` for tests (119 passing), `uv run jupyter lab` for notebooks
- SQLite for data cache
- Package installed in editable mode: `uv pip install -e .` then `uv run --no-sync` (MUST use `--no-sync` or `uv run` re-syncs and drops the editable install, causing `ModuleNotFoundError`)

## Running collector process
A headway collector **may still be running** — check with `ps aux | grep headway_collector | grep -v grep`.
- Data stored in: `data/headway.db`
- To start: `./run_collector.sh` (foreground) or `PYTHONPATH=src nohup .venv/bin/python -m bus_check.collector.headway_collector > data/collector.log 2>&1 &` (background)
- To check data: `sqlite3 data/headway.db "SELECT COUNT(*) as positions, COUNT(DISTINCT collected_at) as polls, COUNT(DISTINCT route) as routes FROM vehicle_positions;"`
- API key is in `.env` (CTA_API_KEY). Rate usage: ~1,800 calls/day (well within 10k limit)
- **Warning:** Don't start multiple instances — check `ps` first or you'll get duplicate data.

## The 20 Frequent Network Routes

| Phase | Launch Date | Routes | Post-data available? |
|-------|------------|--------|---------------------|
| 1 | Mar 23, 2025 | J14, 34, 47, 54, 60, 63, 79, 95 | ~8 months (strongest) |
| 2 | Summer 2025 (~Jun 15) | 4, 49, 53, 66 | ~5 months |
| 3 | Fall 2025 (~Sep 15) | 20, 55, 77, 82 | ~2 months |
| 4 | Dec 21, 2025 | 9, 12, 72, 81 | NONE (data ends Nov 30) |

**Note:** Phase 2/3 dates are approximate placeholders in `config.py`. Exact dates need confirmation from CTA press releases.

## Project structure
```
bus-check/
  CLAUDE.md              # Subagent context file
  pyproject.toml         # uv-managed, hatchling build, src layout
  .env                   # CTA_API_KEY (exists, not committed)
  run_collector.sh       # Shell wrapper to start collector

  src/bus_check/
    config.py            # Route lists, phase dates, service windows, API URLs
    data/
      ridership.py       # SODA API client: fetch_ridership, fetch_all_routes, build_ridership_cache, load_ridership
      bus_tracker.py     # CTA Bus Tracker API client (BusTrackerClient class)
      gtfs.py            # GTFS parser for scheduled headways
      db.py              # SQLite schema (ridership, vehicle_positions, stop_arrivals, reference_stops)
    analysis/
      ridership_analysis.py  # compute_yoy_change, select_control_routes, prepare_did_data
      headway_analysis.py    # compute_headway_metrics, detect_stop_arrivals, compute_headways_from_arrivals
    viz/                 # Empty — charts are inline in notebooks
    collector/
      headway_collector.py   # collect_once + run_collector (polls getvehicles every 60s)

  notebooks/
    01_ridership_exploration.ipynb  # Full 20-route YoY + pooled DiD (EXECUTED)
    02_headway_exploration.ipynb    # GTFS scheduled + observed headways (EXECUTED, ~17h data)
    03_ridership_phases_1_3.ipynb   # Phases 1-3 only, no Phase 4 (EXECUTED)
    04_ridership_without_79.ipynb   # Sensitivity: all routes minus #79 outlier (EXECUTED)
    05_ridership_share.ipynb        # FN share of total CTA ridership over time (EXECUTED)
    06_did_by_phase.ipynb           # Separate DiD per phase with bootstrap CIs (EXECUTED)
    07_did_staggered.ipynb          # Callaway-Sant'Anna staggered DiD (EXECUTED)
    08_did_regression.ipynb         # Regression DiD with route+time FE, clustered SEs (EXECUTED)

  tests/                 # 119 tests, all passing
    conftest.py          # Shared fixtures
    fixtures/            # Sample JSON + GTFS files for mocking
    test_config.py (17), test_db.py (7), test_ridership.py (21),
    test_ridership_analysis.py (31), test_bus_tracker.py (11),
    test_gtfs.py (9), test_headway_analysis.py (19), test_headway_collector.py (6)

  data/                  # gitignored (/data/ in .gitignore)
    headway.db           # Collector writes here
    gtfs/                # Downloaded GTFS feed
```

## Key results

### The headline finding
The **pooled DiD is misleading** (-4.6%) — it's an artifact of mixing treatment timing across 4 phases. When broken out by phase, **all three phases with data show positive effects**:
- Phase 1: **+428 rides/day (+5.9%)**, 95% CI [+42, +799]
- Phase 2: **+586 rides/day (+4.5%)**, 95% CI [+1, +1,271]
- Phase 3: **+665 rides/day (+6.5%)**, 95% CI [+205, +998]

### Supporting evidence
- **13/16 Phase 1-3 routes gained riders YoY** — J14 Jeffery Jump best at +26.1%
- **FN share of total ridership is growing** — +0.3 to +0.9 pp post-launch depending on phase
- **Regression DiD** (notebook 08): +136 rides/day, positive but p=0.07 (insufficient power with only 31 routes)
- **Placebo test passes** (p=0.925) — no evidence of pre-trends
- **Callaway-Sant'Anna** (notebook 07): formal staggered DiD confirms direction
- **Excluding Route 79** makes DiD worse, not better — it's not an outlier story

### Headway adherence (notebook 02, ~17 hours of data)
- **Schedule promises it:** All 20 routes schedule 97-100% of headways <= 10 min
- **Reality falls short:** Average 72.9% of observed headways <= 10 min
- Best: Route 54 (90%), Route 82 (86%), Route 79 (85%)
- Worst: Route 12 (57%), Route 95 (58%), Route 20 (61%)
- **Caveat:** Only ~17 hours of data. Need 2+ weeks for robust conclusions.

## Known issues

1. **`uv pip install -e .` + `uv run --no-sync` required for notebook execution** — Always use: `uv pip install -e . && uv run --no-sync jupyter execute <notebook> --inplace`

2. **Phase 2/3 launch dates are approximate** — config.py uses Jun 15 and Sep 15 as placeholders.

3. **Headway data is preliminary** — ~17 hours collected so far. Continue running collector for weeks.

## Pending work
- [ ] Let collector run for 2+ weeks for robust headway conclusions
- [ ] Confirm exact Phase 2/3 launch dates from CTA press releases
- [ ] Re-execute notebook 02 once more headway data is collected
- [ ] Filter observed headways to service window hours (6am-9pm weekday, 9am-9pm weekend)
- [ ] Investigate Route 47 (no arrivals detected in headway analysis)

## Uncommitted changes
Three fixes from audit feedback (not yet committed):
- `.gitignore`: `data/` → `/data/` (was excluding `src/bus_check/data/` from git)
- `pyproject.toml`: added `python-dateutil>=2.8` as explicit dependency
- `run_collector.sh`: replaced hardcoded absolute path with `cd "$(dirname "$0")"`

## Useful commands
```bash
uv run pytest -v                    # run all 119 tests
uv pip install -e . && uv run --no-sync jupyter lab  # interactive notebooks
uv pip install -e . && uv run --no-sync jupyter execute notebooks/<NB>.ipynb --inplace  # execute a notebook

# Collector
ps aux | grep headway_collector     # check if running
./run_collector.sh                  # start (foreground)
sqlite3 data/headway.db "SELECT COUNT(*), COUNT(DISTINCT collected_at), COUNT(DISTINCT route) FROM vehicle_positions;"
```

## Data sources
- Ridership SODA API: `https://data.cityofchicago.org/resource/jyb9-n7fm.json` (no auth needed)
- Bus Tracker API: `http://www.ctabustracker.com/bustime/api/v2/` (needs CTA_API_KEY in .env)
- GTFS static: `http://www.transitchicago.com/downloads/sch_data/google_transit.zip`
