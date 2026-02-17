"""Validate crossing+interpolation algorithm against downsampled Era 1 data.

Reads the high-frequency (60s) Era 1 data from local SQLite, runs the crossing
algorithm at full resolution ("ground truth"), then downsamples to 5-minute
intervals and re-runs to simulate Era 3 (Worker) collection. Compares arrival
counts, headway distributions, and adherence metrics.

Usage:
    uv run python scripts/validate_algorithm.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bus_check.analysis.headway_analysis import (
    compute_headway_metrics,
    compute_headways_from_arrivals,
    detect_stop_arrivals,
    filter_arrivals_to_service_window,
)
from bus_check.config import ALL_FREQUENT_ROUTES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "headway.db"


def downsample_to_interval(positions: pd.DataFrame, interval_sec: int) -> pd.DataFrame:
    """Downsample positions to simulate a lower polling frequency.

    For each vehicle, keep observations at approximately the given interval
    by selecting every Nth row where N = interval_sec / base_interval.
    Assumes tmstmp is already parsed as datetime.
    """
    result = []
    for vid, group in positions.groupby("vid"):
        group = group.sort_values("tmstmp").reset_index(drop=True)
        if len(group) < 2:
            result.append(group)
            continue

        # Estimate base interval from median time gap
        diffs = group["tmstmp"].diff().dropna().dt.total_seconds()
        if diffs.empty or diffs.median() == 0:
            result.append(group)
            continue

        base_interval = diffs.median()
        step = max(1, round(interval_sec / base_interval))
        result.append(group.iloc[::step])

    if not result:
        return positions.iloc[:0]
    return pd.concat(result, ignore_index=True)


def analyze_route(positions: pd.DataFrame, route: str) -> dict | None:
    """Run the full analysis pipeline on positions for one route."""
    if positions.empty or "pdist" not in positions.columns:
        return None

    positions = positions.copy()
    positions["pdist"] = pd.to_numeric(positions["pdist"], errors="coerce")
    positions["tmstmp"] = pd.to_datetime(positions["tmstmp"])
    positions = positions.dropna(subset=["pdist"])

    if positions.empty:
        return None

    reference_pdist = int((positions["pdist"].min() + positions["pdist"].max()) / 2)

    arrivals = detect_stop_arrivals(positions, reference_pdist)
    if len(arrivals) < 2:
        return None

    arrivals["arrival_time"] = pd.to_datetime(arrivals["arrival_time"])
    arrivals = filter_arrivals_to_service_window(arrivals)
    if len(arrivals) < 2:
        return None

    headways = compute_headways_from_arrivals(arrivals)
    headways = headways[headways <= 120]

    if headways.empty:
        return None

    metrics = compute_headway_metrics(headways)
    return {
        "route": route,
        "arrivals": len(arrivals),
        "headways": len(headways),
        "mean": metrics["mean_headway"],
        "median": metrics["median_headway"],
        "pct_under_10": metrics["pct_under_10"],
        "pct_under_12": metrics["pct_under_12"],
    }


def main() -> int:
    if not DB_PATH.exists():
        print(f"Error: {DB_PATH} not found")
        return 1

    conn = sqlite3.connect(str(DB_PATH))

    print("Validation: Crossing+Interpolation Algorithm")
    print("=" * 70)
    print(f"Data source: {DB_PATH}")
    print(f"Method: Compare full-resolution (60s) vs downsampled (5-min)")
    print()

    full_results = []
    down_results = []

    for route in ALL_FREQUENT_ROUTES:
        positions = pd.read_sql(
            "SELECT vid, tmstmp, pdist, route, direction "
            "FROM vehicle_positions WHERE route = ? ORDER BY collected_at",
            conn,
            params=[route],
        )

        if positions.empty:
            continue

        # Parse timestamps once (stored as strings in SQLite)
        positions["tmstmp"] = pd.to_datetime(positions["tmstmp"])

        # Full resolution (60s)
        full = analyze_route(positions, route)

        # Downsampled to 5-minute intervals
        positions_5m = downsample_to_interval(positions, 300)
        down = analyze_route(positions_5m, route)

        if full:
            full_results.append(full)
        if down:
            down_results.append(down)

    conn.close()

    if not full_results:
        print("No routes produced results. Check data.")
        return 1

    # Build comparison table
    full_df = pd.DataFrame(full_results).set_index("route")
    down_df = pd.DataFrame(down_results).set_index("route")

    # Only compare routes present in both
    common = full_df.index.intersection(down_df.index)
    if common.empty:
        print("No routes with results in both resolutions.")
        return 1

    print(f"Routes analyzed: {len(common)}")
    print()

    print(f"{'Route':>5s}  {'--- 60s (ground truth) ---':^36s}  {'--- 5-min (simulated) ---':^36s}  {'Delta':>8s}")
    print(f"{'':>5s}  {'Arr':>5s} {'HW':>5s} {'Mean':>6s} {'Med':>6s} {'<=10%':>6s}  "
          f"{'Arr':>5s} {'HW':>5s} {'Mean':>6s} {'Med':>6s} {'<=10%':>6s}  {'<=10%':>8s}")
    print("-" * 100)

    deltas = []
    for route in sorted(common):
        f = full_df.loc[route]
        d = down_df.loc[route]
        delta = d["pct_under_10"] - f["pct_under_10"]
        deltas.append(delta)

        print(
            f"{route:>5s}  "
            f"{int(f['arrivals']):5d} {int(f['headways']):5d} {f['mean']:6.1f} {f['median']:6.1f} {f['pct_under_10']:5.1f}%  "
            f"{int(d['arrivals']):5d} {int(d['headways']):5d} {d['mean']:6.1f} {d['median']:6.1f} {d['pct_under_10']:5.1f}%  "
            f"{delta:+7.1f}pp"
        )

    print("-" * 100)

    # Summary statistics
    full_avg = full_df.loc[common, "pct_under_10"].mean()
    down_avg = down_df.loc[common, "pct_under_10"].mean()
    mean_delta = sum(deltas) / len(deltas)

    print(f"\n{'Average':>5s}  {'':36s}  {'':36s}  {mean_delta:+7.1f}pp")
    print(f"\nFull-resolution average adherence: {full_avg:.1f}%")
    print(f"Downsampled (5-min) average adherence: {down_avg:.1f}%")
    print(f"Mean delta (downsampled - full): {mean_delta:+.1f} percentage points")

    # Arrival detection rate
    full_total = full_df.loc[common, "arrivals"].sum()
    down_total = down_df.loc[common, "arrivals"].sum()
    detection_rate = down_total / full_total * 100 if full_total > 0 else 0
    print(f"\nArrival detection rate at 5-min: {down_total}/{full_total} = {detection_rate:.1f}%")

    # Verdict
    print()
    if abs(mean_delta) <= 5:
        print("PASS: Adherence metrics within 5pp at 5-minute resolution.")
    elif abs(mean_delta) <= 10:
        print("MARGINAL: Adherence metrics within 10pp. Acceptable for ongoing monitoring.")
    else:
        print("FAIL: Large divergence between resolutions. Algorithm may need tuning.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
