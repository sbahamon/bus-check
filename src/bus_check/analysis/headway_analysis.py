"""Headway analysis: metrics, stop-arrival detection, and headway computation."""

import pandas as pd

from bus_check.config import is_in_service_window


def compute_headway_metrics(headways: pd.Series) -> dict:
    """Compute comprehensive headway metrics from a Series of headway values (minutes).

    Returns a dict with:
        mean_headway, median_headway, std_headway, cv_headway,
        pct_under_10, pct_under_12, pct_over_15, pct_over_20,
        max_headway, bunching_rate, excess_wait_time
    """
    n = len(headways)
    mean_h = headways.mean()
    std_h = headways.std()

    # Excess wait time: EWT = sum(h_i^2) / (2 * sum(h_i)) - mean(h_i) / 2
    sum_h = headways.sum()
    sum_h2 = (headways**2).sum()
    ewt = sum_h2 / (2 * sum_h) - mean_h / 2

    return {
        "mean_headway": mean_h,
        "median_headway": headways.median(),
        "std_headway": std_h,
        "cv_headway": std_h / mean_h if mean_h != 0 else float("inf"),
        "pct_under_10": (headways <= 10).sum() / n * 100,
        "pct_under_12": (headways <= 12).sum() / n * 100,
        "pct_over_15": (headways > 15).sum() / n * 100,
        "pct_over_20": (headways > 20).sum() / n * 100,
        "max_headway": headways.max(),
        "bunching_rate": (headways < 2).sum() / n * 100,
        "excess_wait_time": ewt,
    }


def detect_stop_arrivals(
    vehicle_positions: pd.DataFrame,
    reference_pdist: int,
    min_gap_minutes: int = 30,
) -> pd.DataFrame:
    """Detect when each vehicle crosses the reference pdist using crossing logic.

    For each vehicle, finds consecutive observation pairs where pdist transitions
    from below the reference to at-or-above it. The arrival time is linearly
    interpolated between the two bounding observations.

    Args:
        vehicle_positions: DataFrame with vid, tmstmp, pdist columns.
        reference_pdist: The pdist value of the reference point.
        min_gap_minutes: Minimum minutes between arrivals for the same vehicle
            to prevent false duplicates from GPS jitter.

    Returns:
        DataFrame with vid, arrival_time, pdist_at_arrival columns.
    """
    if vehicle_positions.empty:
        return pd.DataFrame(columns=["vid", "arrival_time", "pdist_at_arrival"])

    min_gap = pd.Timedelta(minutes=min_gap_minutes)
    arrivals = []

    for vid, group in vehicle_positions.groupby("vid"):
        group = group.sort_values("tmstmp").reset_index(drop=True)
        last_arrival_time = None

        for i in range(len(group) - 1):
            prev = group.iloc[i]
            curr = group.iloc[i + 1]

            if prev["pdist"] < reference_pdist and curr["pdist"] >= reference_pdist:
                # Crossing detected — interpolate arrival time
                denom = curr["pdist"] - prev["pdist"]
                if denom == 0:
                    continue
                fraction = (reference_pdist - prev["pdist"]) / denom
                time_diff = curr["tmstmp"] - prev["tmstmp"]
                arrival_time = prev["tmstmp"] + fraction * time_diff

                # Suppress jitter: skip if too close to last arrival for this vehicle
                if last_arrival_time is not None:
                    if arrival_time - last_arrival_time < min_gap:
                        continue

                arrivals.append(
                    {
                        "vid": vid,
                        "arrival_time": arrival_time,
                        "pdist_at_arrival": reference_pdist,
                    }
                )
                last_arrival_time = arrival_time

    if not arrivals:
        return pd.DataFrame(columns=["vid", "arrival_time", "pdist_at_arrival"])

    return pd.DataFrame(arrivals)


def compute_headways_from_arrivals(arrivals: pd.DataFrame) -> pd.Series:
    """Compute headway gaps in minutes from sorted arrival events.

    Args:
        arrivals: DataFrame with at least an 'arrival_time' column (datetime).

    Returns:
        Series of headway values in minutes (length = len(arrivals) - 1).
    """
    if len(arrivals) <= 1:
        return pd.Series(dtype=float)

    sorted_arrivals = arrivals.sort_values("arrival_time").reset_index(drop=True)
    time_diffs = sorted_arrivals["arrival_time"].diff().dropna()

    # Convert timedelta to minutes
    headways = time_diffs.dt.total_seconds() / 60.0
    return headways.reset_index(drop=True)


def filter_arrivals_to_service_window(arrivals: pd.DataFrame) -> pd.DataFrame:
    """Filter arrivals to the Frequent Network service window.

    Weekdays: 6am-9pm, Weekends: 9am-9pm.
    """
    if arrivals.empty:
        return arrivals.copy()

    times = pd.to_datetime(arrivals["arrival_time"])
    hours = times.dt.hour
    is_weekday = times.dt.dayofweek < 5
    mask = pd.Series(
        [is_in_service_window(h, wd) for h, wd in zip(hours, is_weekday)],
        index=arrivals.index,
    )
    return arrivals[mask].reset_index(drop=True)
