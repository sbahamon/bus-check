# Handoff: Bus-Check Project State

## What this project does
Analyzes CTA's Frequent Network (20 bus routes promised 10-min headways) to answer:
1. Has ridership increased on Frequent Network routes?
2. Are they actually delivering 10-minute headways?

Inspired by a Bluesky post from @laurie-merrell asking exactly these questions (screenshot in project root).

## Tech stack
- Python 3.11+, managed with **uv** (never system Python)
- `uv run pytest` for tests (163 passing), `uv run jupyter lab` for notebooks
- SQLite for local data cache, Cloudflare D1 for cloud headway collection
- Package installed in editable mode: `uv pip install -e .` then `uv run --no-sync` (MUST use `--no-sync` or `uv run` re-syncs and drops the editable install, causing `ModuleNotFoundError`)

## Data collection: Cloudflare Worker
Vehicle positions are collected by a **Cloudflare Worker** (`worker/`) that polls CTA Bus Tracker every 5 minutes during service hours and writes directly to D1 via native binding.

- **Worker name:** `bus-check-collector`
- **Cron:** `*/5 * * * *` (every 5 min, checks Chicago time internally)
- **D1 database:** `bus-check-headways` (ID: `cfaca7b6-4312-4d15-b861-18851989403d`)
- **Health check:** `curl https://bus-check-collector.<subdomain>.workers.dev/health`
- **Logs:** `cd worker && npx wrangler tail` (live stream)
- **Deploy:** `cd worker && npx wrangler deploy`
- **CTA_API_KEY** stored as Worker secret (set via `npx wrangler secret put CTA_API_KEY`)

**Previous collectors (no longer active):**
- Local collector (`src/bus_check/collector/headway_collector.py`) — polled every 60s, wrote to local SQLite. Ran Feb 11-13, 2026.
- GitHub Actions (`collect-headways.yml`) — polled every 30 min, wrote to D1 via REST API. Cron disabled, `workflow_dispatch` kept as emergency fallback.

## The 20 Frequent Network Routes

| Phase | Launch Date | Routes | Post-data available? |
|-------|------------|--------|---------------------|
| 1 | Mar 23, 2025 | J14, 34, 47, 54, 60, 63, 79, 95 | ~8 months (strongest) |
| 2 | Jun 15, 2025 | 4, 20, 49, 66 | ~5 months |
| 3 | Aug 17, 2025 | 53, 55, 77, 82 | ~3.5 months |
| 4 | Dec 21, 2025 | 9, 12, 72, 81 | NONE (data ends Nov 30) |

**All launch dates confirmed** from CTA press releases.

## Project structure
```
bus-check/
  CLAUDE.md              # Subagent context file
  REPRODUCING.md         # AI agent reproduction guide (machine-readable)
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
      d1_client.py       # Cloudflare D1 REST API client (used by update_headways.py)
    analysis/
      ridership_analysis.py  # compute_yoy_change, select_control_routes, prepare_did_data
      headway_analysis.py    # compute_headway_metrics, detect_stop_arrivals, compute_headways_from_arrivals
    viz/                 # Empty — charts are inline in notebooks
    collector/
      headway_collector.py   # collect_once + run_collector (polls getvehicles every 60s)

  notebooks/
    01_ridership_exploration.ipynb  # Full 20-route YoY + pooled DiD (EXECUTED)
    02_headway_exploration.ipynb    # GTFS scheduled + observed headways (EXECUTED)
    03_ridership_phases_1_3.ipynb   # Phases 1-3 only, no Phase 4 (EXECUTED)
    04_ridership_without_79.ipynb   # Sensitivity: all routes minus #79 outlier (EXECUTED)
    05_ridership_share.ipynb        # FN share of total CTA ridership over time (EXECUTED)
    06_did_by_phase.ipynb           # Separate DiD per phase with bootstrap CIs (EXECUTED)
    07_did_staggered.ipynb          # Callaway-Sant'Anna staggered DiD (EXECUTED)
    08_did_regression.ipynb         # Regression DiD with route+time FE, clustered SEs (EXECUTED)

  tests/                 # 163 tests, all passing
    conftest.py          # Shared fixtures
    fixtures/            # Sample JSON + GTFS files for mocking
    test_config.py (21), test_db.py (7), test_ridership.py (21),
    test_ridership_analysis.py (31), test_bus_tracker.py (11),
    test_gtfs.py (9), test_headway_analysis.py (29), test_headway_collector.py (6),
    test_d1_client.py (10), test_collect_to_d1.py (5), test_update_headways.py (15)

  site/                  # Static website (GitHub Pages)
    index.html           # Main analysis page
    headways.html        # Headway reality check
    methodology.html     # Full methodology writeup
    reproducibility.html # Reproducibility guide for humans
    style.css            # Shared styles
    routes.geojson       # Route geometry for map

  scripts/               # Automation scripts
    collect_to_d1.py     # Manual D1 collection (emergency fallback)
    update_headways.py   # Daily: read D1 → update site/headways.html
    validate_algorithm.py # Validate crossing algorithm vs downsampled Era 1

  worker/                # Cloudflare Worker (headway collector)
    wrangler.toml        # Worker config: cron trigger, D1 binding
    src/index.js         # Single-file Worker: poll CTA → D1
    package.json         # Minimal (wrangler dev dep only)

  data/                  # gitignored (/data/ in .gitignore)
    headway.db           # Era 1 local data (464K rows, 60s polling, for validation)
    gtfs/                # Downloaded GTFS feed
```

## Key results

### The headline finding
The **pooled DiD is misleading** (-4.6%) — it's an artifact of mixing treatment timing across 4 phases. When broken out by phase, **all three phases with data show positive effects**:
- Phase 1: **+428 rides/day (+5.9%)**, 95% CI [+42, +799]
- Phase 2: **+514 rides/day (+4.2%)**, 95% CI [+163, +832]
- Phase 3: **+1,142 rides/day (+10.4%)**, 95% CI [+213, +2,492]

### Supporting evidence
- **13/16 Phase 1-3 routes gained riders YoY** — J14 Jeffery Jump best at +26.1%
- **FN share of total ridership is growing** — +0.3 to +0.9 pp post-launch depending on phase
- **Regression DiD** (notebook 08): +236 rides/day (p=0.002 homoskedastic, p=0.22 clustered)
- **Placebo test passes** (p=0.925) — no evidence of pre-trends
- **Callaway-Sant'Anna** (notebook 07): formal staggered DiD confirms direction
- **Excluding Route 79** makes DiD worse, not better — it's not an outlier story

### Headway adherence (notebook 02, data collected continuously)
- **Schedule promises it:** All 20 routes schedule 97-100% of headways <= 10 min
- **Algorithm upgrade (Feb 17, 2026):** Switched from window-based detection to crossing+interpolation. Validated against downsampled 60s data: 94.9% arrival detection rate at 5-min polling, adherence metrics within 1.5 pp of ground truth.
- **Caveat:** Data collected every 5 min via Cloudflare Worker. Need 2+ weeks for robust conclusions.

## Known issues

1. **`uv pip install -e .` + `uv run --no-sync` required for notebook execution** — Always use: `uv pip install -e . && uv run --no-sync jupyter execute <notebook> --inplace`

2. **Headway data is preliminary** — collected every 5 min via Cloudflare Worker + D1. Need 2+ weeks for robust conclusions.

3. ~~**Sparse data gap: Feb 14-16, 2026**~~ — **RESOLVED (Feb 17, 2026).** All pre-Worker data (Eras 1 and 2) deleted from D1. D1 now contains only Worker-era data (5-min polling, Feb 16+). Era 1 data (60s local, 464K rows) preserved locally in `data/headway.db` for algorithm validation.

4. **Algorithm upgrade (Feb 17, 2026):** `detect_stop_arrivals` switched from window-based detection (±500ft tolerance) to crossing+interpolation. The old algorithm had ~80% false negative rate at 5-min polling because buses "jumped over" the 1000ft detection window between polls. The new algorithm detects when `pdist` crosses the reference point between consecutive observations and linearly interpolates the arrival time. Validated: 94.9% arrival detection rate at 5-min vs 60s ground truth, adherence within 1.5 pp.

## Reproducibility
- **For humans:** `site/reproducibility.html` — step-by-step guide on the project website
- **For AI agents:** `REPRODUCING.md` — machine-readable reproduction guide in the repo root
- All 8 notebooks are independent (each fetches data live from public SODA API). No chaining.
- Key gotcha: always `uv pip install -e . && uv run --no-sync jupyter ...`

## Pending work
- [ ] Let Worker collect for 2+ weeks for robust headway conclusions
- [x] ~~Clean up sparse Feb 14-16 data from D1~~ — Done Feb 17: Eras 1+2 deleted, D1 is Worker-only
- [x] ~~Confirm exact Phase 2/3 launch dates from CTA press releases~~ — Done: Phase 2 = Jun 15, Phase 3 = Aug 17
- [ ] Re-execute notebook 02 once more headway data is collected
- [x] ~~Filter observed headways to service window hours~~ — Done: `filter_arrivals_to_service_window()` added
- [x] ~~Investigate Route 47 (no arrivals detected)~~ — Resolved by algorithm upgrade: crossing detection finds arrivals on all 20 routes
- [x] ~~Replace GHA collector with Cloudflare Worker~~ — Done: `worker/` deployed, GHA cron disabled
- [x] ~~Fix headway detection algorithm for 5-min polling~~ — Done Feb 17: crossing+interpolation replaces window-based detection

## Uncommitted changes
Algorithm upgrade + data cleanup + documentation (Feb 17, 2026):
- `src/bus_check/analysis/headway_analysis.py`: crossing+interpolation algorithm replaces window-based detection
- `tests/test_headway_analysis.py`: 7 new tests for crossing algorithm (25 → 29 tests)
- `scripts/update_headways.py`: removed `tolerance_feet` kwarg
- `scripts/validate_algorithm.py`: NEW — downsampled validation script
- `notebooks/02_headway_exploration.ipynb`: updated algorithm call + caveats
- `site/headways.html`: updated algorithm description, collection info, limitations
- `site/methodology.html`: updated data sources, notebook 02 summary, limitations
- `CLAUDE.md`, `README.md`, `REPRODUCING.md`, `handoff.md`: updated test counts, algorithm/data descriptions
- `prompts/`: NEW — LLM consultation files (data-cleanup-consultation.md + 3 response files)

Previous audit fixes (also uncommitted):
- `.gitignore`: `data/` → `/data/` (was excluding `src/bus_check/data/` from git)
- `pyproject.toml`: added `python-dateutil>=2.8` as explicit dependency
- `run_collector.sh`: replaced hardcoded absolute path with `cd "$(dirname "$0")"`

## Useful commands
```bash
uv run pytest -v                    # run all 163 tests
uv pip install -e . && uv run --no-sync jupyter lab  # interactive notebooks
uv pip install -e . && uv run --no-sync jupyter execute notebooks/<NB>.ipynb --inplace  # execute a notebook

# Cloudflare Worker (headway collector)
cd worker && npx wrangler tail      # live logs
cd worker && npx wrangler deploy    # redeploy after changes
curl https://bus-check-collector.<subdomain>.workers.dev/health  # check status
```

## Data sources
- Ridership SODA API: `https://data.cityofchicago.org/resource/jyb9-n7fm.json` (no auth needed)
- Bus Tracker API: `http://www.ctabustracker.com/bustime/api/v2/` (needs CTA_API_KEY in .env)
- GTFS static: `http://www.transitchicago.com/downloads/sch_data/google_transit.zip`
