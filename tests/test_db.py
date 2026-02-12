import sqlite3

from bus_check.data.db import (
    create_schema,
    insert_ridership,
    insert_vehicle_position,
    insert_stop_arrival,
    insert_reference_stop,
    query_ridership,
    query_vehicle_positions,
    query_stop_arrivals,
)


def _make_db():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return conn


def test_create_schema_creates_tables():
    conn = _make_db()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "ridership" in tables
    assert "vehicle_positions" in tables
    assert "stop_arrivals" in tables
    assert "reference_stops" in tables


def test_insert_and_query_ridership():
    conn = _make_db()
    insert_ridership(conn, "79", "2025-04-01", "W", 15000)
    insert_ridership(conn, "79", "2025-04-02", "W", 15500)
    insert_ridership(conn, "63", "2025-04-01", "W", 12000)

    rows = query_ridership(conn, routes=["79"])
    assert len(rows) == 2
    assert rows[0]["route"] == "79"
    assert rows[0]["rides"] == 15000


def test_query_ridership_date_filter():
    conn = _make_db()
    insert_ridership(conn, "79", "2025-03-01", "W", 14000)
    insert_ridership(conn, "79", "2025-04-01", "W", 15000)
    insert_ridership(conn, "79", "2025-05-01", "W", 16000)

    rows = query_ridership(conn, routes=["79"], start_date="2025-04-01")
    assert len(rows) == 2

    rows = query_ridership(
        conn, routes=["79"], start_date="2025-04-01", end_date="2025-04-30"
    )
    assert len(rows) == 1


def test_insert_and_query_vehicle_position():
    conn = _make_db()
    insert_vehicle_position(
        conn,
        collected_at="2025-04-01T08:00:00",
        vid="1234",
        tmstmp="2025-04-01T07:59:55",
        route="79",
        direction="Eastbound",
        destination="Lakefront",
        lat=41.75,
        lon=-87.65,
        heading=90,
        speed=25,
        pdist=15000,
        pattern_id="7901",
        delayed=False,
    )

    rows = query_vehicle_positions(conn, route="79")
    assert len(rows) == 1
    assert rows[0]["vid"] == "1234"
    assert rows[0]["pdist"] == 15000


def test_insert_and_query_stop_arrival():
    conn = _make_db()
    insert_stop_arrival(
        conn,
        route="79",
        direction="Eastbound",
        stop_id="4567",
        vid="1234",
        arrival_time="2025-04-01T08:05:00",
        pdist_at_arrival=15200,
    )
    insert_stop_arrival(
        conn,
        route="79",
        direction="Eastbound",
        stop_id="4567",
        vid="5678",
        arrival_time="2025-04-01T08:15:00",
        pdist_at_arrival=15180,
    )

    rows = query_stop_arrivals(conn, route="79", stop_id="4567")
    assert len(rows) == 2
    assert rows[0]["arrival_time"] < rows[1]["arrival_time"]


def test_insert_reference_stop():
    conn = _make_db()
    insert_reference_stop(
        conn,
        route="79",
        direction="Eastbound",
        stop_id="4567",
        stop_name="79th & Western",
        pdist=15000,
    )
    cursor = conn.execute(
        "SELECT * FROM reference_stops WHERE route=? AND direction=?",
        ("79", "Eastbound"),
    )
    row = cursor.fetchone()
    assert row is not None


def test_ridership_upsert():
    conn = _make_db()
    insert_ridership(conn, "79", "2025-04-01", "W", 15000)
    insert_ridership(conn, "79", "2025-04-01", "W", 16000)
    rows = query_ridership(conn, routes=["79"])
    assert len(rows) == 1
    assert rows[0]["rides"] == 16000
