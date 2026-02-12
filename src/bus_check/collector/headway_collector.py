"""Headway collector: polls CTA Bus Tracker API and stores vehicle positions."""

import sqlite3
import time
from datetime import datetime, timezone

from bus_check.config import ALL_FREQUENT_ROUTES
from bus_check.data.bus_tracker import BusTrackerClient
from bus_check.data.db import create_schema, insert_vehicle_position


def collect_once(
    client: BusTrackerClient,
    db_conn: sqlite3.Connection,
    routes: list[str],
) -> int:
    """Single collection cycle.

    Calls get_vehicles for all routes, stores each vehicle position
    in the database.

    Returns the count of positions stored.
    """
    vehicles = client.get_vehicles(routes)
    collected_at = datetime.now(timezone.utc).isoformat()

    for v in vehicles:
        insert_vehicle_position(
            db_conn,
            collected_at=collected_at,
            vid=str(v.get("vid", "")),
            tmstmp=str(v.get("tmstmp", "")),
            route=str(v.get("rt", "")),
            direction=v.get("des"),
            destination=v.get("des"),
            lat=float(v.get("lat", 0)),
            lon=float(v.get("lon", 0)),
            heading=int(v["hdg"]) if "hdg" in v else None,
            speed=int(v["spd"]) if "spd" in v else None,
            pdist=int(v["pdist"]) if "pdist" in v else None,
            pattern_id=str(v["pid"]) if "pid" in v else None,
            delayed=bool(v.get("dly", False)),
        )

    return len(vehicles)


def run_collector(
    api_key: str,
    db_path: str,
    interval_seconds: int = 60,
    routes: list[str] | None = None,
) -> None:
    """Main collection loop.

    Creates a BusTrackerClient, opens the SQLite database, and calls
    collect_once on repeat at the specified interval.

    Args:
        api_key: CTA Bus Tracker API key.
        db_path: Path to the SQLite database file.
        interval_seconds: Seconds between collection cycles.
        routes: List of routes to collect. Defaults to ALL_FREQUENT_ROUTES.
    """
    if routes is None:
        routes = ALL_FREQUENT_ROUTES

    client = BusTrackerClient(api_key=api_key)
    conn = sqlite3.connect(db_path)
    create_schema(conn)

    try:
        while True:
            count = collect_once(client, conn, routes)
            print(f"Collected {count} vehicle positions")
            time.sleep(interval_seconds)
    finally:
        conn.close()


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ["CTA_API_KEY"]
    run_collector(api_key=api_key, db_path="data/headway.db")
