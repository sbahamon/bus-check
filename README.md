# Bus-Check: CTA Frequent Network Analysis

Did CTA's Frequent Network actually boost ridership? Are the promised 10-minute headways real?

This project analyzes Chicago's 20 Frequent Network bus routes using ridership data from the Chicago Data Portal and real-time vehicle positions from the CTA Bus Tracker API.

## Key Findings

**Ridership is up.** A naive pooled difference-in-differences suggests a -4.6% effect, but that's an artifact of mixing four rollout phases with different treatment windows. Phase-level DiD tells a different story — all three phases with post-launch data show positive effects:

| Phase | Launch | Routes | DiD Estimate | 95% CI |
|-------|--------|--------|-------------|--------|
| 1 | Mar 2025 | J14, 34, 47, 54, 60, 63, 79, 95 | +428 rides/day (+5.9%) | [+42, +799] |
| 2 | Jun 2025 | 4, 20, 49, 66 | +514 rides/day (+4.2%) | [+163, +832] |
| 3 | Aug 2025 | 53, 55, 77, 82 | +1,142 rides/day (+10.4%) | [+213, +2,492] |

13 of 16 Phase 1-3 routes gained riders year-over-year. J14 Jeffery Jump led with +26.1%.

**Headways fall short of the promise.** All 20 routes schedule 97-100% of headways at 10 minutes or less. In practice, only about 59% of observed headways meet that bar during service window hours (based on ~45 hours of collected data — more collection needed).

## Notebooks

| # | Notebook | What it does |
|---|----------|-------------|
| 01 | `ridership_exploration` | Full 20-route year-over-year comparison + pooled DiD |
| 02 | `headway_exploration` | GTFS scheduled vs. observed headways |
| 03 | `ridership_phases_1_3` | Phases 1-3 only (excludes Phase 4 with no post-data) |
| 04 | `ridership_without_79` | Sensitivity test excluding Route 79 outlier |
| 05 | `ridership_share` | FN share of total CTA bus ridership over time |
| 06 | `did_by_phase` | Separate DiD per phase with bootstrap confidence intervals |
| 07 | `did_staggered` | Callaway-Sant'Anna staggered DiD |
| 08 | `did_regression` | OLS with route + time fixed effects, clustered SEs, placebo test |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                    # install dependencies
uv run pytest              # run tests (129 passing)
uv pip install -e .        # required before running notebooks
uv run --no-sync jupyter lab  # open notebooks
```

To collect real-time headway data, you need a CTA Bus Tracker API key in `.env`:

```
CTA_API_KEY=your_key_here
```

Then start the collector:

```bash
./run_collector.sh
```

## Reproducing the Analysis

Every finding on the [project website](https://steffanybahamon.github.io/bus-check/) can be independently verified by running the 8 analysis notebooks. See [`REPRODUCING.md`](REPRODUCING.md) for detailed step-by-step instructions.

**Using an AI coding assistant?** `REPRODUCING.md` is written to be machine-readable — point your AI tool at it and it can walk through the entire reproduction process.

**Website:** The [reproducibility page](https://steffanybahamon.github.io/bus-check/reproducibility.html) has the same guide in a more readable format.

## Data Sources

- **Ridership:** [Chicago Data Portal SODA API](https://data.cityofchicago.org/resource/jyb9-n7fm.json) (no auth needed)
- **Real-time positions:** [CTA Bus Tracker API](http://www.ctabustracker.com/bustime/api/v2/) (requires API key)
- **Schedules:** [CTA GTFS feed](http://www.transitchicago.com/downloads/sch_data/google_transit.zip)

## Project Structure

```
src/bus_check/
  config.py          # Route lists, phase dates, service windows
  data/              # API clients (ridership, bus tracker, GTFS, SQLite)
  analysis/          # Statistical models (ridership DiD, headway metrics)
  collector/         # Real-time Bus Tracker polling pipeline
notebooks/           # Jupyter notebooks (all executed with outputs)
tests/               # 129 tests — pytest with HTTP mocking via responses
```
