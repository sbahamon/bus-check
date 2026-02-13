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
    tolerance_feet: int = 200,
) -> pd.DataFrame:
    """Detect when each vehicle crosses the reference stop pdist.

    For each vehicle in the position time series, finds the first position
    where pdist falls within (reference_pdist - tolerance, reference_pdist + tolerance)
    after having been below reference_pdist - tolerance.

    Args:
        vehicle_positions: DataFrame with vid, tmstmp, pdist, rt columns.
        reference_pdist: The pdist value of the reference stop.
        tolerance_feet: How close (in feet) a vehicle must be to count as arrived.

    Returns:
        DataFrame with vid, arrival_time, pdist_at_arrival columns.
    """
    lower = reference_pdist - tolerance_feet
    upper = reference_pdist + tolerance_feet

    arrivals = []

    for vid, group in vehicle_positions.groupby("vid"):
        group = group.sort_values("tmstmp").reset_index(drop=True)

        # Track whether the vehicle was ever below the lower bound
        was_before_stop = False
        detected = False

        for _, row in group.iterrows():
            pdist = row["pdist"]

            if pdist < lower:
                was_before_stop = True

            if was_before_stop and not detected and lower <= pdist <= upper:
                arrivals.append(
                    {
                        "vid": vid,
                        "arrival_time": row["tmstmp"],
                        "pdist_at_arrival": pdist,
                    }
                )
                detected = True

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
