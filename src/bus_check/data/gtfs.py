"""GTFS parser for computing scheduled headways."""

import os
import zipfile

import pandas as pd
import requests

from bus_check.config import GTFS_DOWNLOAD_URL


def download_gtfs(output_dir: str) -> None:
    """Download and unzip CTA GTFS data.

    Downloads the zip from GTFS_DOWNLOAD_URL and extracts all files
    into output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)

    resp = requests.get(GTFS_DOWNLOAD_URL)
    resp.raise_for_status()

    zip_path = os.path.join(output_dir, "google_transit.zip")
    with open(zip_path, "wb") as f:
        f.write(resp.content)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(output_dir)

    os.remove(zip_path)


def load_stop_times(gtfs_dir: str) -> pd.DataFrame:
    """Parse stop_times.txt from a GTFS directory."""
    path = os.path.join(gtfs_dir, "stop_times.txt")
    return pd.read_csv(path, dtype={"stop_id": str, "trip_id": str})


def load_trips(gtfs_dir: str) -> pd.DataFrame:
    """Parse trips.txt from a GTFS directory."""
    path = os.path.join(gtfs_dir, "trips.txt")
    return pd.read_csv(path, dtype={"route_id": str, "trip_id": str, "service_id": str})


def load_calendar(gtfs_dir: str) -> pd.DataFrame:
    """Parse calendar.txt from a GTFS directory."""
    path = os.path.join(gtfs_dir, "calendar.txt")
    return pd.read_csv(path, dtype={"service_id": str})


def _time_to_minutes(time_str: str) -> float:
    """Convert HH:MM:SS time string to minutes since midnight.

    Handles times >= 24:00:00 (common in GTFS for trips past midnight).
    """
    parts = time_str.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2]) if len(parts) > 2 else 0
    return hours * 60 + minutes + seconds / 60.0


def compute_scheduled_headways(
    gtfs_dir: str,
    route_id: str,
    direction_id: int,
    stop_id: str,
    service_id: str = None,
) -> pd.DataFrame:
    """Compute scheduled headways for a route/direction/stop.

    Joins stop_times with trips, filters to the specified route/direction/stop,
    sorts by arrival_time, and computes headway as the difference between
    consecutive arrivals.

    Returns a DataFrame with columns: arrival_time, headway_minutes.
    The first arrival has headway_minutes = NaN.
    """
    stop_times = load_stop_times(gtfs_dir)
    trips = load_trips(gtfs_dir)

    # Merge stop_times with trips to get route/direction info
    merged = stop_times.merge(trips, on="trip_id", how="inner")

    # Filter to specified route, direction, stop
    mask = (
        (merged["route_id"] == str(route_id))
        & (merged["direction_id"] == direction_id)
        & (merged["stop_id"] == str(stop_id))
    )
    if service_id is not None:
        mask = mask & (merged["service_id"] == service_id)

    filtered = merged[mask].copy()

    if filtered.empty:
        return pd.DataFrame(columns=["arrival_time", "headway_minutes"])

    # Convert arrival_time to minutes for sorting and diff
    filtered["arrival_minutes"] = filtered["arrival_time"].apply(_time_to_minutes)

    # Sort by arrival time
    filtered = filtered.sort_values("arrival_minutes").reset_index(drop=True)

    # Compute headway as diff between consecutive arrivals
    filtered["headway_minutes"] = filtered["arrival_minutes"].diff()

    return filtered[["arrival_time", "headway_minutes"]].reset_index(drop=True)
