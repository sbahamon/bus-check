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
**A headway collector is currently running as PID 86895** collecting real-time CTA Bus Tracker vehicle positions every 60 seconds.
- Data stored in: `data/headway.db`
- Started via: `PYTHONPATH=src nohup .venv/bin/python -m bus_check.collector.headway_collector > data/collector.log 2>&1 &`
- To restart if it dies: `./run_collector.sh` (or the nohup command above)
- To check status: `ps aux | grep headway_collector | grep -v grep`
- To check data: `sqlite3 data/headway.db "SELECT COUNT(*) as positions, COUNT(DISTINCT collected_at) as polls, COUNT(DISTINCT route) as routes FROM vehicle_positions;"`
- API key is in `.env` (CTA_API_KEY)
- Rate usage: ~1,800 calls/day (well within 10k limit)

## The 20 Frequent Network Routes

| Phase | Launch Date | Routes | Post-data available? |
|-------|------------|--------|---------------------|
| 1 | Mar 23, 2025 | J14, 34, 47, 54, 60, 63, 79, 95 | ~8 months (strongest) |
| 2 | Summer 2025 | 4, 49, 53, 66 | ~5 months |
| 3 | Fall 2025 | 20, 55, 77, 82 | ~2 months |
| 4 | Dec 21, 2025 | 9, 12, 72, 81 | NONE (data ends Nov 30) |

## Project structure
```
bus-check/
  CLAUDE.md              # Subagent context file (read this first)
  pyproject.toml         # uv-managed, hatchling build, src layout
  .env                   # CTA_API_KEY (exists, not committed)
  run_collector.sh       # Shell wrapper to start collector with nohup

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
    viz/                 # Empty - charts are inline in notebooks
    collector/
      headway_collector.py   # collect_once + run_collector (polls getvehicles every 60s)

  notebooks/
    01_ridership_exploration.ipynb  # Full 20-route analysis (EXECUTED, has outputs)
    02_headway_exploration.ipynb    # GTFS + headway analysis (CREATED, not yet executed - needs more collected data)
    03_ridership_phases_1_3.ipynb   # Phases 1-3 only, no Phase 4 (EXECUTED, has outputs)
    04_ridership_without_79.ipynb   # All routes minus #79 79th St outlier (EXECUTED, has outputs)
    05_ridership_share.ipynb       # FN share of total CTA ridership over time (EXECUTED, has outputs)
    06_did_by_phase.ipynb          # Separate DiD per phase with bootstrap CIs (EXECUTED, has outputs)
    07_did_staggered.ipynb         # Callaway-Sant'Anna staggered DiD (EXECUTED, has outputs)
    08_did_regression.ipynb        # Regression DiD with route+time FE, clustered SEs (EXECUTED, has outputs)

  tests/                 # 119 tests, all passing
    conftest.py          # Shared fixtures (in_memory_db, ridership_sample_df, sample_headways, etc.)
    fixtures/            # Sample JSON + GTFS files for mocking
    test_config.py       # 17 tests
    test_db.py           # 7 tests
    test_ridership.py    # 21 tests (uses `responses` library for HTTP mocking; includes TestFetchAllRoutes)
    test_ridership_analysis.py  # 31 tests
    test_bus_tracker.py  # 11 tests
    test_gtfs.py         # 9 tests
    test_headway_analysis.py    # 19 tests
    test_headway_collector.py   # 6 tests (mocks BusTrackerClient)

  data/                  # gitignored
    headway.db           # LIVE - collector is writing to this right now
    collector.log        # stdout from collector (may be empty due to Python buffering)
```

## Key results so far

### Ridership analysis (notebook 01 + 03)
- Data fetched from Chicago Data Portal SODA API: 122,084 rows, 131 routes, Jan 2023 - Nov 2025
- **13 of 16 Phase 1-3 routes gained riders YoY**
- Top gainers: J14 Jeffery Jump (+26.1%), #60 Blue Island (+13.6%), #95 95th (+12.8%)
- Notable loser: #79 79th St (-6.2%) — highest-ridership route
- **DiD estimate is NEGATIVE** even with Phase 4 excluded: -443 rides/day (-4.6%)
  - Treated routes gained +547 rides/day
  - Control routes gained +990 rides/day
  - This means the system-wide trend outpaced FN-specific gains
  - Possible explanations: control route selection bias, spillover effects, seasonal confounds, need for staggered DiD estimator (Callaway-Sant'Anna)

### Sensitivity: excluding #79 (notebook 04)
- Dropping #79 makes DiD **worse**, not better: -795 rides/day (-8.4%) vs -565 (-5.8%)
- #79 was actually helping the FN average — its large absolute ridership pulled the treated mean up
- Confirms the negative DiD is a system-wide pattern, NOT a single-route outlier story

### Ridership share (notebook 05)
- FN routes consistently gain share post-launch (small but positive across all phases with data)
- Phase 1: +0.45 pp (11.0% → 11.5%), YoY confirms +0.26 pp
- Phase 1+2: +0.69 pp (21.4% → 22.1%), YoY +0.51 pp
- Phase 1+2+3: +0.31 pp (29.7% → 30.0%), YoY +0.86 pp
- Weekday-only share tracks closely with all-day share
- Phase 4 has no post-data (SODA ends Nov 30)

### Phase-level DiD (notebook 06)
- Breaking DiD by phase **reverses the negative result** — all three phases show positive DiD
- Phase 1: +428 rides/day (+5.9%), 95% bootstrap CI [+42, +799]
- Phase 2: +586 rides/day (+4.5%), 95% bootstrap CI [+1, +1,271]
- Phase 3: +665 rides/day (+6.5%), 95% bootstrap CI [+205, +998]
- The pooled negative DiD was an artifact of mixing treatment timing

### Callaway-Sant'Anna staggered DiD (notebook 07)
- Formal staggered DiD using `csdid` package with never-treated controls
- Properly handles the 4-phase rollout without contamination
- See notebook for group-time ATTs and event study plot

### Regression DiD with fixed effects (notebook 08)
- OLS with route + month FE: +136 rides/day (p=0.071, not significant at 5%)
- Clustered SEs (route level): same point estimate, wider CI, p=0.390
- Phase-specific: Phase 2 (+386, p=0.10) and Phase 3 (+323, p=0.09) near-significant
- **Placebo test passes**: fake treatment 1 year earlier gives -17 rides/day (p=0.925) — no pre-trends
- Bottom line: positive direction consistent with phase-level analysis but insufficient power (only 31 routes)

### Headway analysis (notebook 02) — EXECUTED with ~17 hours of collected data
- **Scheduled (GTFS):** All 20 routes schedule 97-100% of headways at or under 10 min — the timetable delivers on the promise
- **Observed (Bus Tracker):** Average 72.9% of headways <= 10 min across 19 routes (route 47 had no arrivals detected)
- Best: Route 54 (90.0% <= 10 min), Route 82 (86.4%), Route 79 (84.8%)
- Worst: Route 12 (57.1%), Route 95 (58.3%), Route 20 (61.0%)
- Mean observed headway across routes ranges from 5.6 min (Route 54) to 17.4 min (Route 95)
- **Caveat:** Only ~17 hours of data — need 2+ weeks for robust conclusions. Not yet filtered to service window hours.

## Known issues / gotchas

1. **`uv pip install -e .` + `uv run --no-sync` required for notebook execution** — `uv sync` alone doesn't make the package importable by the Jupyter kernel, AND plain `uv run` re-syncs the venv which drops the editable install. Always use: `uv pip install -e . && uv run --no-sync jupyter execute <notebook> --inplace`

2. **Phase 2 and 3 exact launch dates are approximate** — config.py uses June 15 and Sept 15 as placeholders for "Summer 2025" and "Fall 2025". The exact dates should be confirmed from CTA press releases.

3. **`compute_headway_metrics` consolidated** — now lives only in `headway_analysis.py` (11 keys). Removed from `ridership_analysis.py`.

4. **`fetch_all_routes()` added to `ridership.py`** — no longer defined inline in notebooks. Notebooks 01/03 import it from the library.

5. **Multiple collector processes** — if you start the collector multiple times, you'll get duplicate data. Check with `ps aux | grep headway_collector` before starting. As of this handoff, only PID 86895 should be running.

6. **Collector log may appear empty** — Python output buffering with nohup. The collector prints "Collected N vehicle positions" each cycle but it may not flush. The data IS being written to headway.db regardless. Check with `sqlite3 data/headway.db "SELECT COUNT(*) FROM vehicle_positions;"`.

## What to do next

### Immediate
- [ ] Let the collector run for several days/weeks for robust headway conclusions
- [x] Execute notebook 02 — first run with ~17 hours of data, 19/20 routes analyzed
- [x] Investigate #79 79th St ridership decline — sensitivity analysis in notebook 04 shows dropping #79 makes DiD worse; it's not an outlier problem

### Analysis improvements
- [x] Consolidate `compute_headway_metrics` into one location
- [x] Add `fetch_all_routes()` to `ridership.py` as a proper function
- [ ] Confirm exact Phase 2 and 3 launch dates from CTA press releases
- [x] Try Callaway-Sant'Anna staggered DiD estimator — notebook 07, uses `csdid` package
- [x] Break out DiD by phase — notebook 06, all three phases show POSITIVE DiD (reverses pooled result)
- [x] Add regression-based DiD with fixed effects — notebook 08, placebo test passes, positive but not significant at 5%

### Data sources reference
- Ridership SODA API: `https://data.cityofchicago.org/resource/jyb9-n7fm.json` (no auth needed)
- Bus Tracker API: `http://www.ctabustracker.com/bustime/api/v2/` (needs CTA_API_KEY in .env)
- GTFS static: `http://www.transitchicago.com/downloads/sch_data/google_transit.zip`

### Useful commands
```bash
uv run pytest -v                    # run all 119 tests
uv pip install -e .                 # REQUIRED before notebook execution
uv run --no-sync jupyter lab        # interactive notebooks (--no-sync keeps editable install)
uv pip install -e . && uv run --no-sync jupyter execute notebooks/02_headway_exploration.ipynb --inplace  # execute headway notebook

# Collector management
./run_collector.sh                  # start (foreground)
PYTHONPATH=src nohup .venv/bin/python -m bus_check.collector.headway_collector > data/collector.log 2>&1 &  # start (background)
ps aux | grep headway_collector     # check status
sqlite3 data/headway.db "SELECT COUNT(*), COUNT(DISTINCT collected_at), COUNT(DISTINCT route) FROM vehicle_positions;"  # check data
```
