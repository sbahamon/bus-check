import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from bus_check.collector.headway_collector import collect_once, run_collector
from bus_check.data.bus_tracker import BusTrackerClient
from bus_check.data.db import create_schema, query_vehicle_positions


@pytest.fixture
def mock_client():
    client = MagicMock(spec=BusTrackerClient)
    return client


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    yield conn
    conn.close()


# --- collect_once ---


def test_collect_once_stores_positions(mock_client, db_conn):
    """collect_once should call get_vehicles and store results in DB."""
    mock_client.get_vehicles.return_value = [
        {
            "vid": "8001",
            "tmstmp": "20250401 08:00",
            "lat": "41.751245",
            "lon": "-87.654321",
            "hdg": "90",
            "pid": 7901,
            "rt": "79",
            "des": "Lakefront",
            "pdist": 15000,
            "dly": False,
            "spd": 25,
        },
        {
            "vid": "8002",
            "tmstmp": "20250401 08:00",
            "lat": "41.751300",
            "lon": "-87.684000",
            "hdg": "90",
            "pid": 7901,
            "rt": "79",
            "des": "Lakefront",
            "pdist": 8500,
            "dly": False,
            "spd": 18,
        },
    ]

    count = collect_once(mock_client, db_conn, routes=["79"])
    assert count == 2
    mock_client.get_vehicles.assert_called_once_with(["79"])


def test_collect_once_data_in_db(mock_client, db_conn):
    """Stored positions should be queryable from the DB."""
    mock_client.get_vehicles.return_value = [
        {
            "vid": "8001",
            "tmstmp": "20250401 08:00",
            "lat": "41.751245",
            "lon": "-87.654321",
            "hdg": "90",
            "pid": 7901,
            "rt": "79",
            "des": "Lakefront",
            "pdist": 15000,
            "dly": False,
            "spd": 25,
        },
    ]

    collect_once(mock_client, db_conn, routes=["79"])
    rows = query_vehicle_positions(db_conn, route="79")
    assert len(rows) == 1
    assert rows[0]["vid"] == "8001"
    assert rows[0]["route"] == "79"
    assert rows[0]["pdist"] == 15000
    assert rows[0]["lat"] == 41.751245


def test_collect_once_empty_vehicles(mock_client, db_conn):
    """Should handle empty vehicle list gracefully."""
    mock_client.get_vehicles.return_value = []

    count = collect_once(mock_client, db_conn, routes=["999"])
    assert count == 0
    rows = query_vehicle_positions(db_conn)
    assert len(rows) == 0


def test_collect_once_multiple_routes(mock_client, db_conn):
    """Should pass all routes to get_vehicles."""
    mock_client.get_vehicles.return_value = [
        {
            "vid": "8001",
            "tmstmp": "20250401 08:00",
            "lat": "41.75",
            "lon": "-87.65",
            "hdg": "90",
            "pid": 7901,
            "rt": "79",
            "des": "Lakefront",
            "pdist": 15000,
            "dly": False,
            "spd": 25,
        },
        {
            "vid": "6301",
            "tmstmp": "20250401 08:00",
            "lat": "41.78",
            "lon": "-87.63",
            "hdg": "90",
            "pid": 6301,
            "rt": "63",
            "des": "Stony Island",
            "pdist": 12000,
            "dly": False,
            "spd": 22,
        },
    ]

    count = collect_once(mock_client, db_conn, routes=["79", "63"])
    assert count == 2
    mock_client.get_vehicles.assert_called_once_with(["79", "63"])


def test_collect_once_handles_optional_fields(mock_client, db_conn):
    """Vehicle positions with missing optional fields should still store."""
    mock_client.get_vehicles.return_value = [
        {
            "vid": "8001",
            "tmstmp": "20250401 08:00",
            "lat": "41.75",
            "lon": "-87.65",
            "rt": "79",
        },
    ]
    count = collect_once(mock_client, db_conn, routes=["79"])
    assert count == 1


# --- run_collector (wiring test) ---


@patch("bus_check.collector.headway_collector.BusTrackerClient")
@patch("bus_check.collector.headway_collector.collect_once")
@patch("bus_check.collector.headway_collector.create_schema")
def test_run_collector_wiring(mock_create_schema, mock_collect, mock_client_cls, tmp_path):
    """run_collector should create a client, open DB, call collect_once."""
    db_path = str(tmp_path / "test.db")

    # Make collect_once raise after first call to break the loop
    mock_collect.side_effect = [3, KeyboardInterrupt]

    with pytest.raises(KeyboardInterrupt):
        run_collector(api_key="TEST_KEY", db_path=db_path, interval_seconds=0)

    # Should have created a BusTrackerClient
    mock_client_cls.assert_called_once_with(api_key="TEST_KEY")
    # Should have called create_schema
    mock_create_schema.assert_called_once()
    # Should have called collect_once at least once
    assert mock_collect.call_count >= 1
