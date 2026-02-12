import os
import zipfile
from pathlib import Path

import pandas as pd
import pytest
import responses

from bus_check.config import GTFS_DOWNLOAD_URL
from bus_check.data.gtfs import (
    compute_scheduled_headways,
    download_gtfs,
    load_calendar,
    load_stop_times,
    load_trips,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# --- load_stop_times ---


def test_load_stop_times(gtfs_sample_dir):
    df = load_stop_times(gtfs_sample_dir)
    assert isinstance(df, pd.DataFrame)
    assert "trip_id" in df.columns
    assert "arrival_time" in df.columns
    assert "stop_id" in df.columns
    assert "stop_sequence" in df.columns
    assert len(df) == 24  # 6 trips * 3 stops + 3 trips * 2 stops


# --- load_trips ---


def test_load_trips(gtfs_sample_dir):
    df = load_trips(gtfs_sample_dir)
    assert isinstance(df, pd.DataFrame)
    assert "trip_id" in df.columns
    assert "route_id" in df.columns
    assert "direction_id" in df.columns
    assert "service_id" in df.columns
    assert len(df) == 9  # 6 + 3


# --- load_calendar ---


def test_load_calendar(gtfs_sample_dir):
    df = load_calendar(gtfs_sample_dir)
    assert isinstance(df, pd.DataFrame)
    assert "service_id" in df.columns
    assert len(df) == 1


# --- compute_scheduled_headways ---


def test_headways_route_79_stop_b(gtfs_sample_dir):
    """Route 79 has 6 trips at STOP_B with 10-min headways."""
    result = compute_scheduled_headways(
        gtfs_sample_dir,
        route_id="79",
        direction_id=0,
        stop_id="STOP_B",
    )
    assert isinstance(result, pd.DataFrame)
    assert "arrival_time" in result.columns
    assert "headway_minutes" in result.columns
    # 6 arrivals -> 5 headway gaps
    headways = result["headway_minutes"].dropna()
    assert len(headways) == 5
    # All should be 10 minutes
    assert all(h == 10.0 for h in headways)


def test_headways_route_63_stop_e(gtfs_sample_dir):
    """Route 63 has 3 trips at STOP_E with 15-min headways."""
    result = compute_scheduled_headways(
        gtfs_sample_dir,
        route_id="63",
        direction_id=0,
        stop_id="STOP_E",
    )
    headways = result["headway_minutes"].dropna()
    assert len(headways) == 2
    assert all(h == 15.0 for h in headways)


def test_headways_with_service_id_filter(gtfs_sample_dir):
    """Should filter by service_id when provided."""
    result = compute_scheduled_headways(
        gtfs_sample_dir,
        route_id="79",
        direction_id=0,
        stop_id="STOP_B",
        service_id="WKD",
    )
    headways = result["headway_minutes"].dropna()
    assert len(headways) == 5


def test_headways_nonexistent_route(gtfs_sample_dir):
    """Nonexistent route/stop should return empty DataFrame."""
    result = compute_scheduled_headways(
        gtfs_sample_dir,
        route_id="999",
        direction_id=0,
        stop_id="STOP_Z",
    )
    assert len(result) == 0


def test_headways_sorted_by_arrival_time(gtfs_sample_dir):
    """Result should be sorted by arrival_time."""
    result = compute_scheduled_headways(
        gtfs_sample_dir,
        route_id="79",
        direction_id=0,
        stop_id="STOP_B",
    )
    times = result["arrival_time"].tolist()
    assert times == sorted(times)


# --- download_gtfs ---


@responses.activate
def test_download_gtfs(tmp_path):
    """download_gtfs should download and unzip the GTFS archive."""
    # Create a fake zip in memory
    zip_path = tmp_path / "fake.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("stop_times.txt", "trip_id,arrival_time\n")
        zf.writestr("trips.txt", "route_id,trip_id\n")

    with open(zip_path, "rb") as f:
        zip_bytes = f.read()

    responses.add(
        responses.GET,
        GTFS_DOWNLOAD_URL,
        body=zip_bytes,
        status=200,
        content_type="application/zip",
    )

    output_dir = str(tmp_path / "gtfs_output")
    download_gtfs(output_dir)

    assert os.path.isfile(os.path.join(output_dir, "stop_times.txt"))
    assert os.path.isfile(os.path.join(output_dir, "trips.txt"))
