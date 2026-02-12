"""Ridership analysis: YoY change, DiD preparation, control selection, headway metrics."""

from datetime import date
from dateutil.relativedelta import relativedelta

import pandas as pd


def compute_yoy_change(
    df: pd.DataFrame,
    route: str,
    launch_date: date,
    months_window: int = 3,
) -> dict:
    """Compute year-over-year ridership change for a route.

    Compares average weekday ridership in the `months_window` months after
    `launch_date` versus the same period one year prior.

    Args:
        df: Ridership DataFrame with columns: route, date, daytype, rides.
        route: Route identifier string.
        launch_date: Date the route joined the Frequent Network.
        months_window: Number of months after launch_date to analyze.

    Returns:
        Dict with keys: route, pre_avg, post_avg, abs_change, pct_change.
    """
    route_df = df[df["route"] == route].copy()

    # Post period: launch_date to launch_date + months_window months
    post_start = pd.Timestamp(launch_date)
    post_end = pd.Timestamp(launch_date + relativedelta(months=months_window))

    # Pre period: same window one year prior
    pre_start = pd.Timestamp(launch_date - relativedelta(years=1))
    pre_end = pd.Timestamp(launch_date - relativedelta(years=1) + relativedelta(months=months_window))

    # Filter to weekday only (daytype == "W")
    weekday = route_df[route_df["daytype"] == "W"]

    pre_data = weekday[
        (weekday["date"] >= pre_start) & (weekday["date"] < pre_end)
    ]
    post_data = weekday[
        (weekday["date"] >= post_start) & (weekday["date"] < post_end)
    ]

    pre_avg = pre_data["rides"].mean() if len(pre_data) > 0 else 0.0
    post_avg = post_data["rides"].mean() if len(post_data) > 0 else 0.0

    abs_change = post_avg - pre_avg
    pct_change = abs_change / pre_avg if pre_avg != 0 else 0.0

    return {
        "route": route,
        "pre_avg": pre_avg,
        "post_avg": post_avg,
        "abs_change": abs_change,
        "pct_change": pct_change,
    }


def select_control_routes(
    df: pd.DataFrame,
    treated_routes: list[str],
    n_controls: int = 15,
) -> list[str]:
    """Select control routes by matching on average pre-treatment weekday ridership.

    Computes the average weekday ridership across treated routes, then ranks
    all other routes by how close their average weekday ridership is.

    Args:
        df: Ridership DataFrame with columns: route, date, daytype, rides.
        treated_routes: List of treated route identifiers.
        n_controls: Number of control routes to return.

    Returns:
        List of route identifier strings for the closest matches.
    """
    weekday = df[df["daytype"] == "W"]

    # Compute average rides per route
    route_avgs = weekday.groupby("route")["rides"].mean()

    # Average across treated routes
    treated_avg = route_avgs[route_avgs.index.isin(treated_routes)].mean()

    # Exclude treated routes from candidates
    candidates = route_avgs[~route_avgs.index.isin(treated_routes)]

    # Rank by distance to treated average
    distances = (candidates - treated_avg).abs()
    closest = distances.sort_values().head(n_controls)

    return closest.index.tolist()


def prepare_did_data(
    df: pd.DataFrame,
    treated_routes: list[str],
    control_routes: list[str],
    phase_dates: dict[str, date],
) -> pd.DataFrame:
    """Prepare panel data for difference-in-differences estimation.

    Adds columns:
        - treated: bool, True if route is in treated_routes.
        - post: bool, True if date is after the route's launch date.
        - treated_post: bool, interaction of treated and post.

    For control routes, `post` is determined by the earliest launch date
    among treated routes.

    Args:
        df: Ridership DataFrame with columns: route, date, daytype, rides.
        treated_routes: List of treated route identifiers.
        control_routes: List of control route identifiers.
        phase_dates: Dict mapping route -> launch date.

    Returns:
        DataFrame with added columns: treated, post, treated_post.
    """
    all_routes = set(treated_routes) | set(control_routes)
    result = df[df["route"].isin(all_routes)].copy()

    result["treated"] = result["route"].isin(treated_routes)

    # For control routes, use the earliest treated route's launch date
    earliest_launch = min(phase_dates.values())

    def _is_post(row):
        route = row["route"]
        if route in phase_dates:
            launch = pd.Timestamp(phase_dates[route])
        else:
            launch = pd.Timestamp(earliest_launch)
        return row["date"] >= launch

    result["post"] = result.apply(_is_post, axis=1)
    result["treated_post"] = result["treated"] & result["post"]

    return result.reset_index(drop=True)


